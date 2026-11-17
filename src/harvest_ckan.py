"""Harvest the open.alberta.ca catalogue (CKAN `package_search`, `opendata`
records only) into a dated raw snapshot.

Same contract as `src/harvest.py`: metadata only, a hard failure unless the
unique ids equal the server's count, a floor of half the last snapshot, and no
overwrite. The raw snapshot holds descriptions, so it goes to the PRIVATE
snapshots repo clone, in its own `alberta/` subfolder. No public reduced copy
yet: nothing from this source is published.

    python -m src.harvest_ckan [--out DIR] [--date YYYY-MM-DD]
"""
import argparse
import collections
import logging
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from src.harvest import (PACE_S, ROOT, USER_AGENT, HarvestError, asset_floor, code_sha,
                         fetch_with_retry, http_get_json, write_snapshot)

log = logging.getLogger("harvest_ckan")

SEARCH_URL = "https://open.alberta.ca/api/3/action/package_search"
# `publications` (34,614 records, almost all PDF) is out of scope (docs/SCOPE.md).
FILTER = "type:opendata"
SUBDIR = "alberta"
PAGE_SIZE = 1000  # CKAN's default cap on `rows`


def page_url(start):
    # Relevance order can shift between requests, as Socrata's did (issue #26).
    q = {"fq": FILTER, "rows": PAGE_SIZE, "start": start, "sort": "id asc"}
    return f"{SEARCH_URL}?{urllib.parse.urlencode(q)}"


def harvest(fetch, sleep=time.sleep, min_assets=1):
    """Page through every matching package. Returns (results, stats); fails on
    a short or shifted listing, as `src.harvest.harvest` does."""
    results, pages, start, expected = [], 0, 0, None
    while True:
        if pages:
            sleep(PACE_S)
        page = fetch_with_retry(fetch, page_url(start), sleep)
        pages += 1
        if not page.get("success"):
            raise HarvestError(f"CKAN reported failure at start={start}: {page.get('error')}")
        size = page["result"]["count"]
        if expected is None:
            expected = size
        elif size != expected:
            raise HarvestError(f"count changed mid-run: {expected} -> {size}")
        batch = page["result"]["results"]
        results.extend(batch)
        log.info("page start=%d got=%d total=%d expected=%d", start, len(batch), len(results), expected)
        start += PAGE_SIZE
        if not batch or start >= expected:
            break
    ids = [r["id"] for r in results]
    unique = len(set(ids))
    stats = {"result_set_size": expected, "n_results": len(results), "n_unique_ids": unique,
             "duplicate_ids": sorted(i for i, n in collections.Counter(ids).items() if n > 1),
             "pages": pages}
    if unique != expected:
        raise HarvestError(f"collected {unique} unique ids, server reports {expected} (stats: {stats})")
    if unique < min_assets:
        raise HarvestError(f"only {unique} assets, below the floor of {min_assets} (stats: {stats})")
    return results, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.environ.get("LANDSCAPE_RAW_SNAPSHOT_DIR",
                                                   str(ROOT / "data/raw/private-snapshots")))
    ap.add_argument("--date", help="snapshot folder name (default: today, UTC)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    out = Path(args.out) / SUBDIR
    started = datetime.now(timezone.utc)
    date = args.date or started.date().isoformat()
    if (out / date).exists():  # fail before spending any requests
        raise HarvestError(f"{out / date} already exists; refusing to overwrite a snapshot")
    results, stats = harvest(http_get_json, min_assets=asset_floor(out, date))
    manifest = {
        "source": SEARCH_URL, "filter": FILTER, "page_size": PAGE_SIZE, "pace_s": PACE_S,
        "retrieved_started_utc": started.isoformat(timespec="seconds"),
        "retrieved_finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user_agent": USER_AGENT, "code_sha": code_sha(), **stats,
    }
    snap = write_snapshot(out, date, results, manifest)
    log.info("snapshot_written path=%s assets=%d", snap, stats["n_unique_ids"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
