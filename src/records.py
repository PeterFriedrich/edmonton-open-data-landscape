"""M6: one record format for every catalogue source, and one adapter per platform.

A record is the spec's search record (`docs/SPEC_landscape.md`, Outputs, Search):
`source, id, title, publisher, description, tags, columns, formats, updated, url,
category, n_members`. Each adapter returns `(records, dropped)`, where `dropped`
counts every raw asset that is not a record, by reason, so that
`len(raw) == sum(n_members) + sum(dropped)` holds and nothing vanishes.

Socrata sources reuse Edmonton's inventory and units (series collapse to one
record). Only the inventory's `role`, `series_key`, `category`, name and dates
are read: its `licence_class` and custom fields are Edmonton-specific
(`data/DATA.md`, Calgary) and stay out of the record.
"""
import collections
import gzip
import json
from pathlib import Path

from src.inventory import build_inventory
from src.similarity import build_units, clean_text

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / "data/raw/private-snapshots"

# `subdir` is the source's folder in the private snapshots repo; Edmonton stays at
# the root until the rename. `hidden` publishers are left out of search by default.
SOURCES = {
    "edmonton": {"platform": "socrata", "subdir": "", "domain": "data.edmonton.ca", "hidden": set()},
    "calgary": {"platform": "socrata", "subdir": "calgary", "domain": "data.calgary.ca", "hidden": set()},
    "alberta": {"platform": "ckan", "subdir": "alberta", "domain": "open.alberta.ca",
                "hidden": {"Alberta Energy Regulator"}},
}


def snapshot_dirs(source):
    base = SNAPSHOTS / SOURCES[source]["subdir"]
    return sorted(p for p in base.iterdir() if (p / "catalog.json.gz").exists()) if base.is_dir() else []


def load_raw(snap):
    with gzip.open(Path(snap) / "catalog.json.gz", "rt", encoding="utf-8") as f:
        return json.load(f)


def socrata_records(raw, source):
    # build_units expects the inventory CSV's string values.
    inv = [{k: "" if v is None else str(v) for k, v in r.items()} for r in build_inventory(raw)]
    by_id = {a["resource"]["id"]: a for a in raw}
    dropped = collections.Counter(r["exclusion_reason"] for r in inv if r["role"] != "candidate")
    records = []
    for u in build_units(raw, inv):
        a = by_id[u["representative_id"]]
        res = a["resource"]
        records.append({
            "source": source, "id": res["id"], "title": res["name"],
            "publisher": (res.get("attribution") or "").strip(),
            "description": res.get("description") or "",
            "tags": list(a["classification"].get("domain_tags") or []),
            "columns": u["fields"], "formats": [],
            "updated": res.get("data_updated_at") or "",
            "url": a.get("permalink") or f"https://{SOURCES[source]['domain']}/d/{res['id']}",
            "category": u["category"], "n_members": u["n_members"],
        })
    return records, dropped


def ckan_records(raw, source):
    dropped, records = collections.Counter(), []
    for p in raw:
        if p.get("state") != "active" or p.get("private"):
            dropped[f"state:{p.get('state')}" + (":private" if p.get("private") else "")] += 1
            continue
        records.append({
            "source": source, "id": p["id"], "title": p["title"],
            "publisher": (p.get("organization") or {}).get("title") or "",
            "description": p.get("notes") or "",
            "tags": [t["display_name"] for t in p.get("tags") or []],
            "columns": [],  # CKAN packages carry no column schemas
            "formats": sorted({r["format"] for r in p.get("resources") or [] if r.get("format")}),
            "updated": p.get("metadata_modified") or "",
            "url": f"https://{SOURCES[source]['domain']}/opendata/{p['name']}",
            "category": "; ".join(p.get("topic") or []), "n_members": 1,
        })
    return records, dropped


ADAPTERS = {"socrata": socrata_records, "ckan": ckan_records}


def build_records(raw, source):
    records, dropped = ADAPTERS[SOURCES[source]["platform"]](raw, source)
    accounted = sum(r["n_members"] for r in records) + sum(dropped.values())
    if accounted != len(raw):
        raise RuntimeError(f"{source}: {len(raw)} raw assets but {accounted} accounted for")
    return records, dict(dropped)


def search_text(r):
    """The text a record is ranked on. For Socrata this equals the M3a unit text
    plus column names, so Edmonton's rankings are unchanged by M6."""
    text = clean_text(" ".join([r["title"], " ".join(r["tags"]), r["description"]]))
    return text + " " + " ".join(c.replace("_", " ") for c in r["columns"])
