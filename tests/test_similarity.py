"""Guards on the M3a similarity signals (`src/similarity.py`).

Every real dataset must land in exactly one unit (series collapse, nothing
dropped), and a unit a signal can't place must be flagged, not left out. The
schema signal must ignore columns that only say "has a location"; with them in,
every mapped dataset looked alike.
"""
import numpy as np

from src import similarity as sim


def asset(id_, name, fields, types=None, tags=(), description=""):
    return {
        "resource": {"id": id_, "name": name, "description": description,
                     "columns_field_name": list(fields),
                     "columns_datatype": list(types or ["Text"] * len(fields))},
        "classification": {"domain_tags": list(tags)},
    }


def inv_row(id_, name, role="candidate", series_key="", category="Transit", updated="2026-01-01"):
    return {"id": id_, "name": name, "role": role, "series_key": series_key,
            "category": category, "data_updated_at": updated}


def fixture():
    raw = [
        asset("bus1", "Bus stops", ["stop_id", "stop_name", "route_id"], tags=["transit", "bus"],
              description="Transit bus stop locations and routes"),
        asset("bus2", "Bus routes", ["route_id", "route_name"], tags=["transit", "bus"],
              description="Transit bus route list"),
        asset("sp1", "Speed Check Sign - DFS001", ["site_id", "speed_limit"],
              description="Vehicle speed counts"),
        asset("sp2", "Speed Check Sign - DFS002", ["site_id", "speed_limit", "direction"],
              description="Vehicle speed counts"),
        asset("tree", "Trees", ["species", "latitude", "longitude", "geometry_point",
                                ":@computed_region_abcd_efgh"],
              types=["Text", "Number", "Number", "Point", "Number"], description="Tree inventory"),
        asset("park", "Parks", ["park_name", "the_geom", "location_address"],
              types=["Text", "MultiPolygon", "Text"], description="Park boundaries"),
        asset("map1", "Bus map", ["stop_id"]),
    ]
    inventory = [
        inv_row("bus1", "Bus stops"), inv_row("bus2", "Bus routes"),
        inv_row("sp1", "Speed Check Sign - DFS001", series_key="S|speed", category="Vehicle Speed",
                updated="2026-01-01"),
        inv_row("sp2", "Speed Check Sign - DFS002", series_key="S|speed", category="Vehicle Speed",
                updated="2026-02-01"),
        inv_row("tree", "Trees", category="Environmental"), inv_row("park", "Parks", category="Parks"),
        inv_row("map1", "Bus map", role="derived"),
    ]
    return raw, inventory


def test_every_real_dataset_is_in_exactly_one_unit():
    raw, inventory = fixture()
    units = sim.build_units(raw, inventory)
    members = [m for u in units for m in u["member_ids"].split(";")]
    real = [r["id"] for r in inventory if r["role"] == "candidate"]
    assert sorted(members) == sorted(real)
    assert len(units) == 5  # the two speed signs are one series unit; the map is not real


def test_series_unit_uses_latest_member_and_union_of_columns():
    raw, inventory = fixture()
    speed = next(u for u in sim.build_units(raw, inventory) if u["unit"] == "S|speed")
    assert speed["representative_id"] == "sp2"
    assert speed["n_members"] == 2
    assert speed["fields"] == ["direction", "site_id", "speed_limit"]


def test_location_only_columns_are_not_schema_fields():
    names = ["species", "latitude", "longitude", "geometry_point", ":@computed_region_abcd_efgh",
             "the_geom", "location_address", "neighbourhood_name", "Ward"]
    types = ["Text", "Number", "Number", "Point", "Number", "MultiPolygon", "Text", "Text", "Text"]
    assert sim.schema_fields(names, types) == {"species", "neighbourhood_name", "ward"}


def test_units_a_signal_cannot_place_are_flagged_not_dropped():
    raw, inventory = fixture()
    units, neighbours, St, Ss, summary = sim.run(raw, inventory, k=3)
    assert St.shape == Ss.shape == (len(units), len(units))
    flags = {u["unit"]: u["flags"] for u in units}
    # Trees and Parks share no content column once location columns are dropped;
    # the speed series' columns are its own.
    isolated = {u for u, f in flags.items() if "schema:no_shared_field" in f}
    assert isolated == {"tree", "park", "S|speed"}
    assert summary["flags"]["schema:no_shared_field"] == 3


def test_neighbours_exclude_self_and_zero_scores():
    raw, inventory = fixture()
    units, neighbours, St, Ss, _ = sim.run(raw, inventory, k=3)
    assert np.all(np.diag(St) == 0) and np.all(np.diag(Ss) == 0)
    assert all(n["unit"] != n["neighbour"] and n["score"] > 0 for n in neighbours)
    bus = [n for n in neighbours if n["unit"] == "bus1" and n["signal"] == "schema"]
    assert bus[0]["neighbour"] == "bus2" and bus[0]["shared_fields"] == "route_id"
