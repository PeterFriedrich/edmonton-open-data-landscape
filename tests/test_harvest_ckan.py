"""Offline guards on the open.alberta.ca (CKAN) harvester.

No network: the fetch function is a fake over fixture pages. Same contract as
the Socrata harvester (tests/test_harvest.py): a short, shifted or failed
listing fails the run instead of writing a smaller snapshot.
"""
import json
import urllib.parse

import pytest

from src import harvest_ckan as hc
from src.harvest import HarvestError


def package(i):
    return {"id": f"pkg-{i:05d}", "title": f"Package {i}", "type": "opendata", "notes": "Some prose",
            "organization": {"name": "health"}, "resources": []}


def fake_fetch(packages, reported=None, success=True):
    calls = []

    def fetch(url):
        calls.append(url)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        start, rows = int(q["start"][0]), int(q["rows"][0])
        return {"success": success, "result": {"count": len(packages) if reported is None else reported,
                                               "results": packages[start:start + rows]}}
    return fetch, calls


def no_sleep(_):
    pass


def small_pages(monkeypatch, n=100):
    monkeypatch.setattr(hc, "PAGE_SIZE", n)


def test_harvest_pages_through_every_package(monkeypatch):
    small_pages(monkeypatch)
    fetch, calls = fake_fetch([package(i) for i in range(250)])
    results, stats = hc.harvest(fetch, sleep=no_sleep)
    assert len(results) == 250 and stats["pages"] == 3 and len(calls) == 3
    assert stats["n_unique_ids"] == stats["result_set_size"] == 250


def test_harvest_fails_hard_when_listing_is_short(monkeypatch):
    small_pages(monkeypatch)
    fetch, _ = fake_fetch([package(i) for i in range(250)], reported=300)
    with pytest.raises(HarvestError, match="250 unique ids, server reports 300"):
        hc.harvest(fetch, sleep=no_sleep)


def test_harvest_fails_hard_on_duplicates_from_shifting_pages(monkeypatch):
    small_pages(monkeypatch)
    packages = [package(i) for i in range(150)]
    packages[120] = package(5)
    fetch, _ = fake_fetch(packages)
    with pytest.raises(HarvestError, match="149 unique ids"):
        hc.harvest(fetch, sleep=no_sleep)


def test_harvest_fails_when_ckan_reports_failure():
    fetch, _ = fake_fetch([package(1)], success=False)
    with pytest.raises(HarvestError, match="CKAN reported failure"):
        hc.harvest(fetch, sleep=no_sleep)


def test_harvest_fails_when_the_api_reports_nothing():
    fetch, _ = fake_fetch([])
    with pytest.raises(HarvestError, match="below the floor of 1"):
        hc.harvest(fetch, sleep=no_sleep)


def test_pages_ask_for_opendata_in_a_stable_order():
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(hc.page_url(0)).query)
    assert q["fq"] == ["type:opendata"] and q["sort"] == ["id asc"]


def test_main_writes_to_its_own_folder_with_its_own_floor(tmp_path, monkeypatch):
    # An Edmonton snapshot at the root must not set this source's floor.
    (tmp_path / "2026-11-13").mkdir()
    (tmp_path / "2026-11-13/manifest.json").write_text(json.dumps({"n_unique_ids": 2095}))
    fetch, _ = fake_fetch([package(i) for i in range(3)])
    monkeypatch.setattr(hc, "http_get_json", fetch)
    hc.main(["--out", str(tmp_path), "--date", "2026-11-17"])
    manifest = json.loads((tmp_path / "alberta/2026-11-17/manifest.json").read_text())
    assert manifest["n_unique_ids"] == 3 and manifest["filter"] == "type:opendata"
    assert not (tmp_path / "2026-11-17").exists()


def test_main_refuses_existing_snapshot_before_any_request(tmp_path, monkeypatch):
    (tmp_path / "alberta/2026-11-17").mkdir(parents=True)

    def no_network(*a, **k):
        raise AssertionError("made a request despite an existing snapshot")
    monkeypatch.setattr(hc, "http_get_json", no_network)
    with pytest.raises(HarvestError, match="refusing to overwrite"):
        hc.main(["--out", str(tmp_path), "--date", "2026-11-17"])
