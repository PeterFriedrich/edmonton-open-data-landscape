"""Guards on the M3c neighbour spot-check (`src/spotcheck.py`).

A neighbour found by both signals is ONE pair carrying both ranks, so a label
counts toward both signals' precision. `unsure` and unlabelled pairs are counted,
never scored, and a label for a pair outside the sample is an error.
"""
import pytest

from src import spotcheck as sc


def unit(key, category="Transit", members=1):
    return {"unit": key, "name": key.title(), "representative_id": f"id-{key}",
            "category": category, "n_members": str(members)}


def nb(u, signal, rank, v, score=0.5, shared=""):
    return {"unit": u, "signal": signal, "rank": str(rank), "neighbour": v,
            "score": str(score), "shared_fields": shared}


def test_shared_neighbour_is_one_pair_with_both_ranks():
    units = [unit("a", "A"), unit("b", "B"), unit("c", "C")]  # one per category: all sampled
    neighbours = [nb("a", "text", 1, "b"), nb("a", "text", 2, "c"),
                  nb("a", "schema", 1, "b", shared="route_id"), nb("a", "text", 6, "c")]
    pairs = [p for p in sc.build_pairs(units, neighbours, k=5) if p["unit"] == "a"]
    assert len(pairs) == 2
    b = next(p for p in pairs if p["neighbour"] == "b")
    assert (b["text_rank"], b["schema_rank"], b["shared_fields"]) == (1, 1, "route_id")


def test_each_sampled_unit_appears_once_per_stratum():
    units = [unit(f"s{i}", "Surveys") for i in range(5)] + [unit(f"t{i}") for i in range(5)]
    picked = sc.pick_units(units, seed=0)
    keys = [u["unit"] for _, u in picked]
    assert len(keys) == len(set(keys))
    assert sum(1 for s, _ in picked if s == "Surveys") == 2


def test_score_counts_unsure_but_does_not_score_it():
    pairs = [{"pair_id": "p001", "unit": "a", "text_rank": 1, "schema_rank": 1},
             {"pair_id": "p002", "unit": "a", "text_rank": 2, "schema_rank": ""},
             {"pair_id": "p003", "unit": "a", "text_rank": "", "schema_rank": 2}]
    labels = [{"pair_id": "p001", "verdict": "yes"}, {"pair_id": "p002", "verdict": "no"},
              {"pair_id": "p003", "verdict": "unsure"}]
    out = sc.score(pairs, labels)
    assert out["unsure"] == 1
    assert out["signals"]["text"] == {"neighbours": 2, "judged": 2, "precision": 0.5,
                                      "units_with_no_good_neighbour": 0}
    assert out["signals"]["schema"]["judged"] == 1 and out["signals"]["schema"]["precision"] == 1.0


def test_label_outside_sample_is_an_error():
    with pytest.raises(ValueError):
        sc.score([{"pair_id": "p001", "unit": "a", "text_rank": 1, "schema_rank": ""}],
                 [{"pair_id": "p999", "verdict": "yes"}])
