"""M3c: hand-labelled neighbour spot-check (~20 units) before any neighbour output is shown.

`sample` picks units across strata and lists each one's top-k text and schema
neighbours, de-duplicated into pairs. `extend` adds a later signal's top-k for the
same units: ranks go onto existing pairs, new neighbours become new pairs with new
ids, so existing labels stay valid. `score` reads the owner's labels and reports
precision per signal (spec, Outputs).

    python -m src.spotcheck sample SIMILARITY_DIR [--k 5] [--seed 0] [--out DIR]
    python -m src.spotcheck extend PAIRS_CSV SIMILARITY_DIR [--signal embed] [--k 5]
    python -m src.spotcheck score PAIRS_CSV LABELS_CSV

Pairs carry titles, ids and scores only (no descriptions), so they can be committed.
"""
import argparse
import collections
import csv
import json
import logging
import sys
from pathlib import Path

import numpy as np

log = logging.getLogger("spotcheck")

ROOT = Path(__file__).resolve().parents[1]
# (stratum, how many units). "series" = a series unit outside Surveys/Census;
# "category" = one unit from each of the largest remaining categories.
STRATA = [("Surveys", 2), ("Census", 1), ("(none)", 2), ("series", 2), ("category", 13)]
PAIR_FIELDS = ["pair_id", "stratum", "unit", "unit_name", "unit_id", "unit_category", "n_members",
               "neighbour", "neighbour_name", "neighbour_id", "neighbour_category",
               "text_rank", "text_score", "schema_rank", "schema_score", "shared_fields",
               "embed_rank", "embed_score"]
SIGNALS = ("text", "schema", "embed")
VERDICTS = {"yes", "no", "unsure"}


def pick_units(units, seed):
    rng = np.random.default_rng(seed)
    cat = lambda u: u["category"] or "(none)"
    taken, picked = set(), []

    def take(pool, n, stratum):
        pool = sorted((u for u in pool if u["unit"] not in taken), key=lambda u: u["unit"])
        for i in rng.choice(len(pool), min(n, len(pool)), replace=False):
            taken.add(pool[i]["unit"])
            picked.append((stratum, pool[i]))

    for stratum, n in STRATA:
        if stratum == "series":
            take([u for u in units if int(u["n_members"]) > 1 and cat(u) not in ("Surveys", "Census")], n, stratum)
        elif stratum == "category":
            sizes = collections.Counter(cat(u) for u in units)
            rest = [c for c, _ in sizes.most_common() if c not in ("Surveys", "Census", "(none)")]
            for c in rest[:n]:
                take([u for u in units if cat(u) == c], 1, f"category:{c}")
        else:
            take([u for u in units if cat(u) == stratum], n, stratum)
    return picked


def build_pairs(units, neighbours, k=5, seed=0):
    by_unit = {u["unit"]: u for u in units}
    nn = collections.defaultdict(list)
    for r in neighbours:
        if int(r["rank"]) <= k:
            nn[r["unit"]].append(r)
    pairs = []
    for stratum, u in pick_units(units, seed):
        merged = {}
        for r in sorted(nn[u["unit"]], key=lambda r: (r["signal"] != "text", int(r["rank"]))):
            v = by_unit[r["neighbour"]]
            p = merged.setdefault(r["neighbour"], {
                "stratum": stratum, "unit": u["unit"], "unit_name": u["name"],
                "unit_id": u["representative_id"], "unit_category": u["category"],
                "n_members": u["n_members"], "neighbour": v["unit"], "neighbour_name": v["name"],
                "neighbour_id": v["representative_id"], "neighbour_category": v["category"],
                "text_rank": "", "text_score": "", "schema_rank": "", "schema_score": "",
                "shared_fields": "", "embed_rank": "", "embed_score": ""})
            p[f"{r['signal']}_rank"], p[f"{r['signal']}_score"] = int(r["rank"]), r["score"]
            if r["signal"] == "schema":
                p["shared_fields"] = r["shared_fields"]
        pairs += merged.values()
    for i, p in enumerate(pairs, start=1):
        p["pair_id"] = f"p{i:03d}"
    return pairs


