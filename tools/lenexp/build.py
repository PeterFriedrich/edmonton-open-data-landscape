"""Build unit texts (base + boilerplate-stripped) and the BM25 / embedding matrices.

Run from the repo root: .venv/bin/python <this> OUT_DIR
"""
import collections, csv, gzip, json, re, sys, time
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer

sys.path.insert(0, ".")
from src.similarity import build_units, clean_text, RARE_TEXT_MAX_UNITS
from src.embeddings import cosine_dense, EMBED_BATCH, DEFAULT_MODEL

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
SNAP = "2026-10-02"
raw = json.load(gzip.open(f"data/raw/private-snapshots/{SNAP}/catalog.json.gz", "rt"))
inv = list(csv.DictReader(open(f"data/processed/inventory/{SNAP}.csv")))
units = build_units(raw, inv)
ref = [r["unit"] for r in csv.DictReader(open(f"data/processed/similarity/{SNAP}/units.csv"))]
assert [u["unit"] for u in units] == ref, "unit order differs from the committed similarity run"

# Boilerplate = a sentence (digits folded) used by more than RARE_TEXT_MAX_UNITS units.
SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
key = lambda s: re.sub(r"\d+", "#", s.lower()).strip(" .")
by_id = {a["resource"]["id"]: a for a in raw}
sents = []
for u in units:
    d = clean_text(by_id[u["representative_id"]]["resource"].get("description") or "")
    sents.append([s for s in SPLIT.split(d) if s.strip()])
df = collections.Counter(k for ss in sents for k in {key(s) for s in ss})
stripped, lost = [], []
for u, ss in zip(units, sents):
    keep = [s for s in ss if df[key(s)] <= RARE_TEXT_MAX_UNITS]
    tags = " ".join(by_id[u["representative_id"]]["classification"].get("domain_tags") or [])
    stripped.append(clean_text(" ".join([u["name"], tags, " ".join(keep)])))
    lost.append((sum(len(s.split()) for s in ss) - sum(len(s.split()) for s in keep)))
texts = {"base": [u["text"] for u in units], "stripped": stripped}
json.dump({"units": [u["unit"] for u in units], "words_removed": lost,
           "words_base": [len(t.split()) for t in texts["base"]],
           "words_stripped": [len(t.split()) for t in stripped]}, open(OUT / "texts_meta.json", "w"))


def bm25(docs, b, k1=1.2):
    """More-like-this BM25: unit i's own terms (binary) are the query against every unit."""
    cv = CountVectorizer(stop_words="english", min_df=2, max_df=0.5, ngram_range=(1, 2))
    tf = cv.fit_transform(docs).tocsr().astype(np.float64)
    n = tf.shape[0]
    dfreq = np.asarray((tf > 0).sum(0)).ravel()
    idf = np.log(1 + (n - dfreq + 0.5) / (dfreq + 0.5))
    dl = np.asarray(tf.sum(1)).ravel(); avg = dl.mean()
    W = tf.tocoo()
    denom = W.data + k1 * (1 - b + b * dl[W.row] / avg)
    import scipy.sparse as sp
    D = sp.csr_matrix((W.data * (k1 + 1) / denom * idf[W.col], (W.row, W.col)), shape=tf.shape)
    Q = (tf > 0).astype(np.float64)
    S = (Q @ D.T).toarray().astype(np.float32)
    np.fill_diagonal(S, 0.0)
    return S


for name, docs in texts.items():
    for b in (0.0, 0.3, 0.75):
        np.save(OUT / f"bm25_b{b}_{name}.npy", bm25(docs, b))

from fastembed import TextEmbedding
model = TextEmbedding(DEFAULT_MODEL, cache_dir=str(Path.home() / ".cache/fastembed"))
t = time.time()
E = np.array(list(model.embed(stripped, batch_size=EMBED_BATCH)))
np.save(OUT / "embed_vecs_stripped.npy", E)
np.save(OUT / "embed_stripped.npy", cosine_dense(E))
print("embed stripped", round(time.time() - t), "s")
