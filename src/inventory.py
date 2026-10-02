"""M1c: inventory the catalogue, one row per asset, nothing dropped.

Reads a RAW snapshot (it needs descriptions for licence keywords) and writes
`data/processed/inventory/<date>.csv` plus `<date>_summary.json`. Every asset
gets a role; excluded ones carry a reason instead of disappearing. Series
members are grouped under a key, not merged.

    python -m src.inventory RAW_SNAPSHOT_DIR [--out DIR]
"""
import argparse
import collections
import csv
import gzip
import json
import logging
import re
import sys
from pathlib import Path

log = logging.getLogger("inventory")

ROOT = Path(__file__).resolve().parents[1]

# Publisher custom fields: raw key -> output column, with lowercase/stripped value
# -> canonical value. Values outside a map are kept (stripped) and flagged.
CUSTOM = {
    "Time-Frame_Update-Frequency": ("update_frequency", {
        "not updated (historical only)": "Not Updated (Historical Only)", "weekly": "Weekly",
        "when necessary": "When Necessary", "daily": "Daily", "monthly": "Monthly",
        "annually": "Annually", "annual": "Annually", "x times per day": "X times per day",
        "hourly": "Hourly", "quarterly": "Quarterly", "near real-time": "Near Real-Time",
        "bi-weekly": "Bi-Weekly"}),
    "Time-Frame_Automated-or-Manual": ("automated_or_manual", {"automated": "Automated", "manual": "Manual"}),
    "General-Information_Internal-or-External": ("internal_or_external", {
        "internal": "Internal", "internally sourced data": "Internal", "external": "External",
        "externally sourced data": "External", "combined": "Combined", "crowdsourced": "Crowdsourced"}),
    "General-Information_Primary-Dataset-or-View": ("primary_or_view", {"primary": "Primary", "view": "View"}),
    "Quality-Indicators_Duplicates-Removed": ("duplicates_removed", {"yes": "Yes", "no": "No"}),
    "Quality-Indicators_Verified-for-Accuracy": ("verified_for_accuracy", {"yes": "Yes", "no": "No"}),
    "Time-Frame_Period-of-Coverage": ("period_of_coverage", None),  # free text, kept as is
}

# Attributions that name the City or one of its own units, not an outside source.
CITY_ATTRIBUTION = re.compile(
    r"^(the )?city of edmonton\b|^(parks and roads services|financial and corporate services|"
    r"edmonton transit service|business performance|governance and legislative services|"
    r"engineering and survey services)$", re.I)
# Strong phrases only: a bare "licence" mostly means business or pet licences,
# and "Terms of Use" mostly means the City's own ("as per our Terms of Use").
DESCRIPTION_LICENCE = re.compile(
    r"licen[cs]e agreement|licensed under|open government licen[cs]e|/licen[cs]e\b", re.I)
EXTERNAL_CATEGORY = "Externally Sourced Datasets"
DERIVED_TYPES = {"map", "chart", "filter", "story", "calendar"}

FIELDS = [
    "id", "name", "type", "category", "role", "exclusion_reason", "parent_ids", "parent_missing",
    "series_key", "series_size", "licence_class", "licence_signals", "licence_field", "attribution",
    "update_frequency", "automated_or_manual", "internal_or_external", "primary_or_view",
    "duplicates_removed", "verified_for_accuracy", "period_of_coverage", "data_updated_at",
    "metadata_updated_at", "created_at", "n_columns", "unrecognised_values",
]


def series_stem(name):
    """Name with years and other numbers replaced, so yearly or per-site
    members of one series ("Speed Check Sign - DFS041") share a stem."""
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", name.lower())).strip()


def normalise_custom(domain_metadata):
    out, unrecognised = {col: None for col, _ in CUSTOM.values()}, []
    for m in domain_metadata or []:
        if m["key"] not in CUSTOM:
            continue
        col, mapping = CUSTOM[m["key"]]
        value = (m["value"] or "").strip()
        if not value:
            continue
        if mapping is None:
            out[col] = value
        elif value.lower() in mapping:
            out[col] = mapping[value.lower()]
        else:
            out[col] = value
            unrecognised.append(f"{col}={value}")
    return out, unrecognised


