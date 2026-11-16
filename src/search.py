"""Free-text search over the catalogue metadata: which datasets bear on a question.

Ranks the M3a units (name + tags + description, plus column names) against a
query by half embedding cosine, half TF-IDF cosine. The first run on a snapshot
embeds every unit (~4 min on this CPU) and caches the vectors in
`data/processed/search/<date>/`; later queries take a few seconds. The cache is
private: the vectors come from description text (never publish them).

    python -m src.search "property tax by neighbourhood" ["another query" ...]
                         [-k 12] [--peek] [--snapshot DIR]

--peek fetches 3 live rows of each hit from data.edmonton.ca, to check that
the columns needed are really there before pulling the dataset.
"""
import argparse
import gzip
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from src.inventory import build_inventory
from src.similarity import build_units

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ROOT / "data/raw/private-snapshots"
MODEL = "BAAI/bge-small-en-v1.5"


def latest_snapshot():
    return max(p for p in SNAPSHOTS.iterdir() if (p / "catalog.json.gz").exists())


def load_units(snap):
    with gzip.open(snap / "catalog.json.gz", "rt", encoding="utf-8") as f:
        raw = json.load(f)
    # build_units expects the inventory CSV's string values.
    inv = [{k: "" if v is None else str(v) for k, v in r.items()} for r in build_inventory(raw)]
    return build_units(raw, inv)


def unit_text(u):
    return u["text"] + " " + " ".join(f.replace("_", " ") for f in u["fields"])


def rank(query, units, E, qe, tfidf, X, k):
    s = 0.5 * (E @ qe) + 0.5 * (X @ tfidf.transform([query]).T).toarray().ravel()
    return [(float(s[i]), units[i]) for i in np.argsort(-s, kind="stable")[:k]]


def peek(dataset_id, n=3):
    url = f"https://data.edmonton.ca/resource/{dataset_id}.json?$limit={n}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.load(r)
    except Exception as e:  # report and carry on; one dead dataset shouldn't stop the list
        return f"peek failed: {e}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("queries", nargs="+")
    ap.add_argument("-k", type=int, default=12)
    ap.add_argument("--peek", action="store_true")
    ap.add_argument("--snapshot", help="raw snapshot dir; default: the latest")
    args = ap.parse_args(argv)

    from fastembed import TextEmbedding  # local env only; not in requirements-ci.txt

    snap = Path(args.snapshot) if args.snapshot else latest_snapshot()
    cache = ROOT / "data/processed/search" / snap.name
    units = load_units(snap)
    texts = [unit_text(u) for u in units]
    model = TextEmbedding(MODEL, cache_dir=str(Path.home() / ".cache/fastembed"))
    try:
        E = np.load(cache / "vectors.npy")
        if json.loads((cache / "units.json").read_text()) != [u["unit"] for u in units]:
            raise ValueError("unit list changed")
    except (OSError, ValueError):
        print(f"embedding {len(units)} units from {snap.name} (one-off, ~4 min)...", file=sys.stderr)
        E = np.asarray(list(model.embed(texts)), dtype=np.float32)
        E /= np.linalg.norm(E, axis=1, keepdims=True)
        cache.mkdir(parents=True, exist_ok=True)
        np.save(cache / "vectors.npy", E)
        (cache / "units.json").write_text(json.dumps([u["unit"] for u in units]))
    tfidf = TfidfVectorizer(stop_words="english", sublinear_tf=True)
    X = tfidf.fit_transform(texts)

    print(f"snapshot {snap.name}, {len(units)} units")
    for q in args.queries:
        qe = np.asarray(list(model.query_embed([q]))[0], dtype=np.float32)
        qe /= np.linalg.norm(qe)
        print(f"\n== {q}")
        for score, u in rank(q, units, E, qe, tfidf, X, args.k):
            rid = u["representative_id"]
            series = f" (series of {u['n_members']})" if u["n_members"] > 1 else ""
            print(f"{score:.2f}  {rid}  [{u['category'] or '-'}]  {u['name']}{series}")
            print(f"      https://data.edmonton.ca/d/{rid}")
            print(f"      cols: {', '.join(u['fields'][:20])}{' ...' if len(u['fields']) > 20 else ''}")
            if args.peek:
                print("      rows: " + json.dumps(peek(rid))[:600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
