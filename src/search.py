"""Free-text search over catalogue metadata: which datasets bear on a question.

Ranks each source's records (`src/records.py`: title + tags + description, plus
column names) against a query by half embedding cosine, half TF-IDF cosine.
Each source is ranked on its own and prints its own top k; there is no merged
list (spec, Outputs, Search). Vectors are cached per source per snapshot in
`data/processed/search/<source>/<date>/`, keyed by a hash of each record's text,
so a new snapshot embeds only what changed (a first run is ~4 min for Edmonton,
longer for the province). The cache is private: the vectors come from
description text (never publish them).

    python -m src.search "property tax by neighbourhood" ["another query" ...]
                         [--source edmonton,calgary,alberta|all] [-k 12]
                         [--include-hidden] [--json] [--peek] [--snapshot DIR]

Hidden publishers (Alberta Energy Regulator) are left out unless
--include-hidden; the number hidden is printed. --peek fetches 3 live rows of
each Socrata hit, to check that the columns needed are really there before
pulling the dataset; open.alberta.ca has no working row API.
"""
import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from src.records import SOURCES, build_records, load_raw, search_text, snapshot_dirs

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/processed/search"
MODEL = "BAAI/bge-small-en-v1.5"
JSON_DESCRIPTION_CHARS = 300


def rank(query, units, E, qe, tfidf, X, k):
    s = 0.5 * (E @ qe) + 0.5 * (X @ tfidf.transform([query]).T).toarray().ravel()
    return [(float(s[i]), units[i]) for i in np.argsort(-s, kind="stable")[:k]]


def split_hidden(records, hidden, include_hidden):
    if include_hidden:
        return records, 0
    kept = [r for r in records if r["publisher"] not in hidden]
    return kept, len(records) - len(kept)


def text_hash(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def embed_cached(texts, source, snap_name, embed):
    """Vectors for `texts`, reusing any this source's earlier caches hold for the
    same text. `embed` maps a list of texts to an (n, d) array. Only the newest
    readable cache made with MODEL is used: it holds what changed since older ones."""
    hashes = [text_hash(t) for t in texts]
    out = CACHE / source / snap_name
    known = {}
    for d in sorted(CACHE.glob(f"{source}/*/hashes.json"), reverse=True):
        try:
            V, meta = np.load(d.parent / "vectors.npy"), json.loads(d.read_text())
        except (OSError, ValueError):
            continue
        if meta.get("model") == MODEL and len(meta.get("hashes", [])) == len(V):
            known = dict(zip(meta["hashes"], V))
            break
    todo = [i for i, h in enumerate(hashes) if h not in known]
    if todo:
        print(f"embedding {len(todo)} of {len(texts)} {source} records from {snap_name}...", file=sys.stderr)
        V = np.asarray(embed([texts[i] for i in todo]), dtype=np.float32)
        V /= np.linalg.norm(V, axis=1, keepdims=True)
        known.update(zip((hashes[i] for i in todo), V))
    E = np.stack([known[h] for h in hashes]).astype(np.float32)
    if todo or not (out / "hashes.json").exists():
        out.mkdir(parents=True, exist_ok=True)
        np.save(out / "vectors.npy", E)
        (out / "hashes.json").write_text(json.dumps({"model": MODEL, "hashes": hashes}))
    return E


def peek(record, n=3):
    if SOURCES[record["source"]]["platform"] != "socrata":
        return "no row API for this source"
    url = f"https://{SOURCES[record['source']]['domain']}/resource/{record['id']}.json?$limit={n}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.load(r)
    except Exception as e:  # report and carry on; one dead dataset shouldn't stop the list
        return f"peek failed: {e}"


def parse_sources(arg):
    names = list(SOURCES) if arg == "all" else [s.strip() for s in arg.split(",") if s.strip()]
    bad = [s for s in names if s not in SOURCES]
    if bad or not names:
        raise SystemExit(f"unknown source(s) {bad}; known: {', '.join(SOURCES)}")
    return names


def print_hit(score, r, show_peek):
    series = f" (series of {r['n_members']})" if r["n_members"] > 1 else ""
    print(f"{score:.2f}  {r['id']}  [{r['category'] or '-'}]  {r['title']}{series}")
    print(f"      {r['url']}")
    if r["columns"]:
        print(f"      cols: {', '.join(r['columns'][:20])}{' ...' if len(r['columns']) > 20 else ''}")
    else:
        print(f"      publisher: {r['publisher'] or '-'}; formats: {', '.join(r['formats']) or '-'}")
    if show_peek:
        print("      rows: " + json.dumps(peek(r))[:600])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("queries", nargs="+")
    ap.add_argument("--source", default="all", help="comma-separated sources, or all (default)")
    ap.add_argument("-k", type=int, default=12, help="hits per source")
    ap.add_argument("--include-hidden", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--peek", action="store_true")
    ap.add_argument("--snapshot", help="raw snapshot dir (one source only); default: each source's latest")
    args = ap.parse_args(argv)
    names = parse_sources(args.source)
    if args.snapshot and len(names) != 1:
        raise SystemExit("--snapshot needs exactly one --source")

    from fastembed import TextEmbedding  # local env only; not in requirements-ci.txt
    model = TextEmbedding(MODEL, cache_dir=str(Path.home() / ".cache/fastembed"))

    indexes, meta = {}, {}
    for name in names:
        snaps = [Path(args.snapshot)] if args.snapshot else snapshot_dirs(name)[-1:]
        if not snaps:
            meta[name], indexes[name] = {"skipped": "no snapshot harvested"}, None
            continue
        snap = snaps[0]
        records, dropped = build_records(load_raw(snap), name)
        records, n_hidden = split_hidden(records, SOURCES[name]["hidden"], args.include_hidden)
        texts = [search_text(r) for r in records]
        if texts:
            E = embed_cached(texts, name, snap.name, lambda ts: list(model.embed(ts)))
            tfidf = TfidfVectorizer(stop_words="english", sublinear_tf=True)
            indexes[name] = (records, E, tfidf, tfidf.fit_transform(texts))
        else:
            indexes[name] = None
        meta[name] = {"snapshot": snap.name, "n_records": len(records), "n_hidden": n_hidden,
                      "hidden_publishers": sorted(SOURCES[name]["hidden"]) if n_hidden else [],
                      "dropped": dropped}

    out = {"sources": meta, "queries": []}
    if not args.json:
        for name, m in meta.items():
            if "skipped" in m:
                print(f"{name}: skipped, {m['skipped']}")
                continue
            hid = (f", {m['n_hidden']} hidden ({'; '.join(m['hidden_publishers'])}; --include-hidden shows them)"
                   if m["n_hidden"] else "")
            print(f"{name}: snapshot {m['snapshot']}, {m['n_records']} records{hid}")
    for q in args.queries:
        qe = np.asarray(list(model.query_embed([q]))[0], dtype=np.float32)
        qe /= np.linalg.norm(qe)
        hits = {name: rank(q, ix[0], ix[1], qe, ix[2], ix[3], args.k) if ix else []
                for name, ix in indexes.items()}
        if args.json:
            out["queries"].append({"query": q, "hits": {
                name: [{"score": round(s, 4), **r, "description": r["description"][:JSON_DESCRIPTION_CHARS],
                        **({"rows": peek(r)} if args.peek else {})}
                       for s, r in hs] for name, hs in hits.items()}})
            continue
        print(f"\n== {q}")
        for name, hs in hits.items():
            print(f"-- {name}")
            for score, r in hs:
                print_hit(score, r, args.peek)
    if args.json:
        json.dump(out, sys.stdout, indent=1)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
