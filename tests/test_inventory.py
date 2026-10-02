"""Guards on the M1c inventory (`src/inventory.py`).

The invariant that matters most: every asset in the snapshot comes out as
exactly one row with a role. Excluded assets carry a reason; series members
are grouped, never merged away. The rest pin each classification rule against
a minimal fixture, so a rule that quietly stops matching fails here.
"""
import pytest

from src import inventory as inv


def asset(id_, name="X", type_="dataset", parents=(), category="Transportation",
          attribution="City of Edmonton", licence="See Terms of Use", description="", custom=()):
    return {
        "resource": {"id": id_, "name": name, "type": type_, "parent_fxf": list(parents),
                     "attribution": attribution, "description": description,
                     "columns_field_name": ["a"], "provenance": "official"},
        "classification": {"domain_category": category,
                           "domain_metadata": [{"key": k, "value": v} for k, v in custom]},
        "metadata": {"license": licence},
    }


def by_id(rows):
    return {r["id"]: r for r in rows}


def test_every_asset_is_one_row_with_a_role():
    raw = [asset("d1"), asset("m1", type_="map", parents=["d1"]), asset("h1", type_="href"),
           asset("s1", type_="story", parents=["gone"])]
    rows = inv.build_inventory(raw)
    assert len(rows) == len(raw)
    assert all(r["role"] in {"candidate", "derived", "non_tabular"} for r in rows)
    assert all(r["exclusion_reason"] for r in rows if r["role"] != "candidate")


def test_roles_and_missing_parents():
    rows = by_id(inv.build_inventory([
        asset("d1"), asset("f1", type_="filter", parents=["d1"]),
        asset("s1", type_="story", parents=["gone"]), asset("x1", type_="file")]))
    assert rows["d1"]["role"] == "candidate"
    assert rows["f1"]["exclusion_reason"] == "derived:filter"
    assert rows["s1"]["exclusion_reason"] == "derived:story:parent_missing"
    assert rows["s1"]["parent_missing"] == "gone"
    assert rows["x1"]["exclusion_reason"] == "standalone:file"


def test_series_grouped_within_category_not_merged():
    rows = by_id(inv.build_inventory([
        asset("a", "Speed Check Sign - DFS041", category="Vehicle Speed"),
        asset("b", "Speed Check Sign - DFS102", category="Vehicle Speed"),
        asset("c", "Speed Check Sign - DFS103", category="Other"),  # same stem, other category
        asset("d", "Something Else")]))
    assert rows["a"]["series_key"] == rows["b"]["series_key"] != ""
    assert rows["a"]["series_size"] == 2
    assert rows["c"]["series_key"] == "" and rows["d"]["series_key"] == ""
    summary = inv.summarise(list(rows.values()))
    assert summary["real_datasets_all_members"] == 4
    assert summary["real_datasets_series_once"] == 3


def test_custom_fields_normalised_and_unknown_flagged():
    rows = inv.build_inventory([asset("a", custom=[
        ("General-Information_Internal-or-External", "Internally Sourced Data "),
        ("Time-Frame_Update-Frequency", "Annual"),
        ("Time-Frame_Automated-or-Manual", "Sometimes")])])
    r = rows[0]
    assert r["internal_or_external"] == "Internal"
    assert r["update_frequency"] == "Annually"
    assert r["automated_or_manual"] == "Sometimes"
    assert r["unrecognised_values"] == "automated_or_manual=Sometimes"


@pytest.mark.parametrize("kwargs, signal", [
    ({"attribution": "Statistics Canada"}, "attribution=non_city"),
    ({"category": "Externally Sourced Datasets"}, "category=external"),
    ({"licence": "Canada Open Government Licence"}, "licence_field=Canada Open Government Licence"),
    ({"description": "Use is subject to the Open Government Licence - Alberta"}, "description=licence_phrase"),
    ({"custom": [("General-Information_Internal-or-External", "External")]}, "internal_or_external=External"),
])
def test_third_party_signals(kwargs, signal):
    r = inv.build_inventory([asset("a", **kwargs)])[0]
    assert r["licence_class"] == "third_party"
    assert signal in r["licence_signals"].split(";")


@pytest.mark.parametrize("description", [
    "A list of businesses with a valid licence to operate in Edmonton.",
    "You are free to use it as per our Terms of Use found on data.edmonton.ca.",
])
def test_city_wording_is_not_a_third_party_signal(description):
    r = inv.build_inventory([asset("a", description=description)])[0]
    assert r["licence_class"] == "city"


def test_unknown_when_no_evidence_either_way():
    r = inv.build_inventory([asset("a", attribution=None)])[0]
    assert r["licence_class"] == "unknown"
