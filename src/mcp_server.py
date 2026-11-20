"""MCP server over `src.search`, so the embedding model stays loaded between searches
instead of reloading on every command-line run.

    .venv/bin/python -m src.mcp_server                      # stdio, one process per client
    .venv/bin/python -m src.mcp_server --transport http     # shared, http://127.0.0.1:8765/mcp

One tool, `search_datasets`, returning the same object as `python -m src.search --json`.
The model and each source's index load on the first call that needs them; every call
checks for a newer snapshot and rebuilds only that source. The server never embeds
records: an in-request embed of a new snapshot took the box to 23 of 24 GB and hung it
(2026-11-20), and the service now runs under a 1 GB cap. If the newest snapshot's vectors
are not cached, it serves the newest snapshot that is and says so under `cache_cold`; if
none is, the source is skipped with the command that warms it (`WARM`, which
`scripts/weekly_snapshot.sh` runs after each harvest). Registering the server with
Claude Code is the `server` session's call; from another machine, run the stdio command
over ssh (no open port, no tunnel).

HTTP binds to loopback only, with no option to change it: this box has public ports.
It is stateless (no MCP session ids), so a client keeps working across a service restart.

Everything printed to stdout is protocol: progress goes to stderr (`embed_cached`).
"""
import argparse
import sys
import threading
import traceback

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from src import search

MAX_K = 25
HOST, PORT, HTTP_PATH = "127.0.0.1", 8765, "/mcp"
HTTP_APP = {"streamable_http_path": HTTP_PATH, "stateless_http": True}

server = MCPServer(
    "open-data-search",
    instructions=(
        "Search Alberta open-data catalogues (data.edmonton.ca, data.calgary.ca, open.alberta.ca) "
        "by metadata to shortlist datasets before pulling data. Each source is ranked separately."),
)

_lock = threading.Lock()
_model = None
_indexes = {}  # (source, include_hidden) -> (snapshot name, meta, index)
WARM = ".venv/bin/python -m src.search --source {} --include-hidden warm"  # --include-hidden caches both views


def _index(name, include_hidden):
    """Newest snapshot whose vectors are all cached; never embeds (module docstring)."""
    snaps = search.snapshot_dirs(name)
    if not snaps:
        return {"skipped": "no snapshot harvested"}, None
    cached = _indexes.get((name, include_hidden))
    if cached and cached[0] == snaps[-1].name:
        return cached[1], cached[2]
    cold = []
    for snap in reversed(snaps):
        if cached and cached[0] == snap.name:
            meta, index = cached[1], cached[2]
        else:
            try:
                meta, index = search.build_index(name, snap, _model, include_hidden, embed=False)
            except search.ColdCache as e:
                cold.append(str(e))
                continue
        if cold:
            meta = {**meta, "cache_cold": {"newest_snapshot": snaps[-1].name, "reason": cold[0],
                                           "warm_with": WARM.format(name)}}
        _indexes[(name, include_hidden)] = (snap.name, meta, index)
        return meta, index
    return {"skipped": f"cache cold: {cold[0]}; warm it with `{WARM.format(name)}`"}, None


@server.tool()
def search_datasets(queries: list[str], sources: str = "all", k: int = 5,
                    include_hidden: bool = False, peek: bool = False) -> dict:
    """Rank catalogue datasets against free-text queries (embedding + TF-IDF over title,
    tags, description and column names). Returns per-source snapshot info and, per query,
    the top k hits of each source with id, title, publisher, url, columns, category and a
    300-character description.

    queries: one or more search phrases.
    sources: comma-separated subset of edmonton, calgary, alberta, or "all".
    k: hits per source per query (1-25); each hit is about 1.5 KB of JSON.
    include_hidden: also show hidden publishers (Alberta Energy Regulator).
    peek: fetch 3 live rows of each Socrata hit (slower; open.alberta.ca has no row API).
    """
    global _model
    if not queries or not all(q.strip() for q in queries):
        raise ToolError("queries must hold at least one non-blank phrase")
    if not 1 <= k <= MAX_K:
        raise ToolError(f"k must be between 1 and {MAX_K}")
    try:
        names = search.parse_sources(sources)
    except SystemExit as e:  # parse_sources exits for the CLI; here it must not end the server
        raise ToolError(str(e)) from None
    meta, indexes = {}, {}
    with _lock:  # only loading is serialised; built indexes are read-only, so ranking and peeks run outside it
        try:
            if _model is None:
                _model = search.load_model()
            for name in names:
                meta[name], indexes[name] = _index(name, include_hidden)
        except Exception as e:  # the SDK hides an unexpected error's text from the caller
            traceback.print_exc(file=sys.stderr)
            raise ToolError(f"loading the search index failed: {type(e).__name__}: {e}") from e
        model = _model
    return {"sources": meta,
            "queries": [{"query": q, "hits": search.hits_json(search.query_hits(q, indexes, model, k), peek)}
                        for q in queries]}


def main(argv=None):
    p = argparse.ArgumentParser(description="MCP server over src.search")
    p.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    p.add_argument("--port", type=int, default=PORT, help=f"http only (default {PORT}); always on {HOST}")
    a = p.parse_args(argv)
    if a.transport == "stdio":
        server.run("stdio")
    else:
        server.run("streamable-http", host=HOST, port=a.port, **HTTP_APP)


if __name__ == "__main__":
    main()
