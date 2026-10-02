"""M3 text-signal variant: sentence embeddings of the same unit text TF-IDF uses.

Rebuilds the M3a units (name + tags + description, one unit per real dataset or
series), embeds them with a fastembed ONNX model (no torch; DECISIONS 2026-10-02),
and writes next to the M3a outputs in `data/processed/similarity/<date>/`:

- `embed_sim.npy`        unit x unit cosine matrix, rows in units.csv order
- `embed_neighbours.csv` top-k neighbours per unit, signal `embed`
- `embed_summary.json`   model, category agreement, agreement with text and schema

Texts longer than the model's limit (512 tokens for bge-small) are truncated, so
long descriptions count only by their opening.

    python -m src.embeddings RAW_SNAPSHOT_DIR [--inventory CSV] [--sim-dir DIR]
                             [--model NAME] [--cache-dir DIR] [--k 10]
"""
import argparse
import csv
import gzip
import json
import logging
import sys
from pathlib import Path

import numpy as np

from src.similarity import NEIGHBOUR_FIELDS, build_units, category_agreement, signal_agreement, top_neighbours

log = logging.getLogger("embeddings")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


def check_unit_order(units, units_csv):
    """The matrices are compared row by row with M3a's, so the units must be the
    same and in the same order. Fail rather than misalign."""
    with open(units_csv, newline="", encoding="utf-8") as f:
        expected = [r["unit"] for r in csv.DictReader(f)]
    got = [u["unit"] for u in units]
    if got != expected:
        raise RuntimeError(f"units differ from {units_csv} ({len(got)} vs {len(expected)}); "
                           "re-run src.similarity on the same snapshot first")


def cosine_dense(E):
    E = E / np.linalg.norm(E, axis=1, keepdims=True)
    S = (E @ E.T).astype(np.float32)
    np.fill_diagonal(S, 0.0)
    return S


def run(units, embed, St, Ss, k=10):
    """`embed` maps a list of texts to an (n, d) array; injected so tests need no model."""
    E = np.asarray(embed([u["text"] for u in units]), dtype=np.float32)
    Se = cosine_dense(E)
    top5 = lambda S, i: set(np.argsort(-S[i], kind="stable")[:5])
    summary = {
        "n_units": len(units), "dim": int(E.shape[1]),
        "category_agreement": category_agreement(Se, units),
        "agreement_with_text": signal_agreement(Se, St),
        "agreement_with_schema": signal_agreement(Se, Ss),
        "top5_shared_with_text_mean": round(float(np.mean(
            [len(top5(Se, i) & top5(St, i)) for i in range(len(units))])), 3),
    }
    return Se, top_neighbours(Se, units, "embed", k), summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw_dir")
    ap.add_argument("--inventory", help="default: data/processed/inventory/<snapshot date>.csv")
    ap.add_argument("--sim-dir", help="default: data/processed/similarity/<snapshot date>")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--cache-dir", default=str(Path.home() / ".cache/fastembed"))
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    from fastembed import TextEmbedding  # local env only; not in requirements-ci.txt

    raw_dir = Path(args.raw_dir)
    inv_path = Path(args.inventory or ROOT / f"data/processed/inventory/{raw_dir.name}.csv")
    sim_dir = Path(args.sim_dir or ROOT / f"data/processed/similarity/{raw_dir.name}")
    with gzip.open(raw_dir / "catalog.json.gz", "rt", encoding="utf-8") as f:
        raw = json.load(f)
    with open(inv_path, newline="", encoding="utf-8") as f:
        inventory = list(csv.DictReader(f))

    units = build_units(raw, inventory)
    check_unit_order(units, sim_dir / "units.csv")
    model = TextEmbedding(args.model, cache_dir=args.cache_dir)
    Se, neighbours, summary = run(units, lambda texts: list(model.embed(texts)),
                                  np.load(sim_dir / "text_sim.npy"), np.load(sim_dir / "schema_sim.npy"), args.k)

    np.save(sim_dir / "embed_sim.npy", Se)
    with open(sim_dir / "embed_neighbours.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=NEIGHBOUR_FIELDS)
        w.writeheader()
        w.writerows(neighbours)
    summary = {"snapshot": raw_dir.name, "model": args.model, **summary}
    (sim_dir / "embed_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    log.info("embeddings path=%s %s", sim_dir, json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
