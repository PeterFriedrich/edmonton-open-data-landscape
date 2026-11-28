"""Score each similarity variant on the 210 labelled pairs and on catalogue-wide hubness.

Run from the repo root: .venv/bin/python <this> OUT_DIR
"""
import csv, json, sys
from pathlib import Path
import numpy as np
from scipy.stats import skew, spearmanr

OUT = Path(sys.argv[1]); SNAP = "2026-10-02"; K = 5
SIM = Path(f"data/processed/similarity/{SNAP}")
units = [r["unit"] for r in csv.DictReader(open(SIM / "units.csv"))]
idx = {u: i for i, u in enumerate(units)}
n_terms = np.array([int(r["n_text_terms"]) for r in csv.DictReader(open(SIM / "units.csv"))])
meta = json.load(open(OUT / "texts_meta.json"))
prog = {r["unit"]: r["programme_key"] for r in csv.DictReader(open(f"data/processed/programmes/{SNAP}/assignments.csv"))}

pairs = list(csv.DictReader(open(f"data/spotcheck/{SNAP}_pairs.csv")))
verdict = {r["pair_id"]: r["verdict"] for r in csv.DictReader(open(f"data/spotcheck/{SNAP}_labels.csv"))}
lab = {}
for p in pairs:
    if p["pair_id"] in verdict:
        lab[(p["unit"], p["neighbour"])] = verdict[p["pair_id"]]
sample = sorted({p["unit"] for p in pairs}, key=lambda u: pairs[[q["unit"] for q in pairs].index(u)]["pair_id"])
missing = [u for u in sample if u not in idx] + [n for (_, n) in lab if n not in idx]
assert not missing, missing

def csls(S, k=10):
    T = S.copy(); np.fill_diagonal(T, -np.inf)
    r = np.sort(T, 1)[:, -k:].mean(1)
    C = 2 * S - r[None, :]          # r_i is constant within row i, so it can't change a ranking
    np.fill_diagonal(C, -np.inf)
    return C

def ranks(S):
    T = S.astype(float).copy(); np.fill_diagonal(T, -np.inf)
    return np.argsort(-T, 1, kind="stable")

def rrf(*Ss, k=60):
    n = Ss[0].shape[0]; R = np.zeros((n, n))
    for S in Ss:
        o = ranks(S); pos = np.empty_like(o); pos[np.arange(n)[:, None], o] = np.arange(1, n + 1)[None, :]
        R += 1.0 / (k + pos)
    np.fill_diagonal(R, 0)
    return R

L = lambda f: np.load(f).astype(float)
tfidf = L(SIM / "text_sim.npy"); emb = L(SIM / "embed_sim.npy")
V = {
    "tfidf (current)": tfidf,
    "bm25 b=0.75": L(OUT / "bm25_b0.75_base.npy"),
    "bm25 b=0.3": L(OUT / "bm25_b0.3_base.npy"),
    "bm25 b=0": L(OUT / "bm25_b0.0_base.npy"),
    "bm25 b=0.3 stripped": L(OUT / "bm25_b0.3_stripped.npy"),
    "embed (current)": emb,
    "embed stripped": L(OUT / "embed_stripped.npy"),
    "embed CSLS": csls(emb),
    "embed stripped CSLS": csls(L(OUT / "embed_stripped.npy")),
    "RRF tfidf+embed": rrf(tfidf, emb),
    "RRF bm25 b=0.3 + embed stripped": rrf(L(OUT / "bm25_b0.3_base.npy"), L(OUT / "embed_stripped.npy")),
}

short = lambda u: n_terms[idx[u]] <= 25
def label_block(top, us):
    v = [lab.get((u, units[j])) for u in us for j in top[idx[u]]]
    lbl = [x for x in v if x]
    yes = lbl.count("yes")
    known_yes = [(u, n) for (u, n), x in lab.items() if x == "yes" and u in us]
    hit = sum(idx[n] in set(top[idx[u]]) for u, n in known_yes)
    known_no = sum(x == "no" for x in v)
    return {"labelled": f"{len(lbl)}/{len(v)}", "prec_labelled": round(yes / len(lbl), 3) if lbl else None,
            "known_yes_in_top5": f"{hit}/{len(known_yes)}", "known_no_in_top5": known_no}

out = {}
for name, S in V.items():
    o = ranks(S); top = o[:, :K]
    N = np.bincount(top.ravel(), minlength=len(units))
    T = S.copy(); np.fill_diagonal(T, -np.inf)
    bands = {}
    for lo, hi in [(0, 10), (11, 25), (26, 80), (81, 117), (118, 10**6)]:
        m = (n_terms >= lo) & (n_terms <= hi)
        bands[f"{lo}-{hi if hi < 10**6 else '+'}"] = round(float(N[m].mean()), 1)
    outside = [u for u in sample if not prog.get(u)]
    out[name] = {
        "k_skew": round(float(skew(N)), 2), "max_hub": int(N.max()), "never_in_top5": int((N == 0).sum()),
        "rho_len_indegree": round(float(spearmanr(n_terms, N).statistic), 2),
        "mean_in_top5_by_len_band": bands,
        "all20": label_block(top, sample), "outside_programmes17": label_block(top, outside),
        "short_units": label_block(top, [u for u in sample if short(u)]),
        "longer_units": label_block(top, [u for u in sample if not short(u)]),
    }
out["_meta"] = {"sample_short_units": [u for u in sample if short(u)],
                "n_sample": len(sample), "labels": len(lab),
                "units_with_boilerplate_removed": int(sum(1 for w in meta["words_removed"] if w)),
                "median_words_base": float(np.median(meta["words_base"])),
                "median_words_stripped": float(np.median(meta["words_stripped"]))}
json.dump(out, open(OUT / "results.json", "w"), indent=1)
for name, r in out.items():
    if name == "_meta": print(json.dumps(r)); continue
    print(f"{name:34s} skew {r['k_skew']:5.2f} hub {r['max_hub']:3d} never {r['never_in_top5']:3d} "
          f"rho {r['rho_len_indegree']:5.2f} | 17: {r['outside_programmes17']} | short: {r['short_units']}")
    print(" " * 34, "bands", r["mean_in_top5_by_len_band"], "| all20", r["all20"])

# Unlabelled pairs the promising variants put in a sample unit's top 5.
new = {}
for name in ("embed stripped", "embed CSLS", "embed stripped CSLS", "RRF tfidf+embed"):
    top = ranks(V[name])[:, :K]
    new[name] = {(u, units[j]) for u in sample for j in top[idx[u]] if (u, units[j]) not in lab}
    print(name, "unlabelled pairs:", len(new[name]))
print("union of the three embed variants:", len(new["embed stripped"] | new["embed CSLS"] | new["embed stripped CSLS"]))
