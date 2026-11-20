"""Guards on the MCP server (`src/mcp_server.py`), called in-process through the SDK's
client. The model is the fake from `test_search.py`, so no real model is needed."""
import asyncio
import json
import shutil
import socket
import subprocess
import sys
import threading
import time
import types
from pathlib import Path

import pytest
import uvicorn
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
    warm("alberta")
    return snaps


def warm(source):
    """What weekly_snapshot.sh does after a harvest: the CLI embeds, the server only reads."""
    assert search.main(mcp_server.WARM.format(source).split()[3:]) == 0


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
    CountingModel.loads = 0
    call({"queries": ["water"], "sources": "alberta"})
    call({"queries": ["water"], "sources": "alberta", "include_hidden": True})  # the warm step covers both views
    assert CountingModel.loads == 1
    assert FakeModel.calls == [10]  # only the warm step embedded

    catalogue["alberta"]["2026-11-24"] = [pkg(i, "Health") for i in range(12)]
    warm("alberta")
    CountingModel.loads = 0
    _, text = call({"queries": ["water"], "sources": "alberta"})
    out = json.loads(text)["sources"]["alberta"]
    assert (out["snapshot"], out["n_records"], "cache_cold" in out) == ("2026-11-24", 12, False)
    assert CountingModel.loads == 0


def test_a_cold_snapshot_is_never_embedded_inside_a_request(catalogue):
    """2026-11-20: an in-request embed of a new snapshot hung the box. The server must serve
    the newest warm snapshot and say so, then pick up the new one once the CLI warms it."""
    call({"queries": ["water"], "sources": "alberta"})
    catalogue["alberta"]["2026-11-24"] = [pkg(i, "Health") for i in range(12)]
    FakeModel.calls = []
    for _ in range(2):
        err, text = call({"queries": ["water"], "sources": "alberta"})
        out = json.loads(text)["sources"]["alberta"]
        assert not err and out["snapshot"] == "2026-11-17"
        assert out["cache_cold"]["newest_snapshot"] == "2026-11-24"
        assert "12 alberta records from 2026-11-24" in out["cache_cold"]["reason"]
        assert out["cache_cold"]["warm_with"] == mcp_server.WARM.format("alberta")
    assert FakeModel.calls == []

    warm("alberta")
    out = json.loads(call({"queries": ["water"], "sources": "alberta"})[1])["sources"]["alberta"]
    assert out["snapshot"] == "2026-11-24" and "cache_cold" not in out


def test_a_source_with_no_warm_snapshot_is_skipped_with_the_warm_command(catalogue, tmp_path):
    for d in (tmp_path / "cache").iterdir():
        shutil.rmtree(d)
    FakeModel.calls = []
    err, text = call({"queries": ["water"], "sources": "alberta"})
    out = json.loads(text)
    assert not err and out["queries"][0]["hits"]["alberta"] == []
    assert out["sources"]["alberta"]["skipped"].startswith("cache cold: 6 of 6 alberta records")
    assert mcp_server.WARM.format("alberta") in out["sources"]["alberta"]["skipped"]
    assert FakeModel.calls == []


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


def free_port():
    with socket.socket() as s:
        s.bind((mcp_server.HOST, 0))
        return s.getsockname()[1]


def listening_addresses(port):
    """Local addresses with a socket listening on `port`, from /proc/net/tcp{,6} (Linux)."""
    out = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        for line in Path(table).read_text().splitlines()[1:]:
            local, state = line.split()[1], line.split()[3]
            addr, hexport = local.split(":")
            if state == "0A" and int(hexport, 16) == port:  # 0A = LISTEN
                out.add(addr)
    return out


def test_http_command_serves_the_tool_and_listens_on_loopback_only(tmp_path):
    port = free_port()
    log = (tmp_path / "server.log").open("w")
    proc = subprocess.Popen([sys.executable, "-m", "src.mcp_server", "--transport", "http", "--port", str(port)],
                            cwd=Path(__file__).resolve().parents[1], stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(100):
            if listening_addresses(port) or proc.poll() is not None:
                break
            time.sleep(0.1)
        assert proc.poll() is None, (tmp_path / "server.log").read_text()
        assert listening_addresses(port) == {"0100007F"}  # 127.0.0.1, and nothing else

        async def go():
            async with Client(f"http://{mcp_server.HOST}:{port}{mcp_server.HTTP_PATH}") as c:
                return [t.name for t in (await c.list_tools()).tools]
        assert asyncio.run(asyncio.wait_for(go(), 30)) == ["search_datasets"]
    finally:
        proc.terminate()
        proc.wait(10)


def test_http_sessions_are_served_concurrently(catalogue, monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(search, "peek", lambda r: release.wait(10) and "rows")
    call({"queries": ["water"], "sources": "alberta"})  # build the index first; loading is serialised by design
    port = free_port()
    http = uvicorn.Server(uvicorn.Config(mcp_server.server.streamable_http_app(**mcp_server.HTTP_APP),
                                         host=mcp_server.HOST, port=port, log_level="warning"))
    threading.Thread(target=http.run, daemon=True).start()
    for _ in range(100):
        if http.started:
            break
        time.sleep(0.05)
    assert http.started
    url = f"http://{mcp_server.HOST}:{port}{mcp_server.HTTP_PATH}"
    done = []

    async def session(args, label):
        async with Client(url) as c:
            t = time.time()
            r = await c.call_tool("search_datasets", args)
            done.append((label, r.is_error, time.time() - t))
            release.set()

    async def go():
        slow = asyncio.create_task(session({"queries": ["water"], "sources": "alberta", "peek": True}, "peek"))
        await asyncio.sleep(0.5)
        await asyncio.gather(*(session({"queries": ["water"], "sources": "alberta"}, f"plain{i}") for i in range(3)), slow)
    try:
        asyncio.run(asyncio.wait_for(go(), 30))
    finally:
        release.set()
        http.should_exit = True
    assert sorted(d[0] for d in done[:3]) == ["plain0", "plain1", "plain2"]
    assert all(not err and secs < 5 for _, err, secs in done[:3]) and done[3][:2] == ("peek", False)
