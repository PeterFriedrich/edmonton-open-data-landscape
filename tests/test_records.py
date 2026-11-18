"""Guards on the M6 record adapters (`src/records.py`).

The invariant that matters most: every raw asset becomes a record or is counted
with a reason. The rest pin that Socrata records rank on exactly the M3a unit
text (so M6 leaves Edmonton's rankings alone) and that CKAN fields map as stated.
"""
import pytest

from src import records as rec
from src.inventory import build_inventory
from src.similarity import build_units


def asset(id_, name="Bus stops", type_="dataset", parents=(), tags=(), description="Stops <b>list</b>",
          fields=("stop_id", "the_geom"), types=("text", "point"), updated="2026-01-01"):
    return {
        "resource": {"id": id_, "name": name, "type": type_, "parent_fxf": list(parents),
                     "attribution": "City of Edmonton", "description": description,
                     "columns_field_name": list(fields), "columns_datatype": list(types),
                     "data_updated_at": updated},
        "classification": {"domain_category": "Transit", "domain_tags": list(tags), "domain_metadata": []},
        "metadata": {}, "permalink": f"https://data.edmonton.ca/d/{id_}",
    }


def package(id_, state="active", private=False, org="Health", topic=("Health and Wellness",)):
    return {"id": id_, "name": f"pkg-{id_}", "title": f"Title {id_}", "notes": "Notes", "state": state,
            "private": private, "organization": {"title": org}, "topic": list(topic),
            "tags": [{"display_name": "IHDA"}], "metadata_modified": "2024-07-18T19:47:33",
            "resources": [{"format": "XLSX"}, {"format": "CSV"}, {"format": "XLSX"}, {"format": ""}]}


def socrata_fixture():
    return [asset("d1"), asset("m1", type_="map", parents=["d1"]), asset("h1", type_="href"),
            asset("y1", name="Ridership 2023", updated="2024-01-01"),
            asset("y2", name="Ridership 2024", updated="2025-01-01", fields=("route", "riders"))]


def test_every_socrata_asset_is_a_record_or_counted():
    raw = socrata_fixture()
    records, dropped = rec.build_records(raw, "edmonton")
    assert sum(r["n_members"] for r in records) + sum(dropped.values()) == len(raw)
    assert dropped == {"derived:map": 1, "standalone:href": 1}
    series = next(r for r in records if r["n_members"] == 2)
    assert series["id"] == "y2"  # latest member represents the series


def test_every_ckan_package_is_a_record_or_counted():
    raw = [package("a"), package("b", state="deleted"), package("c", private=True)]
    records, dropped = rec.build_records(raw, "alberta")
    assert [r["id"] for r in records] == ["a"]
    assert dropped == {"state:deleted": 1, "state:active:private": 1}


def test_build_records_fails_when_an_adapter_loses_assets(monkeypatch):
    monkeypatch.setitem(rec.ADAPTERS, "ckan", lambda raw, source: ([], {}))
    with pytest.raises(RuntimeError, match="1 raw assets but 0"):
        rec.build_records([package("a")], "alberta")


def test_socrata_search_text_is_the_m3a_unit_text():
    raw = socrata_fixture()
    inv = [{k: "" if v is None else str(v) for k, v in r.items()} for r in build_inventory(raw)]
    units = build_units(raw, inv)
    records, _ = rec.socrata_records(raw, "edmonton")
    assert [rec.search_text(r) for r in records] == [
        u["text"] + " " + " ".join(f.replace("_", " ") for f in u["fields"]) for u in units]


def test_socrata_record_does_not_carry_edmonton_licence_or_custom_fields():
    records, _ = rec.socrata_records(socrata_fixture(), "calgary")
    assert set(records[0]) == {"source", "id", "title", "publisher", "description", "tags", "columns",
                               "formats", "updated", "url", "category", "n_members"}


def test_ckan_record_fields():
    (r,), _ = rec.ckan_records([package("a")], "alberta")
    assert r["url"] == "https://open.alberta.ca/opendata/pkg-a"
    assert r["formats"] == ["CSV", "XLSX"]
    assert r["publisher"] == "Health" and r["category"] == "Health and Wellness" and r["columns"] == []
