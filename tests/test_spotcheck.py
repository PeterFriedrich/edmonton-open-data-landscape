"""Guards on the M3c neighbour spot-check (`src/spotcheck.py`).

A neighbour found by both signals is ONE pair carrying both ranks, so a label
counts toward both signals' precision. `unsure` counts as a miss in the headline
precision and is dropped in the second bound (DECISIONS 2026-11-20); the gate is
judged on units outside programmes only and never passes while a pair in its
scope is unlabelled. A label for a pair outside the sample is an error. Extending
with a later signal must keep every existing pair id, so labels stay attached.
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


def pair(pid, u, stratum="category:Transit", **ranks):
    p = {"pair_id": pid, "unit": u, "stratum": stratum,
         "text_rank": "", "schema_rank": "", "embed_rank": ""}
    p.update({f"{k}_rank": v for k, v in ranks.items()})
    return p


def lab(*pv):
    return [{"pair_id": p, "verdict": v} for p, v in pv]


def test_unsure_is_a_miss_in_the_headline_and_dropped_in_the_second_bound():
    pairs = [pair("p001", "a", text=1, schema=1), pair("p002", "a", text=2),
             pair("p003", "a", text=3, schema=2), pair("p004", "a", text=4)]
    out = sc.score(pairs, lab(("p001", "yes"), ("p002", "no"), ("p003", "unsure")), {"a": ""})
    t = out["signals"]["text"]
    assert (t["labelled"], t["yes"], t["no"], t["unsure"], t["unlabelled"]) == (3, 1, 1, 1, 1)
    assert t["precision"] == 0.333 and t["precision_unsure_dropped"] == 0.5
    s = out["signals"]["schema"]
    assert s["precision"] == 0.5 and s["precision_unsure_dropped"] == 1.0
    assert "judged" not in t  # it meant yes + no; removed rather than redefined


def test_a_unit_whose_labels_are_all_unsure_has_no_good_neighbour():
    pairs = [pair("p001", "a", text=1), pair("p002", "a", text=2), pair("p003", "b", text=1)]
    t = sc.score(pairs, lab(("p001", "unsure"), ("p002", "unsure"), ("p003", "yes")),
                 {"a": "", "b": ""})["signals"]["text"]
    assert t["units_with_no_good_neighbour"] == 1 and t["units_all_unsure"] == 1
    assert t["precision_unsure_dropped"] == 1.0


def test_a_partly_labelled_unit_is_not_yet_one_with_no_good_neighbour():
    pairs = [pair("p001", "a", text=1), pair("p002", "a", text=2)]
    t = sc.score(pairs, lab(("p001", "no")), {"a": ""})["signals"]["text"]
    assert (t["units_partly_labelled"], t["units_with_no_good_neighbour"]) == (1, 0)
    t = sc.score(pairs, lab(("p001", "no"), ("p002", "no")), {"a": ""})["signals"]["text"]
    assert (t["units_partly_labelled"], t["units_with_no_good_neighbour"]) == (0, 1)


def test_the_gate_says_no_pairs_when_a_signal_has_none_in_scope():
    pairs = [pair("p001", "a", text=1)]
    out = sc.score(pairs, lab(("p001", "yes")), {"a": ""})
    assert out["outside_programmes"]["schema"]["gate"] == {"status": "no_pairs"}
    assert out["outside_programmes"]["text"]["gate"] == {"status": "pass"}


def test_a_unit_with_no_neighbours_from_a_signal_is_not_a_unit_with_no_good_one():
    pairs = [pair("p001", "a", text=1), pair("p002", "b", text=1, schema=1)]
    s = sc.score(pairs, lab(("p001", "yes"), ("p002", "yes")), {"a": "", "b": ""})["signals"]["schema"]
    assert (s["units"], s["units_with_no_neighbours"], s["units_with_no_good_neighbour"]) == (2, 1, 0)


def gate_case(n_yes, n_miss, n_units_no_good):
    """Units outside programmes: n_units_no_good units with one "no" each, the rest of
    the misses as "unsure" on a unit that also has a yes, and one programme unit with
    only "no" labels, which the gate must not see."""
    pairs, labels, programmes, i = [], [], {"prog": "suffix:x"}, 0

    def add(u, verdict):
        nonlocal i
        i += 1
        pairs.append(pair(f"p{i:03d}", u, text=1))
        labels.append({"pair_id": f"p{i:03d}", "verdict": verdict})
        programmes[u] = programmes.get(u, "")
    for k in range(n_units_no_good):
        add(f"bad{k}", "no")
    for _ in range(n_yes):
        add("good", "yes")
    for _ in range(n_miss - n_units_no_good):
        add("good", "unsure")
    for _ in range(5):
        add("prog", "no")
    programmes["prog"] = "suffix:x"
    return pairs, labels, programmes


@pytest.mark.parametrize("n_yes,n_miss,n_bad,status", [
    (7, 3, 3, "pass"),   # 70% and 3 units: both at the limit
    (69, 31, 3, "fail"),  # 69%
    (8, 4, 4, "fail"),   # 67% and 4 units
    (96, 4, 4, "fail"),  # 96% but 4 units with no good neighbour
])
def test_gate_on_units_outside_programmes_at_70_percent_and_3_units(n_yes, n_miss, n_bad, status):
    pairs, labels, programmes = gate_case(n_yes, n_miss, n_bad)
    out = sc.score(pairs, labels, programmes)
    assert (out["gate"]["min_precision"], out["gate"]["max_units_no_good"]) == (0.70, 3)
    assert out["outside_programmes"]["text"]["gate"]["status"] == status
    assert out["in_programmes"]["text"]["gate"]["status"] == "pending_redraw"
    assert out["in_programmes"]["text"]["no"] == 5


def test_gate_is_incomplete_while_a_pair_in_scope_is_unlabelled():
    pairs, labels, programmes = gate_case(7, 3, 3)
    pairs.append(pair("p999", "good", text=2))
    g = sc.score(pairs, labels, programmes)["outside_programmes"]["text"]["gate"]
    assert g == {"status": "incomplete", "unlabelled": 1}
    pairs, labels, programmes = gate_case(7, 3, 3)
    pairs.append(pair("p999", "prog", text=2))  # unlabelled, but outside the gate's scope
    assert sc.score(pairs, labels, programmes)["outside_programmes"]["text"]["gate"]["status"] == "pass"


def test_by_stratum_pools_the_one_unit_category_strata():
    pairs = [pair("p001", "a", "category:Transit", text=1), pair("p002", "b", "category:Parks", text=1),
             pair("p003", "c", "Surveys", text=1)]
    out = sc.score(pairs, lab(("p001", "yes"), ("p002", "no")), {"a": "", "b": "", "c": "suffix:x"})
    assert set(out["by_stratum"]) == {"category", "Surveys"}
    assert out["by_stratum"]["category"]["text"]["units"] == 2
    assert out["by_stratum"]["category"]["text"]["precision"] == 0.5


def test_a_unit_missing_from_the_programme_assignments_is_an_error():
    with pytest.raises(ValueError):
        sc.score([pair("p001", "a", text=1)], lab(("p001", "yes")), {})


def test_label_outside_sample_is_an_error():
    with pytest.raises(ValueError):
        sc.score([pair("p001", "a", text=1)], lab(("p999", "yes")), {"a": ""})


def test_extend_keeps_pair_ids_and_appends_new_neighbours():
    units = [unit("a", "A"), unit("b", "B"), unit("c", "C"), unit("d", "D")]
    pairs = [p for p in sc.build_pairs(units, [nb("a", "text", 1, "b")], k=5) if p["unit"] == "a"]
    before = [(p["pair_id"], p["neighbour"]) for p in pairs]
    out = sc.extend([dict(p) for p in pairs], units,
                    [nb("a", "embed", 1, "c"), nb("a", "embed", 2, "b"), nb("a", "embed", 6, "d"),
                     nb("z", "embed", 1, "b")], "embed", k=5)
    assert [(p["pair_id"], p["neighbour"]) for p in out[:len(pairs)]] == before
    assert out[0]["embed_rank"] == 2
    new = out[len(pairs):]
    assert [(p["neighbour"], p["embed_rank"], p["text_rank"]) for p in new] == [("c", 1, "")]
    assert new[0]["pair_id"] == f"p{len(pairs) + 1:03d}"
    with pytest.raises(ValueError):
        sc.extend(out, units, [nb("a", "embed", 1, "c")], "embed")
