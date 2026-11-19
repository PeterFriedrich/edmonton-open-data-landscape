"""MCP server (stdio) over `src.search`, so the embedding model stays loaded between
searches instead of reloading on every command-line run.

    .venv/bin/python -m src.mcp_server

One tool, `search_datasets`, returning the same object as `python -m src.search --json`.
The model and each source's index load on the first call that needs them; every call
checks for a newer snapshot and rebuilds only that source. A source whose vectors are
not cached yet is embedded inside that first call (minutes for a new snapshot with many
changed records; 13m43s for all three from empty), so run the CLI once after a harvest to
warm the cache. Registering the server with
Claude Code is the `server` session's call; from another machine, run this command over
ssh as the server command (stdio needs no open port).

Everything printed to stdout is protocol: progress goes to stderr (`embed_cached`).
"""
import sys
import threading
import traceback

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from src import search

MAX_K = 25

server = MCPServer(
    "open-data-search",
    instructions=(
        "Search Alberta open-data catalogues (data.edmonton.ca, data.calgary.ca, open.alberta.ca) "
        "by metadata to shortlist datasets before pulling data. Each source is ranked separately."),
)

_lock = threading.Lock()
_model = None
_indexes = {}  # (source, include_hidden) -> (snapshot name, meta, index)


def _index(name, include_hidden):
    snaps = search.snapshot_dirs(name)[-1:]
    if not snaps:
        return {"skipped": "no snapshot harvested"}, None
    cached = _indexes.get((name, include_hidden))
    if cached and cached[0] == snaps[0].name:
        return cached[1], cached[2]
    meta, index = search.build_index(name, snaps[0], _model, include_hidden)
    _indexes[(name, include_hidden)] = (snaps[0].name, meta, index)
    return meta, index


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


if __name__ == "__main__":
    server.run("stdio")
