"""M4: 2D map coordinates for the similarity units, kept still from week to week.

t-SNE on 1 - mean(text, schema) similarity. A fresh t-SNE each week would
reshuffle the whole map (median move 5.5-9.2% of map extent, p95 24-37%; measured
2026-10-14, `TODO.md` M4), so a normal week starts from last week's coordinates
instead: new units begin at the median of their nearest kept units, and the run
uses `early_exaggeration=1` (the default 12 cancels the init) for 250 iterations.
The result is Procrustes-aligned onto last week's map.

Three kinds of week:
- `warm`:      the above. Gated: median move <= GATE_MEDIAN, p95 <= GATE_P95.
- `new_topic`: some new unit's top-10 neighbours are mostly other new units. A short
               warm run separates a whole new cluster poorly, so this week runs
               NEW_TOPIC_ITER iterations, moves more, and is flagged for the change log.
- `anchor`:    first week, `--reanchor`, or due (cumulative drift since the last
               anchor > REANCHOR_DRIFT, or the anchor is REANCHOR_DAYS old). A fresh
               run, aligned onto last week, with the epoch bumped.

Writes `data/layout/<date>/` (committed: the next week starts from it, and it holds
only unit ids and numbers, never description text):

- `coords.csv`   unit, x, y, epoch, is_new
- `summary.json` mode, movement, cumulative drift, new and removed unit ids, gate

    python -m src.layout SIMILARITY_DIR [--prev DIR] [--out DIR] [--seed 0] [--reanchor]
"""
import argparse
import csv
import datetime as dt
import json
import logging
import sys
from pathlib import Path

import numpy as np
from scipy.linalg import orthogonal_procrustes
from sklearn.manifold import TSNE

from src.clustering import distances

log = logging.getLogger("layout")

ROOT = Path(__file__).resolve().parents[1]
PERPLEXITY = 30
WARM_ITER = 250
NEW_TOPIC_ITER = 1000
PLACE_K = 5
TOPIC_K = 10
GATE_MEDIAN = 2.5
GATE_P95 = 5.0
REANCHOR_DRIFT = 10.0
REANCHOR_DAYS = 91


class GateFailed(RuntimeError):
    pass


def tsne(D, init, seed, max_iter=1000, warm=False):
    kw = {"early_exaggeration": 1} if warm else {}
    perplexity = min(PERPLEXITY, (len(D) - 1) / 3)
    return TSNE(metric="precomputed", init=init, perplexity=perplexity, random_state=seed,
                max_iter=max_iter, **kw).fit_transform(D)


def place(D_new_kept, kept_xy):
    """Start each new unit at the median position of its PLACE_K nearest kept units."""
    nn = np.argsort(D_new_kept, axis=1)[:, :PLACE_K]
    return np.median(kept_xy[nn], axis=1)


def align(ref, xy, rows=None):
    """Rotate and translate xy so that xy[rows] lies on ref; no scaling."""
    sub = xy if rows is None else xy[rows]
    mr, mx = ref.mean(0), sub.mean(0)
    R, _ = orthogonal_procrustes(sub - mx, ref - mr)
    return (xy - mx) @ R + mr


def movement(ref, xy):
    """Median and p95 move of each row, as % of ref's extent."""
    d = np.linalg.norm(ref - xy, axis=1) / np.ptp(ref, axis=0).max() * 100
    return round(float(np.median(d)), 2), round(float(np.percentile(d, 95)), 2)


def new_topic(D, is_new):
    """New units whose top-TOPIC_K neighbours are mostly other new units."""
    Dn = D[is_new].copy()
    Dn[np.arange(len(Dn)), np.flatnonzero(is_new)] = np.inf
    nn = np.argsort(Dn, axis=1)[:, :TOPIC_K]
    return np.flatnonzero(is_new)[is_new[nn].sum(axis=1) > TOPIC_K / 2]


