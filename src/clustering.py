"""M3b: cluster the similarity units and compare with the portal's categories.

Reads `data/processed/similarity/<date>/` (M3a) and clusters three ways: text,
schema, and their mean. Agglomerative clustering, average linkage, on
1 - cosine. Categories are a reference, not ground truth (spec), so agreement is
reported with subsample intervals, and again without the categories that hold
more than DOMINANT_SHARE of all units (2026-10-02: Surveys and Census, which form
clusters of their own and inflate ARI from ~0.25 to ~0.88). Writes
`data/processed/clustering/<date>/`:

- `assignments.csv` one row per unit, a cluster id per signal
- `clusters.csv`    one row per cluster: size, frequent name words, top categories
- `summary.json`    agreement (ARI with a 95% subsample interval; AMI, NMI), stability, k sweep

    python -m src.clustering SIMILARITY_DIR [--k 60] [--out DIR] [--seed 0]
"""
import argparse
import collections
import csv
import json
import logging
import re
import sys
from pathlib import Path

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score, normalized_mutual_info_score

log = logging.getLogger("clustering")

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = ("text", "schema", "combined")
DOMINANT_SHARE = 0.10
K_SWEEP = (20, 40, 60, 90, 120)
NAME_STOPWORDS = {"the", "of", "and", "in", "for", "by", "to", "a", "on", "at", "edmonton",
                  "city", "data", "dataset", "current", "historical", "deprecated"}


def distances(sim):
    D = np.clip(1.0 - sim.astype(np.float64), 0.0, 1.0)
    np.fill_diagonal(D, 0.0)
    return D


def cluster(D, k):
    return AgglomerativeClustering(n_clusters=k, metric="precomputed", linkage="average").fit_predict(D)


def agreement(labels, categories, mask, rng, n_boot, frac=0.8):
    """ARI, AMI and NMI between clusters and categories on `mask`. ARI gets a 95%
    interval from random 80% subsets of units (clustering held fixed). Not a
    resample WITH replacement: duplicated units always agree with themselves, which
    pushed ARI's interval above its value. AMI and NMI get no interval: both
    shift with sample size at this many clusters, so their subset spread didn't
    contain the full-data value either."""
    y, c = categories[mask], labels[mask]
    subsets = (rng.choice(len(y), int(frac * len(y)), replace=False) for _ in range(n_boot))
    boots = [adjusted_rand_score(y[i], c[i]) for i in subsets]
    return {"n": int(mask.sum()),
            "ari": round(adjusted_rand_score(y, c), 3),
            "ari_ci95": [round(float(np.percentile(boots, q)), 3) for q in (2.5, 97.5)],
            "ari_interval": f"{int(frac * 100)}% subsets x {n_boot}",
            "ami": round(adjusted_mutual_info_score(y, c), 3),
            "nmi": round(normalized_mutual_info_score(y, c), 3)}


def stability(D, labels, k, rng, n_sub, frac=0.8):
    """Re-cluster random 80% subsets; ARI between each subset clustering and the
    full clustering restricted to the same units."""
    scores = []
    for _ in range(n_sub):
        i = np.sort(rng.choice(len(D), int(frac * len(D)), replace=False))
        scores.append(adjusted_rand_score(labels[i], cluster(D[np.ix_(i, i)], k)))
    return {"subsets": n_sub, "fraction": frac, "ari_mean": round(float(np.mean(scores)), 3),
            "ari_min": round(float(np.min(scores)), 3)}


def name_words(names, n=4):
    words = collections.Counter()
    for name in names:
        words.update({w for w in re.findall(r"[a-z][a-z'-]*[a-z]", name.lower()) if w not in NAME_STOPWORDS})
    return ";".join(w for w, _ in words.most_common(n))


def describe(units, labels, signal):
    rows = []
    for c in sorted(set(labels)):
        members = [u for u, l in zip(units, labels) if l == c]
        cats = collections.Counter(u["category"] or "(none)" for u in members)
        rows.append({"signal": signal, "cluster": int(c), "size": len(members),
                     "name_words": name_words(u["name"] for u in members),
                     "top_categories": ";".join(f"{k}={v}" for k, v in cats.most_common(3)),
                     "n_categories": len(cats), "example": members[0]["name"]})
    return sorted(rows, key=lambda r: -r["size"])


def run(units, sims, k=60, seed=0, n_boot=1000, n_sub=20):
    rng = np.random.default_rng(seed)
    sims = dict(sims, combined=(sims["text"] + sims["schema"]) / 2)
    categories = np.array([u["category"] for u in units], dtype=object)
    counts = collections.Counter(categories[categories != ""])
    dominant = sorted(c for c, n in counts.items() if n > DOMINANT_SHARE * len(units))
    has_cat = categories != ""
    masks = {"all_categorised": has_cat, "without_dominant": has_cat & ~np.isin(categories, dominant)}

    assignments = [{"unit": u["unit"], "name": u["name"], "category": u["category"]} for u in units]
    clusters, summary = [], {"k": k, "n_units": len(units), "uncategorised_units": int((~has_cat).sum()),
                             "dominant_categories": {c: counts[c] for c in dominant}, "signals": {}}
    for signal in SIGNALS:
        D = distances(sims[signal])
        labels = cluster(D, k)
        for a, l in zip(assignments, labels):
            a[f"cluster_{signal}"] = int(l)
        clusters += describe(units, labels, signal)
        sizes = collections.Counter(labels)
        summary["signals"][signal] = {
            "largest_clusters": sorted(sizes.values(), reverse=True)[:5],
            "singletons": sum(1 for n in sizes.values() if n == 1),
            **{name: agreement(labels, categories, m, rng, n_boot) for name, m in masks.items()},
            "stability": stability(D, labels, k, rng, n_sub),
            "k_sweep_without_dominant": {
                kk: round(adjusted_rand_score(categories[masks["without_dominant"]],
                                              cluster(D, kk)[masks["without_dominant"]]), 3)
                for kk in K_SWEEP if kk < len(units)},
        }
    if len(assignments) != len(units):
        raise RuntimeError("assignment count differs from unit count")
    return assignments, clusters, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("similarity_dir")
    ap.add_argument("--k", type=int, default=60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "data/processed/clustering"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    sim_dir = Path(args.similarity_dir)
    with open(sim_dir / "units.csv", newline="", encoding="utf-8") as f:
        units = list(csv.DictReader(f))
    sims = {s: np.load(sim_dir / f"{s}_sim.npy") for s in ("text", "schema")}
    assignments, clusters, summary = run(units, sims, args.k, args.seed)

    out = Path(args.out) / sim_dir.name
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("assignments.csv", assignments), ("clusters.csv", clusters)):
        with open(out / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    summary = {"snapshot": sim_dir.name, "seed": args.seed, **summary}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    log.info("clustering path=%s %s", out, json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