def extend(pairs, units, neighbours, signal, k=5):
    by_unit = {u["unit"]: u for u in units}
    existing = {(p["unit"], p["neighbour"]): p for p in pairs}
    first = {}
    for p in pairs:
        first.setdefault(p["unit"], p)
        p.setdefault(f"{signal}_rank", ""), p.setdefault(f"{signal}_score", "")
    if any(p[f"{signal}_rank"] != "" for p in pairs):
        raise ValueError(f"pairs already carry {signal} ranks")
    new = []
    for r in neighbours:
        if r["unit"] not in first or int(r["rank"]) > k:
            continue
        p = existing.get((r["unit"], r["neighbour"]))
        if p is None:
            h, v = first[r["unit"]], by_unit[r["neighbour"]]
            p = {f: "" for f in PAIR_FIELDS}
            p.update({f: h[f] for f in ("stratum", "unit", "unit_name", "unit_id", "unit_category", "n_members")})
            p.update({"neighbour": v["unit"], "neighbour_name": v["name"],
                      "neighbour_id": v["representative_id"], "neighbour_category": v["category"]})
            new.append(p)
        p[f"{signal}_rank"], p[f"{signal}_score"] = int(r["rank"]), r["score"]
    for i, p in enumerate(new, start=len(pairs) + 1):
        p["pair_id"] = f"p{i:03d}"
    return pairs + new


def score(pairs, labels):
    """Precision of each signal's top-k: share of labelled neighbours judged related.
    `unsure` and unlabelled pairs are counted, not scored."""
    verdict = {}
    for r in labels:
        if r["verdict"] not in VERDICTS:
            raise ValueError(f"{r['pair_id']}: verdict {r['verdict']!r} not in {sorted(VERDICTS)}")
        verdict[r["pair_id"]] = r["verdict"]
    unknown = set(verdict) - {p["pair_id"] for p in pairs}
    if unknown:
        raise ValueError(f"labels for pairs not in the sample: {sorted(unknown)[:5]}")
    out = {"pairs": len(pairs), "labelled": len(verdict),
           "unsure": sum(v == "unsure" for v in verdict.values()), "signals": {}}
    for signal in (s for s in SIGNALS if any(f"{s}_rank" in p for p in pairs)):
        mine = [p for p in pairs if p.get(f"{signal}_rank", "") != ""]
        judged = [verdict[p["pair_id"]] for p in mine if verdict.get(p["pair_id"]) in ("yes", "no")]
        per_unit = collections.defaultdict(list)
        for p in mine:
            if verdict.get(p["pair_id"]) in ("yes", "no"):
                per_unit[p["unit"]].append(verdict[p["pair_id"]] == "yes")
        out["signals"][signal] = {
            "neighbours": len(mine), "judged": len(judged),
            "precision": round(judged.count("yes") / len(judged), 3) if judged else None,
            "units_with_no_good_neighbour": sum(1 for v in per_unit.values() if not any(v)),
        }
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("similarity_dir")
    s.add_argument("--k", type=int, default=5)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--out", default=str(ROOT / "data/spotcheck"))
    e = sub.add_parser("extend")
    e.add_argument("pairs_csv")
    e.add_argument("similarity_dir")
    e.add_argument("--signal", default="embed")
    e.add_argument("--k", type=int, default=5)
    c = sub.add_parser("score")
    c.add_argument("pairs_csv")
    c.add_argument("labels_csv")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    read = lambda p: list(csv.DictReader(open(p, newline="", encoding="utf-8")))
    if args.cmd == "sample":
        sim = Path(args.similarity_dir)
        pairs = build_pairs(read(sim / "units.csv"), read(sim / "neighbours.csv"), args.k, args.seed)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{sim.name}_pairs.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=PAIR_FIELDS)
            w.writeheader()
            w.writerows(pairs)
        log.info("spotcheck path=%s units=%d pairs=%d", path, len({p["unit"] for p in pairs}), len(pairs))
    elif args.cmd == "extend":
        sim = Path(args.similarity_dir)
        before = read(args.pairs_csv)
        n = len(before)
        pairs = extend(before, read(sim / "units.csv"), read(sim / f"{args.signal}_neighbours.csv"),
                       args.signal, args.k)
        with open(args.pairs_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=PAIR_FIELDS)
            w.writeheader()
            w.writerows(pairs)
        log.info("spotcheck extend path=%s signal=%s new_pairs=%d total=%d",
                 args.pairs_csv, args.signal, len(pairs) - n, len(pairs))
    else:
        print(json.dumps(score(read(args.pairs_csv), read(args.labels_csv)), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
