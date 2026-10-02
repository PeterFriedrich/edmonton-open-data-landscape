"""Offline guards on the catalogue harvester and the public reduction.

No network: the fetch function is a fake over fixture pages. What they pin:
Socrata pages and caps silently, so a short or shifted listing must fail the
run, not write a smaller snapshot; and the public reduced snapshot must never
carry descriptions (docs/DECISIONS.md, 2026-10-02).
"""
import gzip
import json
import urllib.error

import pytest

from src import harvest as hv
from src import reduce_snapshot as rs


def asset(i, description="Some prose", purpose="Prose purpose"):
    return {
        "resource": {"id": f"id-{i:04d}", "name": f"Asset {i}", "type": "dataset", "provenance": "official",
                     "description": description, "columns_name": ["A"], "columns_field_name": ["a"],
                     "columns_datatype": ["text"], "columns_description": ["col prose"], "parent_fxf": [],
                     "data_updated_at": "2026-09-30T10:38:10.000Z"},
        "classification": {"domain_category": "Transportation", "domain_tags": ["t"],
                           "domain_metadata": [{"key": "Time-Frame_Update-Frequency", "value": "Daily"},
                                               {"key": "General-Information_Purpose", "value": purpose}]},
        "metadata": {"domain": "data.edmonton.ca", "license": "See Terms of Use"},
        "permalink": f"https://data.edmonton.ca/d/id-{i:04d}",
    }


def fake_fetch(assets, reported=None):
    calls = []

    def fetch(url):
        calls.append(url)
        offset = int(url.split("offset=")[1].split("&")[0])
        return {"resultSetSize": len(assets) if reported is None else reported,
                "results": assets[offset:offset + hv.PAGE_SIZE]}
    return fetch, calls


def no_sleep(_):
    pass


def test_harvest_pages_through_whole_listing():
    assets = [asset(i) for i in range(250)]
    fetch, calls = fake_fetch(assets)
    results, stats = hv.harvest(fetch, sleep=no_sleep)
    assert len(results) == 250 and stats["pages"] == 3 and len(calls) == 3
    assert stats["n_unique_ids"] == stats["result_set_size"] == 250


def test_harvest_fails_hard_when_listing_is_short():
    fetch, _ = fake_fetch([asset(i) for i in range(250)], reported=300)
    with pytest.raises(hv.HarvestError, match="250 unique ids, server reports 300"):
        hv.harvest(fetch, sleep=no_sleep)


def test_harvest_fails_hard_on_duplicates_from_shifting_pages():
    assets = [asset(i) for i in range(150)]
    assets[120] = asset(5)  # order shifted between pages: one id seen twice, one never
    fetch, _ = fake_fetch(assets)
    with pytest.raises(hv.HarvestError, match="149 unique ids"):
        hv.harvest(fetch, sleep=no_sleep)


def test_harvest_paces_between_requests():
    slept = []
    fetch, _ = fake_fetch([asset(i) for i in range(250)])
    hv.harvest(fetch, sleep=slept.append)
    assert slept == [hv.PACE_S, hv.PACE_S]


def http_error(code, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError("u", code, "err", headers, None)


def test_retry_honours_retry_after_then_succeeds():
    slept, attempts = [], iter([http_error(429, "30"), {"ok": 1}])

    def fetch(url):
        r = next(attempts)
        if isinstance(r, Exception):
            raise r
        return r
    assert hv.fetch_with_retry(fetch, "u", slept.append) == {"ok": 1}
    assert slept == [30.0]


def test_retry_stops_after_consecutive_failures():
    slept = []

    def fetch(url):
        raise http_error(503)
    with pytest.raises(hv.HarvestError, match="consecutive failures"):
        hv.fetch_with_retry(fetch, "u", slept.append)
    assert len(slept) == hv.MAX_CONSECUTIVE_FAILURES
    assert slept == sorted(slept)  # backs off, never speeds up


def test_client_error_is_not_retried():
    def fetch(url):
        raise http_error(404)
    with pytest.raises(hv.HarvestError, match="HTTP 404"):
        hv.fetch_with_retry(fetch, "u", no_sleep)


def make_raw_snapshot(tmp_path, assets):
    stats = {"n_unique_ids": len(assets)}
    return hv.write_snapshot(tmp_path / "raw", "2026-10-02", assets, {"domain": "data.edmonton.ca", **stats})


def test_write_snapshot_layout_and_no_overwrite(tmp_path):
    snap = make_raw_snapshot(tmp_path, [asset(1)])
    assert sorted(p.name for p in snap.iterdir()) == ["catalog.json.gz", "manifest.json"]
    with pytest.raises(hv.HarvestError, match="refusing to overwrite"):
        make_raw_snapshot(tmp_path, [asset(1)])


def all_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from all_keys(v)


def test_reduced_snapshot_carries_no_descriptions(tmp_path):
    raw = make_raw_snapshot(tmp_path, [asset(i, description="SECRET-PROSE", purpose="SECRET-PURPOSE")
                                       for i in range(3)])
    out = rs.reduce_snapshot(raw, tmp_path / "public")
    text = gzip.decompress((out / "catalog_reduced.json.gz").read_bytes()).decode()
    reduced = json.loads(text)
    assert not [k for k in all_keys(reduced) if "description" in k.lower()]
    assert "SECRET" not in text
    assert reduced[0]["custom_fields"] == {"Time-Frame_Update-Frequency": "Daily"}
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["dropped_custom_fields"] == {"General-Information_Purpose": 3}  # dropped, but counted


def test_reduced_snapshot_keeps_every_asset(tmp_path):
    raw = make_raw_snapshot(tmp_path, [asset(i) for i in range(5)])
    manifest = json.loads((raw / "manifest.json").read_text())
    manifest["n_unique_ids"] = 6
    (raw / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(RuntimeError, match="5 reduced assets vs 6"):
        rs.reduce_snapshot(raw, tmp_path / "public")
