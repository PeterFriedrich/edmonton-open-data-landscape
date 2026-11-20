"""Guards on catalogue search (`src/search.py`). Vectors are hand-made or come from
a fake model, so no real model is needed."""
import json
import sys
import types

import numpy as np
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer

from src import records, search


def test_rank_orders_by_combined_score_and_column_names_count():
    units = [{"title": t, "tags": [], "description": "", "columns": f} for t, f in [
        ("road maintenance areas", []),
        ("property assessment", ["neighbourhood_name", "assessed_value"]),
        ("graffiti survey", []),
    ]]
    texts = [records.search_text(u) for u in units]
    tfidf = TfidfVectorizer().fit(texts)
    X = tfidf.transform(texts)
    E = np.eye(3, dtype=np.float32)
    # Embedding favours "road"; TF-IDF on a column name ("neighbourhood") favours "property" enough to win.
    hits = search.rank("neighbourhood assessed value", units, E, np.array([0.6, 0.5, 0], np.float32),
                       tfidf, X, k=2)
    assert [u["title"] for _, u in hits] == ["property assessment", "road maintenance areas"]


class FakeModel:
    calls = []

    def __init__(self, *a, **kw):
        pass

    def embed(self, texts, batch_size=256):
        FakeModel.calls.append(len(texts))
        FakeModel.batch_size = batch_size
        return [np.array([1.0, (hash(t) % 7) + 1.0]) for t in texts]

    def query_embed(self, qs):
        return [np.array([1.0, 1.0]) for _ in qs]


def pkg(i, org):
    return {"id": f"p{i}", "name": f"p{i}", "title": f"Water quality {i}", "notes": "", "state": "active",
            "organization": {"title": org}, "tags": [], "resources": [], "topic": []}


def run(monkeypatch, tmp_path, capsys, *argv):
    FakeModel.calls = []
    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=FakeModel))
    monkeypatch.setattr(search, "CACHE", tmp_path / "cache")
    raws = {"alberta": [pkg(i, "Alberta Energy Regulator" if i < 4 else "Health") for i in range(10)],
            "calgary": []}
    monkeypatch.setattr(search, "snapshot_dirs", lambda s: [tmp_path / s / "2026-11-17"])
    monkeypatch.setattr(search, "load_raw", lambda snap: raws[snap.parent.name])
    assert search.main(["water", "--source", "alberta,calgary", "-k", "3", *argv]) == 0
    return capsys.readouterr().out


def test_hidden_publishers_are_counted_and_k_is_per_source(monkeypatch, tmp_path, capsys):
    out = json.loads(run(monkeypatch, tmp_path, capsys, "--json"))
    assert out["sources"]["alberta"]["n_hidden"] == 4
    assert out["sources"]["alberta"]["n_records"] == 6
    hits = out["queries"][0]["hits"]
    assert len(hits["alberta"]) == 3 and hits["calgary"] == []
    assert all(h["publisher"] == "Health" for h in hits["alberta"])

    shown = json.loads(run(monkeypatch, tmp_path, capsys, "--json", "--include-hidden"))
    assert shown["sources"]["alberta"]["n_hidden"] == 0 and shown["sources"]["alberta"]["n_records"] == 10


def test_text_output_prints_the_hidden_count(monkeypatch, tmp_path, capsys):
    out = run(monkeypatch, tmp_path, capsys)
    assert "4 hidden (Alberta Energy Regulator" in out


def test_cache_reuses_vectors_by_text_hash(monkeypatch, tmp_path, capsys):
    run(monkeypatch, tmp_path, capsys, "--json")
    assert FakeModel.calls == [6]
    run(monkeypatch, tmp_path, capsys, "--json", "--include-hidden")
    assert FakeModel.calls == [4]  # only the 4 newly shown records are embedded


def test_cache_from_another_model_or_torn_write_is_not_reused(monkeypatch, tmp_path, capsys):
    run(monkeypatch, tmp_path, capsys, "--json")
    meta = tmp_path / "cache/alberta/2026-11-17/hashes.json"
    good = json.loads(meta.read_text())
    meta.write_text(json.dumps({**good, "model": "other/model"}))
    run(monkeypatch, tmp_path, capsys, "--json")
    assert FakeModel.calls == [6]
    meta.write_text(json.dumps({**good, "hashes": good["hashes"][:5]}))  # vectors and hashes out of step
    run(monkeypatch, tmp_path, capsys, "--json")
    assert FakeModel.calls == [6]


def test_unharvested_source_is_reported_not_silently_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(search, "snapshot_dirs", lambda s: [])
    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=FakeModel))
    assert search.main(["water", "--source", "calgary", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["sources"]["calgary"] == {"skipped": "no snapshot harvested"}
    assert out["queries"][0]["hits"]["calgary"] == []


def test_empty_source_list_is_an_error():
    with pytest.raises(SystemExit):
        search.parse_sources(" , ")


def test_embedding_uses_the_small_batch(monkeypatch, tmp_path, capsys):
    """fastembed's default batch (256) peaked at 10.2 GB on a cold Edmonton embed (2026-11-20)."""
    run(monkeypatch, tmp_path, capsys)
    assert FakeModel.batch_size == search.EMBED_BATCH <= 32
