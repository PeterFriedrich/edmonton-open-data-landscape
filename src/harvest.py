"""Harvest the data.edmonton.ca catalogue listing (Socrata Discovery API) into a
dated raw snapshot.

Metadata only: no per-asset `/api/views` calls (TODO.md, M1a scope). The raw
snapshot holds descriptions, so it goes to the PRIVATE snapshots repo clone;
`src/reduce_snapshot.py` makes the public copy.

    python -m src.harvest [--out DIR] [--date YYYY-MM-DD]

Env: SOCRATA_APP_TOKEN (optional, sent as X-App-Token),
     LANDSCAPE_RAW_SNAPSHOT_DIR (default data/raw/private-snapshots).
"""
import argparse
import collections
import gzip
import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("harvest")

ROOT = Path(__file__).resolve().parents[1]
DISCOVERY_URL = "https://api.us.socrata.com/api/catalog/v1"
DOMAIN = "data.edmonton.ca"
PAGE_SIZE = 100
PACE_S = 5.0
MAX_CONSECUTIVE_FAILURES = 5
USER_AGENT = "edmonton-open-data-landscape harvester (https://github.com/PeterFriedrich/edmonton-open-data-landscape)"


class HarvestError(RuntimeError):
    pass


def http_get_json(url, token=None, timeout=60):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Accept-Encoding": "gzip"}
    if token:
        headers["X-App-Token"] = token
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    return json.loads(body)


def _retry_after_s(err, attempt):
    """Seconds to wait after a failed request: the server's Retry-After if it
    sent one, else exponential backoff from the base pace."""
    header = getattr(err, "headers", None) and err.headers.get("Retry-After")
    if header and header.isdigit():
        return float(header)
    return PACE_S * 2 ** attempt


def fetch_with_retry(fetch, url, sleep):
    for attempt in range(MAX_CONSECUTIVE_FAILURES):
        try:
            return fetch(url)
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise HarvestError(f"HTTP {e.code} for {url}") from e
            err = e
        except (urllib.error.URLError, TimeoutError) as e:
            err = e
        wait = _retry_after_s(err, attempt)
        log.warning("request_failed url=%s attempt=%d error=%s wait_s=%.0f", url, attempt + 1, err, wait)
        sleep(wait)
    raise HarvestError(f"{MAX_CONSECUTIVE_FAILURES} consecutive failures for {url}; stopping")


def page_url(offset):
    # The default order is relevance, which is not stable across requests: on
    # 2026-10-09 one id came back on two pages and another on none (issue #26).
    q = {"domains": DOMAIN, "limit": PAGE_SIZE, "offset": offset, "order": "dataset_id"}
    return f"{DISCOVERY_URL}?{urllib.parse.urlencode(q)}"


def harvest(fetch, sleep=time.sleep):
    """Page through the whole listing. Returns (results, stats).

    Socrata caps and pages silently, so the run fails hard unless the unique
    ids collected equal the server's resultSetSize."""
    results, pages, offset, expected = [], 0, 0, None
    while True:
        if pages:
            sleep(PACE_S)
        page = fetch_with_retry(fetch, page_url(offset), sleep)
        pages += 1
        size = page["resultSetSize"]
        if expected is None:
            expected = size
        elif size != expected:
            raise HarvestError(f"resultSetSize changed mid-run: {expected} -> {size}")
        batch = page["results"]
        results.extend(batch)
        log.info("page offset=%d got=%d total=%d expected=%d", offset, len(batch), len(results), expected)
        offset += PAGE_SIZE
        if not batch or offset >= expected:
            break
    ids = [r["resource"]["id"] for r in results]
    unique = len(set(ids))
    stats = {"result_set_size": expected, "n_results": len(results), "n_unique_ids": unique,
             "duplicate_ids": sorted(i for i, n in collections.Counter(ids).items() if n > 1),
             "pages": pages}
    if unique != expected:
        raise HarvestError(f"collected {unique} unique ids, server reports {expected} (stats: {stats})")
    return results, stats


def code_sha():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def write_snapshot(out_root, date, results, manifest):
    snap = Path(out_root) / date
    if snap.exists():
        raise HarvestError(f"{snap} already exists; refusing to overwrite a snapshot")
    tmp = snap.with_name(snap.name + ".partial")
    tmp.mkdir(parents=True)
    with gzip.open(tmp / "catalog.json.gz", "wt", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
    (tmp / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    tmp.rename(snap)
    return snap


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=os.environ.get("LANDSCAPE_RAW_SNAPSHOT_DIR",
                                                   str(ROOT / "data/raw/private-snapshots")))
    ap.add_argument("--date", help="snapshot folder name (default: today, UTC)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    token = os.environ.get("SOCRATA_APP_TOKEN") or None
    started = datetime.now(timezone.utc)
    date = args.date or started.date().isoformat()
    if (Path(args.out) / date).exists():  # fail before spending any requests
        raise HarvestError(f"{Path(args.out) / date} already exists; refusing to overwrite a snapshot")
    results, stats = harvest(lambda url: http_get_json(url, token))
    manifest = {
        "source": DISCOVERY_URL, "domain": DOMAIN, "page_size": PAGE_SIZE, "pace_s": PACE_S,
        "retrieved_started_utc": started.isoformat(timespec="seconds"),
        "retrieved_finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "app_token_used": bool(token), "user_agent": USER_AGENT, "code_sha": code_sha(), **stats,
    }
    snap = write_snapshot(args.out, date, results, manifest)
    log.info("snapshot_written path=%s assets=%d", snap, stats["n_unique_ids"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
