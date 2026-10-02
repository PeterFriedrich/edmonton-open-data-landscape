"""Make the PUBLIC reduced copy of a raw catalogue snapshot.

The raw snapshot stays in the private repo (docs/DECISIONS.md, 2026-10-02):
anything whose licence status is uncertain (descriptions, free-text purpose)
is kept out of this public repo. An ALLOW-list, not a deny-list, so a field
Socrata adds later stays private until someone decides otherwise. Custom-field
keys outside the allow-list are dropped and counted in the reduced manifest.

    python -m src.reduce_snapshot RAW_SNAPSHOT_DIR [--out DIR]
"""
import argparse
import collections
import gzip
import json
import logging
import sys
from pathlib import Path

log = logging.getLogger("reduce_snapshot")

ROOT = Path(__file__).resolve().parents[1]

RESOURCE_KEYS = (
    "id", "name", "type", "provenance", "attribution", "createdAt", "updatedAt",
    "data_updated_at", "metadata_updated_at", "publication_date", "parent_fxf",
    "columns_name", "columns_field_name", "columns_datatype", "download_count",
)
CLASSIFICATION_KEYS = ("domain_category", "domain_tags")
CUSTOM_FIELD_KEYS = {
    "Time-Frame_Update-Frequency", "Time-Frame_Automated-or-Manual", "Time-Frame_Period-of-Coverage",
    "General-Information_Internal-or-External", "General-Information_Primary-Dataset-or-View",
    "Quality-Indicators_Duplicates-Removed", "Quality-Indicators_Verified-for-Accuracy",
    "Spatial_Datum", "Spatial_Coordinate-System",
}


def reduce_asset(asset, dropped):
    res, cls = asset["resource"], asset.get("classification", {})
    out = {k: res.get(k) for k in RESOURCE_KEYS}
    out.update({k: cls.get(k) for k in CLASSIFICATION_KEYS})
    custom = {}
    for m in cls.get("domain_metadata") or []:
        if m["key"] in CUSTOM_FIELD_KEYS:
            custom[m["key"]] = m["value"]
        else:
            dropped[m["key"]] += 1
    out["custom_fields"] = custom
    out["license"] = (asset.get("metadata") or {}).get("license")
    out["permalink"] = asset.get("permalink")
    return out


def reduce_snapshot(raw_dir, out_root):
    raw_dir = Path(raw_dir)
    with gzip.open(raw_dir / "catalog.json.gz", "rt", encoding="utf-8") as f:
        raw = json.load(f)
    raw_manifest = json.loads((raw_dir / "manifest.json").read_text())
    dropped = collections.Counter()
    reduced = sorted((reduce_asset(a, dropped) for a in raw), key=lambda a: a["id"])
    if len(reduced) != raw_manifest["n_unique_ids"]:
        raise RuntimeError(f"{len(reduced)} reduced assets vs {raw_manifest['n_unique_ids']} in raw manifest")

    out = Path(out_root) / raw_dir.name
    if out.exists():
        raise RuntimeError(f"{out} already exists; refusing to overwrite")
    out.mkdir(parents=True)
    with gzip.open(out / "catalog_reduced.json.gz", "wt", encoding="utf-8") as f:
        json.dump(reduced, f, ensure_ascii=False)
    manifest = {
        "reduced_from": {k: raw_manifest.get(k) for k in
                         ("retrieved_started_utc", "retrieved_finished_utc", "domain", "code_sha", "n_unique_ids")},
        "n_assets": len(reduced),
        "kept_resource_keys": list(RESOURCE_KEYS), "kept_custom_fields": sorted(CUSTOM_FIELD_KEYS),
        "dropped_custom_fields": dict(sorted(dropped.items())),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    log.info("reduced path=%s assets=%d dropped_custom_fields=%s", out, len(reduced), dict(dropped))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw_dir")
    ap.add_argument("--out", default=str(ROOT / "data/snapshots"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    reduce_snapshot(args.raw_dir, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
