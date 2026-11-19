"""Guards on the MCP server (`src/mcp_server.py`), called in-process through the SDK's
client. The model is the fake from `test_search.py`, so no real model is needed."""
import asyncio
import json
import sys
import threading
import time
import types

import pytest
from mcp import Client

from src import mcp_server, search
from test_search import FakeModel, pkg


class CountingModel(FakeModel):
    loads = 0

    def __init__(self, *a, **kw):
        CountingModel.loads += 1


@pytest.fixture
def catalogue(monkeypatch, tmp_path):
    """Two sources whose snapshots the test can add to: {source: {snapshot: raw}}."""
    FakeModel.calls, CountingModel.loads = [], 0
    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=CountingModel))
    monkeypatch.setattr(search, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(mcp_server, "_model", None)
    monkeypatch.setattr(mcp_server, "_indexes", {})
    snaps = {"alberta": {"2026-11-17": [pkg(i, "Alberta Energy Regulator" if i < 4 else "Health")
                                        for i in range(10)]},
             "calgary": {"2026-11-17": []}}
    monkeypatch.setattr(search, "snapshot_dirs", lambda s: [tmp_path / s / d for d in sorted(snaps[s])])
    monkeypatch.setattr(search, "load_raw", lambda snap: snaps[snap.parent.name][snap.name])
    return snaps


def call(args):
    async def go():
        async with Client(mcp_server.server) as c:
            r = await c.call_tool("search_datasets", args)
            return r.is_error, r.content[0].text
    return asyncio.run(go())


def test_tool_returns_the_same_object_as_cli_json(catalogue, capsys):
    assert search.main(["water", "tank", "--source", "alberta,calgary", "-k", "3", "--json"]) == 0
    cli = json.loads(capsys.readouterr().out)
    err, text = call({"queries": ["water", "tank"], "sources": "alberta,calgary", "k": 3})
    assert not err
    assert json.loads(text) == cli
    assert len(cli["queries"][0]["hits"]["alberta"]) == 3


def test_model_loads_once_and_a_newer_snapshot_is_picked_up_without_restart(catalogue):
    call({"queries": ["water"], "sources": "alberta"})
    call({"queries": ["water"], "sources": "alberta"})
    assert CountingModel.loads == 1
    assert FakeModel.calls == [6]  # second call reused the loaded index; nothing re-embedded

    catalogue["alberta"]["2026-11-24"] = [pkg(i, "Health") for i in range(12)]
    _, text = call({"queries": ["water"], "sources": "alberta"})
    out = json.loads(text)["sources"]["alberta"]
    assert (out["snapshot"], out["n_records"]) == ("2026-11-24", 12)
    assert CountingModel.loads == 1


def test_bad_arguments_are_tool_errors_and_the_server_keeps_serving(catalogue):
    err, text = call({"queries": ["water"], "sources": "nope"})
    assert err and "unknown source(s) ['nope']" in text
    err, text = call({"queries": []})
    assert err and "at least one non-blank phrase" in text
    err, text = call({"queries": ["water"], "k": 0})
    assert err and "k must be between 1 and 25" in text
    err, text = call({"queries": ["water"], "sources": "calgary"})
    assert not err and json.loads(text)["queries"][0]["hits"]["calgary"] == []


def test_a_slow_peek_does_not_hold_up_another_search(catalogue, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(search, "peek", lambda r: release.wait(10) and "rows")
    call({"queries": ["water"], "sources": "alberta"})  # build the index first; loading is serialised by design
    done = []

    async def go():
        async with Client(mcp_server.server) as c:
            async def peeking():
                await c.call_tool("search_datasets", {"queries": ["water"], "sources": "alberta", "peek": True})
                done.append("peek")

            async def plain():
                t = time.time()
                await c.call_tool("search_datasets", {"queries": ["water"], "sources": "alberta"})
                done.append(("plain", time.time() - t))
                release.set()
            slow = asyncio.create_task(peeking())
            await asyncio.sleep(0.2)
            await asyncio.gather(plain(), slow)
    asyncio.run(go())
    assert done[0][0] == "plain" and done[0][1] < 5 and done[1] == "peek"


def test_a_failed_load_tells_the_caller_why(catalogue, monkeypatch):
    def broken(snap):
        raise OSError("catalog.json.gz is truncated")
    monkeypatch.setattr(search, "load_raw", broken)
    err, text = call({"queries": ["water"], "sources": "alberta"})
    assert err and "OSError: catalog.json.gz is truncated" in text