def licence_signals(asset, custom):
    res = asset["resource"]
    attribution = (res.get("attribution") or "").strip()
    licence = (asset.get("metadata") or {}).get("license")
    signals = []
    if custom["internal_or_external"] in ("External", "Combined", "Crowdsourced"):
        signals.append(f"internal_or_external={custom['internal_or_external']}")
    if asset["classification"].get("domain_category") == EXTERNAL_CATEGORY:
        signals.append("category=external")
    if attribution and not CITY_ATTRIBUTION.search(attribution):
        signals.append("attribution=non_city")
    if licence and licence != "See Terms of Use":
        signals.append(f"licence_field={licence}")
    if DESCRIPTION_LICENCE.search(res.get("description") or ""):
        signals.append("description=licence_phrase")
    if signals:
        return "third_party", signals
    city_evidence = CITY_ATTRIBUTION.search(attribution) or custom["internal_or_external"] == "Internal"
    return ("city" if city_evidence else "unknown"), signals


def role_of(res, ids):
    parents = res.get("parent_fxf") or []
    missing = [p for p in parents if p not in ids]
    if res["type"] == "dataset" and not parents:
        return "candidate", "", missing
    if parents:
        reason = f"derived:{res['type']}" + (":parent_missing" if missing else "")
        return "derived", reason, missing
    return "non_tabular", f"standalone:{res['type']}", missing


def build_inventory(raw):
    ids = {a["resource"]["id"] for a in raw}
    rows = []
    for a in raw:
        res = a["resource"]
        custom, unrecognised = normalise_custom(a["classification"].get("domain_metadata"))
        role, reason, missing = role_of(res, ids)
        cls, signals = licence_signals(a, custom)
        rows.append({
            "id": res["id"], "name": res["name"], "type": res["type"],
            "category": a["classification"].get("domain_category") or "",
            "role": role, "exclusion_reason": reason,
            "parent_ids": ";".join(res.get("parent_fxf") or []), "parent_missing": ";".join(missing),
            "series_key": "", "series_size": 1,
            "licence_class": cls, "licence_signals": ";".join(signals),
            "licence_field": (a.get("metadata") or {}).get("license") or "",
            "attribution": res.get("attribution") or "",
            **{k: v or "" for k, v in custom.items()},
            "data_updated_at": res.get("data_updated_at") or "",
            "metadata_updated_at": res.get("metadata_updated_at") or "",
            "created_at": res.get("createdAt") or "",
            "n_columns": len(res.get("columns_field_name") or []),
            "unrecognised_values": ";".join(unrecognised),
        })

    groups = collections.defaultdict(list)
    for r in rows:
        if r["role"] == "candidate":
            groups[(r["category"], series_stem(r["name"]))].append(r)
    for (category, stem), members in groups.items():
        if len(members) > 1:
            for r in members:
                r["series_key"] = f"{category}|{stem}"
                r["series_size"] = len(members)

    if len(rows) != len(raw) or len({r["id"] for r in rows}) != len(raw):
        raise RuntimeError(f"inventory has {len(rows)} rows for {len(raw)} assets")
    return sorted(rows, key=lambda r: r["id"])


def summarise(rows):
    C = collections.Counter
    candidates = [r for r in rows if r["role"] == "candidate"]
    series = {r["series_key"] for r in candidates if r["series_key"]}
    in_series = sum(1 for r in candidates if r["series_key"])
    return {
        "n_assets": len(rows),
        "roles": dict(C(r["role"] for r in rows)),
        "exclusion_reasons": dict(C(r["exclusion_reason"] for r in rows if r["exclusion_reason"])),
        "real_datasets_all_members": len(candidates),
        "real_datasets_series_once": len(candidates) - in_series + len(series),
        "n_series": len(series), "datasets_in_series": in_series,
        "licence_class_all": dict(C(r["licence_class"] for r in rows)),
        "licence_class_candidates": dict(C(r["licence_class"] for r in candidates)),
        "publisher_says_view_but_no_parent": sum(1 for r in candidates if r["primary_or_view"] == "View"),
        "unrecognised_values": dict(C(v for r in rows for v in r["unrecognised_values"].split(";") if v)),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw_dir")
    ap.add_argument("--out", default=str(ROOT / "data/processed/inventory"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    raw_dir = Path(args.raw_dir)
    with gzip.open(raw_dir / "catalog.json.gz", "rt", encoding="utf-8") as f:
        rows = build_inventory(json.load(f))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{raw_dir.name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    summary = {"snapshot": raw_dir.name, **summarise(rows)}
    (out / f"{raw_dir.name}_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    log.info("inventory path=%s %s", out / f"{raw_dir.name}.csv", json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