def run(units, D, prev=None, anchor=None, date=None, seed=0, reanchor=False):
    """Coordinates for `units` (rows of D).

    prev:   last week's {"coords": {unit: (x, y)}, "summary": dict}, or None.
    anchor: the last anchor week's {unit: (x, y)}, for cumulative drift; or None.
    Returns (rows, summary). Raises GateFailed on a warm week that moves too much."""
    n = len(units)
    if prev is None:
        prev_coords, prev_summary = {}, {}
    else:
        prev_coords, prev_summary = prev["coords"], prev["summary"]
    is_new = np.array([u not in prev_coords for u in units])
    kept = np.flatnonzero(~is_new)
    removed = sorted(set(prev_coords) - set(units))
    epoch = prev_summary.get("epoch", 0)
    anchor_date = prev_summary.get("anchor_date")

    due = []
    if prev is None:
        due.append("first week")
    if reanchor:
        due.append("requested")
    if prev_summary.get("drift_median", 0) > REANCHOR_DRIFT:
        due.append(f"drift {prev_summary['drift_median']}% > {REANCHOR_DRIFT}%")
    if anchor_date and date and (dt.date.fromisoformat(date) - dt.date.fromisoformat(anchor_date)).days >= REANCHOR_DAYS:
        due.append(f"anchor {anchor_date} is {REANCHOR_DAYS}+ days old")
    if len(kept) < PLACE_K and prev is not None:
        due.append(f"only {len(kept)} units kept")

    prev_xy = np.array([prev_coords[units[i]] for i in kept]).reshape(-1, 2)
    topic = []
    if due:
        mode = "anchor"
        xy = tsne(D, "random", seed)
        epoch, anchor_date = epoch + 1, date
    else:
        topic = new_topic(D, is_new)
        mode = "new_topic" if len(topic) else "warm"
        init = np.zeros((n, 2), dtype=np.float32)
        init[kept] = prev_xy
        if is_new.any():
            init[is_new] = place(D[np.ix_(is_new, kept)], prev_xy)
        xy = tsne(D, init, seed, NEW_TOPIC_ITER if len(topic) else WARM_ITER, warm=True)

    move = drift = None
    if len(kept) >= 3:
        xy = align(prev_xy, xy, kept)
        move = movement(prev_xy, xy[kept])
    if mode == "anchor":
        drift = (0.0, 0.0)
    elif anchor:
        common = [i for i, u in enumerate(units) if u in anchor]
        if len(common) >= 3:
            ref = np.array([anchor[units[i]] for i in common])
            drift = movement(ref, align(ref, xy[common]))

    summary = {
        "date": date, "mode": mode, "epoch": epoch, "anchor_date": anchor_date, "seed": seed,
        "anchor_reasons": due, "n_units": n, "n_kept": int(len(kept)),
        "new": [units[i] for i in np.flatnonzero(is_new)] if prev is not None else [],
        "removed": removed,
        "new_topic_units": [units[i] for i in topic],
        "move_median": move and move[0], "move_p95": move and move[1],
        "drift_median": drift and drift[0], "drift_p95": drift and drift[1],
        "gate": {"median": GATE_MEDIAN, "p95": GATE_P95, "applies": mode == "warm"},
    }
    if mode == "warm" and move and (move[0] > GATE_MEDIAN or move[1] > GATE_P95):
        raise GateFailed(f"warm week moved median {move[0]}%, p95 {move[1]}% "
                         f"(gate {GATE_MEDIAN}%/{GATE_P95}%); rerun with --reanchor to accept a reshuffle")
    rows = [{"unit": u, "x": round(float(x), 4), "y": round(float(y), 4), "epoch": epoch,
             "is_new": int(bool(is_new[i]) and prev is not None)}
            for i, (u, (x, y)) in enumerate(zip(units, xy))]
    return rows, summary


def read_coords(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["unit"]: (float(r["x"]), float(r["y"])) for r in csv.DictReader(f)}


def latest_before(out_root, date):
    weeks = sorted(p for p in out_root.glob("????-??-??") if p.name < date and (p / "coords.csv").exists())
    return weeks[-1] if weeks else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("similarity_dir")
    ap.add_argument("--prev", help="last week's layout dir (default: newest earlier one under --out)")
    ap.add_argument("--out", default=str(ROOT / "data/layout"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--reanchor", action="store_true", help="fresh layout, epoch bump")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    sim_dir, out_root = Path(args.similarity_dir), Path(args.out)
    date = sim_dir.name
    with open(sim_dir / "units.csv", newline="", encoding="utf-8") as f:
        units = [r["unit"] for r in csv.DictReader(f)]
    S = (np.load(sim_dir / "text_sim.npy").astype(np.float64) + np.load(sim_dir / "schema_sim.npy")) / 2
    D = distances(S)
    if D.shape != (len(units), len(units)):
        raise RuntimeError(f"matrix {D.shape} does not match {len(units)} units")

    prev_dir = Path(args.prev) if args.prev else latest_before(out_root, date)
    prev = anchor = None
    if prev_dir:
        prev = {"coords": read_coords(prev_dir / "coords.csv"),
                "summary": json.loads((prev_dir / "summary.json").read_text())}
        anchor_dir = out_root / str(prev["summary"]["anchor_date"])
        if (anchor_dir / "coords.csv").exists():
            anchor = read_coords(anchor_dir / "coords.csv")
        else:
            log.warning("anchor layout %s missing: cumulative drift not measured", anchor_dir)
    log.info("layout date=%s prev=%s", date, prev_dir)

    try:
        rows, summary = run(units, D, prev, anchor, date, args.seed, args.reanchor)
    except GateFailed as e:
        log.error("layout gate failed date=%s: %s", date, e)
        return 1
    summary["prev"] = prev_dir.name if prev_dir else None
    out = out_root / date
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "coords.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    log.info("layout path=%s %s", out, json.dumps({k: v for k, v in summary.items() if k not in ("new", "removed")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
