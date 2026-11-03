"""Guards on programme detection (`src/programmes.py`).

A family needs enough units sharing ONE kind of evidence; a group just short of
the threshold is reported, not silently dropped. Families never chain: a unit
in two families is listed in both and flagged, and every unit comes out,
including those with no programme.
"""
from src import programmes as prog


def asset(id_, name, fields=("a",), purpose=None, tags=()):
    meta = [{"key": prog.PURPOSE_KEY, "value": purpose}] if purpose else []
    return {
        "resource": {"id": id_, "name": name, "description": "",
                     "columns_field_name": list(fields), "columns_datatype": ["Text"] * len(fields)},
        "classification": {"domain_tags": list(tags), "domain_metadata": meta},
    }


def inv_row(id_, name):
    return {"id": id_, "name": name, "role": "candidate", "series_key": "",
            "category": "Surveys", "data_updated_at": "2026-01-01"}


def run(assets):
    inventory = [inv_row(a["resource"]["id"], a["resource"]["name"]) for a in assets]
    return prog.detect(assets, inventory)


def survey_panel():
    return [asset(f"s{i}", f"Topic {i} Survey - Edmonton Insight Community", fields=(f"q{i}",),
                  tags=["insight community"]) for i in range(5)]


def test_shared_title_suffix_forms_one_family():
    assignments, families, _ = run(survey_panel() + [asset("x", "Trees", fields=("species",))])
    keys = {a["unit"]: a["programme_key"] for a in assignments}
    assert {keys[f"s{i}"] for i in range(5)} == {"suffix:edmonton insight community"}
    assert keys["x"] == ""
    assert [(f["evidence"], f["n_units"], f["common_tags"]) for f in families] == \
        [("suffix", 5, "insight community")]


def test_group_under_the_threshold_is_reported_not_a_family():
    assets = [asset(f"p{i}", f"Report {i}", fields=(f"c{i}",), purpose="To promote transparency")
              for i in range(prog.MIN_UNITS["purpose"] - 1)]
    assignments, families, summary = run(assets)
    assert families == []
    assert all(a["programme_key"] == "" for a in assignments)
    [near] = summary["near_threshold"]
    assert (near["evidence"], near["n_units"], near["label"]) == ("purpose", 3, "to promote transparency")
    assert near["key"].startswith("purpose:") and near["units"] == ["p0", "p1", "p2"]


def test_status_suffixes_and_tiny_column_sets_are_not_programmes():
    assets = [asset(f"d{i}", f"Thing {i} - Deprecated", fields=("name",)) for i in range(6)]
    assets += [asset(f"y{i}", f"Thing {i} – 2019", fields=(f"z{i}",)) for i in range(6)]
    _, families, summary = run(assets)
    assert families == [] and summary["near_threshold"] == []


def test_a_tie_goes_to_the_title_suffix():
    # s0..s4 share a suffix AND an identical 3-column set: two 5-unit families.
    assets = [asset(f"s{i}", f"Topic {i} - Edmonton Insight Community", fields=("a", "b", "c"))
              for i in range(5)]
    assignments, families, _ = run(assets)
    assert sorted(f["evidence"] for f in families) == ["columns", "suffix"]
    assert {a["programme_key"] for a in assignments} == {"suffix:edmonton insight community"}


def test_unit_in_two_families_is_flagged_and_families_do_not_chain():
    # s0..s4 share a suffix; s4 and m0..m2 share a purpose. Chaining would make one
    # family of 8; the purpose family must hold its own 4 and s4 must be flagged.
    assets = survey_panel()
    assets[4] = asset("s4", "Topic 4 Survey - Edmonton Insight Community", fields=("q4",),
                      purpose="Monthly survey results")
    assets += [asset(f"m{i}", f"Monthly {i}", fields=(f"m{i}",), purpose="Monthly survey results")
               for i in range(3)]
    assignments, families, summary = run(assets)
    sizes = {f["evidence"]: f["n_units"] for f in families}
    assert sizes == {"suffix": 5, "purpose": 4}
    s4 = next(a for a in assignments if a["unit"] == "s4")
    assert s4["programme_key"] == "suffix:edmonton insight community"
    assert s4["also_in"].startswith("purpose:")
    assert summary["n_in_several"] == 1
    assert summary["overlaps"][0]["shared_units"] == 1
    assert {a["programme_key"] for a in assignments if a["unit"].startswith("m")} == {s4["also_in"]}


def test_every_unit_comes_out():
    assets = survey_panel() + [asset(f"x{i}", f"Other {i}", fields=(f"o{i}",)) for i in range(4)]
    assignments, _, summary = run(assets)
    assert sorted(a["unit"] for a in assignments) == sorted(a["resource"]["id"] for a in assets)
    assert summary["n_with_programme"] + summary["n_without_programme"] == summary["n_units"] == 9
