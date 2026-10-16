"""Guards on the M4 layout (`src/layout.py`).

The map must stay still from week to week: a fresh t-SNE moved it a median
5.5-9.2% of its extent, so a normal week is warm-started and gated. A new topic
and a re-anchor are allowed to move it, but must say so.
"""
import numpy as np
import pytest

from src import layout as lay
from src.clustering import distances


def blobs(n_blobs=8, size=40, dim=30, seed=0):
    """Units in loose groups; distance = 1 - cosine similarity. Tighter or smaller
    groups make t-SNE's within-group placement arbitrary, so a warm week moves
    more than on the real matrices (1.0-1.4% median there, p95 <= 2.1%)."""
    rng = np.random.default_rng(seed)
    centres = rng.normal(size=(n_blobs, dim))
    X = np.repeat(centres, size, axis=0) + rng.normal(scale=0.8, size=(n_blobs * size, dim))
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    S = np.clip(X @ X.T, 0, 1)
    np.fill_diagonal(S, 0)
    units = [f"g{i // size}-{i % size}" for i in range(len(X))]
    return units, distances(S)


def week(units, D, keep, prev=None, anchor=None, date="2026-10-02", **kw):
    idx = [i for i, u in enumerate(units) if u in keep]
    rows, summary = lay.run([units[i] for i in idx], D[np.ix_(idx, idx)], prev, anchor, date, **kw)
    return {"coords": {r["unit"]: (r["x"], r["y"]) for r in rows}, "summary": summary}, rows


def test_warm_week_with_scattered_arrivals_stays_within_the_gate():
    units, D = blobs()
    rng = np.random.default_rng(1)
    arrivals = set(rng.choice(units, 10, replace=False))
    w1, _ = week(units, D, set(units) - arrivals)
    w2, rows = week(units, D, set(units), prev=w1, anchor=w1["coords"], date="2026-10-09")
    s = w2["summary"]
    assert s["mode"] == "warm" and s["epoch"] == 1
    assert s["move_median"] <= lay.GATE_MEDIAN and s["move_p95"] <= lay.GATE_P95
    assert sorted(s["new"]) == sorted(arrivals)
    assert {r["unit"] for r in rows if r["is_new"]} == arrivals


def test_new_units_start_at_the_median_of_their_nearest_kept_units():
    kept_xy = np.array([[0, 0], [1, 0], [2, 0], [3, 0], [4, 0], [100, 100]], dtype=float)
    D = np.array([[0.1, 0.2, 0.3, 0.4, 0.5, 0.9]])
    assert lay.place(D, kept_xy).tolist() == [[2.0, 0.0]]


def test_removed_units_are_reported_not_dropped_silently():
    units, D = blobs()
    w1, _ = week(units, D, set(units))
    gone = {units[0], units[50]}
    w2, rows = week(units, D, set(units) - gone, prev=w1, anchor=w1["coords"], date="2026-10-09")
    assert w2["summary"]["removed"] == sorted(gone)
    assert len(rows) == len(units) - 2


def test_a_whole_new_group_is_flagged_and_runs_longer():
    units, D = blobs()
    group = {u for u in units if u.startswith("g7-")}
    w1, _ = week(units, D, set(units) - group)
    w2, _ = week(units, D, set(units), prev=w1, anchor=w1["coords"], date="2026-10-09")
    s = w2["summary"]
    assert s["mode"] == "new_topic"
    assert set(s["new_topic_units"]) <= group and len(s["new_topic_units"]) > len(group) / 2
    assert not s["gate"]["applies"]


@pytest.mark.parametrize("prev_summary, reason", [
    ({"drift_median": lay.REANCHOR_DRIFT + 1}, "drift"),
    ({"anchor_date": "2026-07-01"}, "days old"),
])
def test_reanchor_when_drift_or_age_is_due(prev_summary, reason):
    units, D = blobs(n_blobs=4, size=20)
    w1, _ = week(units, D, set(units))
    w1["summary"].update(prev_summary)
    w2, rows = week(units, D, set(units), prev=w1, date="2026-10-09")
    s = w2["summary"]
    assert s["mode"] == "anchor" and s["epoch"] == 2 and s["anchor_date"] == "2026-10-09"
    assert any(reason in r for r in s["anchor_reasons"])
    assert {r["epoch"] for r in rows} == {2}


def test_a_warm_week_that_moves_too_much_fails_loudly(monkeypatch):
    units, D = blobs(n_blobs=4, size=20)
    w1, _ = week(units, D, set(units))
    monkeypatch.setattr(lay, "GATE_MEDIAN", 0.0)
    with pytest.raises(lay.GateFailed):
        week(units, D, set(units), prev=w1, anchor=w1["coords"], date="2026-10-09")
