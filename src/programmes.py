"""Programme detection: families of units wider than a series, each with its evidence.

A programme is a set of units the publisher produced from one template, such as
the Edmonton Insight Community surveys. They match each other on shared wording
and columns, which swamps the neighbour lists (spec, Outputs). Works on the same
units as `src/similarity.py` (series counted once) and writes
`data/processed/programmes/<date>/`:

- `assignments.csv` one row per unit, including units with no programme
- `families.csv`    one row per family: its evidence, size, sample names, common tags
- `summary.json`    counts, overlaps between families, groups just under a threshold

Each family comes from ONE kind of evidence. Families are never chained or merged:
a unit in two families keeps the larger as its `programme_key` (on a tie: suffix,
then purpose, then columns) and lists the others under `also_in`, and every pair
of overlapping families is reported.

    python -m src.programmes RAW_SNAPSHOT_DIR [--inventory CSV] [--out DIR]
"""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import logging
import re
import sys
from pathlib import Path

from src.similarity import build_units

log = logging.getLogger("programmes")

ROOT = Path(__file__).resolve().parents[1]
PURPOSE_KEY = "General-Information_Purpose"
# Minimum units per family, per evidence kind. Starting guesses (owner, 2026-11-03);
# the summary's `near_threshold` shows what each would add if lowered.
MIN_UNITS = {"suffix": 5, "purpose": 4, "columns": 5}
NEAR = 2
# One-word suffixes are statuses, formats or years ("Deprecated", "History",
# "WGS84", "2019"), not publisher templates.
MIN_SUFFIX_WORDS = 2
# One or two shared columns ("name", "area id") don't make a template.
MIN_COLUMNS = 3
PRIORITY = {"suffix": 0, "purpose": 1, "columns": 2}
TAG_SHARE = 0.8
ASSIGNMENT_FIELDS = ["unit", "name", "programme_key", "evidence", "also_in"]
FAMILY_FIELDS = ["programme_key", "evidence", "n_units", "label", "common_tags", "sample_names"]


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def title_suffix(name):
    parts = re.split(r" [-\u2013] ", name)
    suffix = norm(parts[-1]) if len(parts) > 1 else ""
    return suffix if len(suffix.split()) >= MIN_SUFFIX_WORDS else ""


def purposes(member_ids, by_id):
    """Distinct Purpose texts across a unit's members (series members can differ)."""
    out = set()
    for i in member_ids:
        for m in by_id[i]["classification"].get("domain_metadata") or []:
            if m.get("key") == PURPOSE_KEY and norm(m.get("value")):
                out.add(norm(m["value"]))
    return out


def short_hash(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def detect(raw, inventory):
    by_id = {a["resource"]["id"]: a for a in raw}
    units = build_units(raw, inventory)
    groups = {kind: collections.defaultdict(list) for kind in MIN_UNITS}
    for u in units:
        # Suffix and Purpose both look at every series member, as the schema signal does.
        members = u["member_ids"].split(";")
        for sfx in {title_suffix(by_id[i]["resource"]["name"]) for i in members} - {""}:
            groups["suffix"][sfx].append(u)
        for p in purposes(members, by_id):
            groups["purpose"][p].append(u)
        if len(u["fields"]) >= MIN_COLUMNS:
            groups["columns"][" ".join(u["fields"])].append(u)

    families, near = [], []
    for kind, by_value in groups.items():
        for value, members in by_value.items():
            n = len(members)
            key = f"suffix:{value}" if kind == "suffix" else f"{kind}:{short_hash(value)}"
            if n >= MIN_UNITS[kind]:
                families.append({"programme_key": key, "evidence": kind, "label": value,
                                 "members": members})
            elif n >= MIN_UNITS[kind] - NEAR and n > 1:
                near.append({"key": key, "evidence": kind, "n_units": n, "label": value,
                             "units": sorted(u["unit"] for u in members)})

    def tags(u):
        return set().union(*[set(by_id[i]["classification"].get("domain_tags") or [])
                             for i in u["member_ids"].split(";")])
    for f in families:
        f["n_units"] = len(f["members"])
        counts = collections.Counter(t for u in f["members"] for t in tags(u))
        f["common_tags"] = ";".join(sorted(t for t, c in counts.items() if c >= TAG_SHARE * f["n_units"]))
        f["sample_names"] = "; ".join(sorted(u["name"] for u in f["members"])[:3])
    families.sort(key=lambda f: (-f["n_units"], PRIORITY[f["evidence"]], f["programme_key"]))

    in_families = collections.defaultdict(list)
    for f in families:  # largest first, so in_families[unit][0] is the largest
        for u in f["members"]:
            in_families[u["unit"]].append(f)
    assignments = []
    for u in units:
        fs = in_families.get(u["unit"], [])
        assignments.append({
            "unit": u["unit"], "name": u["name"],
            "programme_key": fs[0]["programme_key"] if fs else "",
            "evidence": fs[0]["evidence"] if fs else "",
            "also_in": ";".join(f["programme_key"] for f in fs[1:]),
        })
    if len(assignments) != len(units):
        raise RuntimeError(f"{len(units)} units in, {len(assignments)} assignments out")

    overlaps = collections.Counter()
    for fs in in_families.values():
        for i, a in enumerate(fs):
            for b in fs[i + 1:]:
                overlaps[(a["programme_key"], b["programme_key"])] += 1
    summary = {
        "n_units": len(units),
        "n_with_programme": sum(1 for a in assignments if a["programme_key"]),
        "n_without_programme": sum(1 for a in assignments if not a["programme_key"]),
        "n_in_several": sum(1 for a in assignments if a["also_in"]),
        "min_units": MIN_UNITS,
        "families_by_evidence": dict(collections.Counter(f["evidence"] for f in families)),
        "overlaps": [{"a": a, "b": b, "shared_units": n} for (a, b), n in overlaps.most_common()],
        "near_threshold": sorted(near, key=lambda r: (r["evidence"], -r["n_units"], r["key"])),
    }
    return assignments, families, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw_dir")
    ap.add_argument("--inventory", help="default: data/processed/inventory/<snapshot date>.csv")
    ap.add_argument("--out", default=str(ROOT / "data/processed/programmes"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    raw_dir = Path(args.raw_dir)
    inv_path = Path(args.inventory or ROOT / f"data/processed/inventory/{raw_dir.name}.csv")
    with gzip.open(raw_dir / "catalog.json.gz", "rt", encoding="utf-8") as f:
        raw = json.load(f)
    with open(inv_path, newline="", encoding="utf-8") as f:
        inventory = list(csv.DictReader(f))
    inv_abs = inv_path.resolve()
    inv_label = str(inv_abs.relative_to(ROOT)) if inv_abs.is_relative_to(ROOT) else str(inv_abs)

    assignments, families, summary = detect(raw, inventory)
    out = Path(args.out) / raw_dir.name
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "assignments.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ASSIGNMENT_FIELDS)
        w.writeheader()
        w.writerows(assignments)
    with open(out / "families.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FAMILY_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(families)
    summary = {"snapshot": raw_dir.name, "inventory": inv_label, **summary}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    log.info("programmes path=%s %s", out, json.dumps({k: v for k, v in summary.items()
                                                       if k not in ("overlaps", "near_threshold")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
