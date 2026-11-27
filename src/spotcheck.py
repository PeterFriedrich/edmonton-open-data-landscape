"""M3c: hand-labelled neighbour spot-check (~20 units) before any neighbour output is shown.

`sample` picks units across strata and lists each one's top-k text and schema
neighbours, de-duplicated into pairs. `extend` adds a later signal's top-k for the
same units: ranks go onto existing pairs, new neighbours become new pairs with new
ids, so existing labels stay valid. `score` reads the owner's labels and reports
precision per signal, per stratum and inside/outside programmes, with the gate
(spec, Outputs; DECISIONS 2026-11-20).

    python -m src.spotcheck sample SIMILARITY_DIR [--k 5] [--seed 0] [--out DIR]
    python -m src.spotcheck extend PAIRS_CSV SIMILARITY_DIR [--signal embed] [--k 5]
    python -m src.spotcheck score PAIRS_CSV LABELS_CSV --programmes ASSIGNMENTS_CSV

`probe_score` ranks the owner's expected neighbours in each method's full list (DECISIONS
2026-11-27); its command waits for the picks.

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
# The 2026-11-20 spot-check decision rule (docs/DECISIONS.md): a signal's neighbour list
# is shown only if precision (unsure = miss) is at least this and at most this many units
# have no good neighbour in their top k. Provisional; a change after the tally is read
# needs its own DECISIONS row.
GATE_MIN_PRECISION = 0.70
GATE_MAX_UNITS_NO_GOOD = 3
# The expected-neighbour probe's rule (docs/DECISIONS.md 2026-11-27), locked before
# the picks were scored: headline = share of picks in a method's top PROBE_TOP_K.
PROBE_TOP_K = 5
PROBE_ALSO_K = 10


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


def _signal_block(signal, pairs, verdict):
    """One signal's figures over `pairs` (all pairs of one scope). Unsure counts as a
    miss in `precision` and is dropped in `precision_unsure_dropped` (DECISIONS 2026-11-20)."""
    units = {p["unit"] for p in pairs}
    by_unit = collections.defaultdict(list)
    for p in pairs:
        if p.get(f"{signal}_rank", "") != "":
            by_unit[p["unit"]].append(verdict.get(p["pair_id"]))
    v = [x for xs in by_unit.values() for x in xs]
    yes, no, unsure = v.count("yes"), v.count("no"), v.count("unsure")
    labelled = yes + no + unsure
    seen = {u: [x for x in xs if x] for u, xs in by_unit.items()}
    # "No good neighbour" needs every pair judged: an unlabelled pair could still be a yes.
    done = [xs for xs in by_unit.values() if all(xs)]
    return {
        "neighbours": len(v), "labelled": labelled, "unlabelled": len(v) - labelled,
        "yes": yes, "no": no, "unsure": unsure,
        "precision": round(yes / labelled, 3) if labelled else None,
        "precision_unsure_dropped": round(yes / (yes + no), 3) if yes + no else None,
        "units": len(units),
        "units_with_no_neighbours": len(units - set(by_unit)),
        "units_unlabelled": sum(1 for xs in seen.values() if not xs),
        "units_partly_labelled": sum(1 for u, xs in seen.items() if xs and len(xs) < len(by_unit[u])),
        "units_with_no_good_neighbour": sum(1 for xs in done if "yes" not in xs),
        "units_all_unsure": sum(1 for xs in done if set(xs) == {"unsure"}),
    }


def _gate(b):
    if not b["neighbours"]:
        return {"status": "no_pairs"}
    if b["unlabelled"]:
        return {"status": "incomplete", "unlabelled": b["unlabelled"]}
    ok = (b["labelled"] and b["yes"] / b["labelled"] >= GATE_MIN_PRECISION
          and b["units_with_no_good_neighbour"] <= GATE_MAX_UNITS_NO_GOOD)
    return {"status": "pass" if ok else "fail"}


def score(pairs, labels, programmes):
    """Precision of each signal's top-k, pooled, per scope and per stratum, and the
    2026-11-20 gate on units outside programmes. `programmes` maps unit -> programme_key
    ("" when the unit is in none). Programme units' gate waits for their pairs to be
    redrawn after sibling removal (DECISIONS 2026-11-20)."""
    verdict = {}
    for r in labels:
        if r["verdict"] not in VERDICTS:
            raise ValueError(f"{r['pair_id']}: verdict {r['verdict']!r} not in {sorted(VERDICTS)}")
        verdict[r["pair_id"]] = r["verdict"]
    unknown = set(verdict) - {p["pair_id"] for p in pairs}
    if unknown:
        raise ValueError(f"labels for pairs not in the sample: {sorted(unknown)[:5]}")
    missing = {p["unit"] for p in pairs} - set(programmes)
    if missing:
        raise ValueError(f"units not in the programme assignments: {sorted(missing)[:5]}")
    signals = [s for s in SIGNALS if any(f"{s}_rank" in p for p in pairs)]
    blocks = lambda ps: {s: _signal_block(s, ps, verdict) for s in signals}
    outside = blocks([p for p in pairs if not programmes[p["unit"]]])
    inside = blocks([p for p in pairs if programmes[p["unit"]]])
    for b in outside.values():
        b["gate"] = _gate(b)
    for b in inside.values():
        b["gate"] = {"status": "pending_redraw"}
    strata = collections.defaultdict(list)
    for p in pairs:
        strata["category" if p["stratum"].startswith("category:") else p["stratum"]].append(p)
    return {
        "pairs": len(pairs), "labelled": len(verdict),
        "unsure": sum(v == "unsure" for v in verdict.values()),
        "gate": {"min_precision": GATE_MIN_PRECISION, "max_units_no_good": GATE_MAX_UNITS_NO_GOOD,
                 "scope": "outside_programmes"},
        "signals": blocks(pairs), "outside_programmes": outside, "in_programmes": inside,
        "by_stratum": {k: blocks(v) for k, v in strata.items()},
    }


def _probe_block(per_unit):
    """Average within each unit first, then across units, so a unit with 3 picks
    weighs the same as one with 1."""
    if not per_unit:
        return {"units": 0, "top5": None, "top10": None, "median_rank": None}
    m = lambda key: round(float(np.mean([u[key] for u in per_unit])), 3)
    return {"units": len(per_unit), "top5": m("top5"), "top10": m("top10"),
            "median_rank": float(np.median([u["median_rank"] for u in per_unit]))}


def probe_score(picks, rankings, programmes):
    """Rank of each owner-expected neighbour in each method's full list.

    `picks` maps unit -> list of picked units (already mapped from dataset ids), or
    None for "None come to mind". `rankings` maps method -> unit -> every other unit,
    best first. `programmes` maps unit -> programme_key ("" when in none).

    The unit itself and its same-programme siblings are removed from the list before
    ranking; a sibling pick is reported apart (`structure_picks`, "shown in the
    structure section"), and a pick of the unit itself (a series twin) under
    `self_picks`. The headline scope is units outside programmes; programme units are
    reported apart until their redraw (DECISIONS 2026-11-27)."""
    missing = set(picks) - set(programmes)
    if missing:
        raise ValueError(f"units not in the programme assignments: {sorted(missing)[:5]}")
    out = {"top_k": PROBE_TOP_K, "also_k": PROBE_ALSO_K, "scope": "outside_programmes",
           "units_none": sorted(u for u, ps in picks.items() if ps is None), "methods": {}}
    for method, ranking in rankings.items():
        scopes = {"outside_programmes": [], "in_programmes": []}
        structure, self_picks = [], []
        for unit, ps in sorted(picks.items()):
            if not ps:
                continue
            if unit not in ranking:
                raise ValueError(f"{method}: no ranking for unit {unit!r}")
            prog = programmes[unit]
            sib = {u for u, k in programmes.items() if prog and k == prog and u != unit}
            order = [u for u in ranking[unit] if u != unit and u not in sib]
            pos = {u: i + 1 for i, u in enumerate(order)}
            ranks = []
            for p in ps:
                if p == unit:
                    self_picks.append((unit, p))
                elif p in sib:
                    structure.append((unit, p))
                elif p not in pos:
                    raise ValueError(f"{method}: pick {p!r} for {unit!r} is not in its ranking")
                else:
                    ranks.append(pos[p])
            if not ranks:
                continue
            scopes["in_programmes" if prog else "outside_programmes"].append({
                "top5": sum(r <= PROBE_TOP_K for r in ranks) / len(ranks),
                "top10": sum(r <= PROBE_ALSO_K for r in ranks) / len(ranks),
                "median_rank": float(np.median(ranks))})
        out["methods"][method] = {
            "outside_programmes": _probe_block(scopes["outside_programmes"]),
            "in_programmes": dict(_probe_block(scopes["in_programmes"]), status="pending_redraw"),
            "structure_picks": len(structure), "self_picks": len(self_picks)}
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
    c.add_argument("--programmes", required=True,
                   help="assignments.csv from src.programmes for the same snapshot")
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
        programmes = {r["unit"]: r["programme_key"] for r in read(args.programmes)}
        print(json.dumps(score(read(args.pairs_csv), read(args.labels_csv), programmes), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
