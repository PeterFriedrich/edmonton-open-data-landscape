"""Guards on the embedding text variant (`src/embeddings.py`).

Its matrix is compared row by row with M3a's text and schema matrices, so the
units must match units.csv in order; a mismatch must fail, not misalign. The
model is injected, so these tests need no fastembed and no download.
"""
import csv

import numpy as np
import pytest

from src import embeddings as emb


def units(*names):
    return [{"unit": n, "name": n, "category": "C", "text": n, "fields": []} for n in names]


def write_units_csv(path, names):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["unit"])
        w.writeheader()
        w.writerows({"unit": n} for n in names)


def test_unit_order_mismatch_fails(tmp_path):
    write_units_csv(tmp_path / "units.csv", ["a", "b", "c"])
    emb.check_unit_order(units("a", "b", "c"), tmp_path / "units.csv")
    with pytest.raises(RuntimeError):
        emb.check_unit_order(units("a", "c", "b"), tmp_path / "units.csv")


def test_neighbours_follow_cosine_and_skip_self():
    vecs = {"a": [1, 0], "b": [0.9, 0.1], "c": [0, 1]}
    us = units("a", "b", "c")
    other = np.array([[0, .5, .2], [.5, 0, .1], [.2, .1, 0]], dtype=np.float32)
    S, rows, summary = emb.run(us, lambda texts: [vecs[t] for t in texts], other, other, k=2)
    assert np.allclose(np.diag(S), 0)
    first = {r["unit"]: r["neighbour"] for r in rows if r["rank"] == 1}
    assert first == {"a": "b", "b": "a", "c": "b"}
    assert summary["dim"] == 2


def test_main_embeds_in_small_batches(monkeypatch, tmp_path):
    """fastembed's default batch (256) peaked at ~10 GB on Edmonton (2026-11-20) and,
    with the search service, filled the box."""
    import gzip, json, sys, types
    from src import similarity as sim
    from tests.test_similarity import rare_fixture

    raw, inventory = rare_fixture()
    raw_dir = tmp_path / "2026-10-02"
    raw_dir.mkdir()
    with gzip.open(raw_dir / "catalog.json.gz", "wt", encoding="utf-8") as f:
        json.dump(raw, f)
    inv = tmp_path / "inv.csv"
    with open(inv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(inventory[0]))
        w.writeheader()
        w.writerows(inventory)
    monkeypatch.setattr(sim, "ROOT", tmp_path)  # summary records the inventory relative to ROOT
    assert sim.main([str(raw_dir), "--inventory", str(inv), "--out", str(tmp_path / "sim"), "--k", "3"]) == 0

    class FakeModel:
        def __init__(self, *a, **kw):
            pass

        def embed(self, texts, batch_size=256):
            FakeModel.batch_size = batch_size
            return [np.array([len(t), sum(map(ord, t)) % 97, 1.0]) for t in texts]

    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=FakeModel))
    assert emb.main([str(raw_dir), "--inventory", str(inv), "--sim-dir", str(tmp_path / "sim" / raw_dir.name),
                     "--k", "3"]) == 0
    assert FakeModel.batch_size == emb.EMBED_BATCH <= 32
