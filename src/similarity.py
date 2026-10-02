"""M3a: two dataset-similarity signals, kept separate (text and schema).

Works on real datasets with each series counted once (one unit per series; see
M1c). Reads the RAW snapshot (text uses descriptions) plus the M1c inventory, and
writes `data/processed/similarity/<date>/`:

- `units.csv`      one row per unit, with flags for units a signal can't place
- `neighbours.csv` top-k neighbours per unit per signal (score > 0 only)
- `text_sim.npy`, `schema_sim.npy`  unit x unit cosine matrices, rows in units.csv order
- `summary.json`   counts, category agreement vs chance, agreement between signals

    python -m src.similarity RAW_SNAPSHOT_DIR [--inventory CSV] [--out DIR] [--k 10]
"""
import argparse
import csv
import gzip
import json
import logging
import re
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.feature_extraction.text import TfidfVectorizer

log = logging.getLogger("similarity")

ROOT = Path(__file__).resolve().parents[1]
SIGNALS = ("text", "schema")
UNIT_FIELDS = ["unit", "representative_id", "name", "category", "n_members", "member_ids",
               "n_text_terms", "n_schema_fields", "n_schema_fields_shared", "flags"]
NEIGHBOUR_FIELDS = ["unit", "signal", "rank", "neighbour", "neighbour_name", "score", "shared_fields"]


def normalise_field(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


GEOMETRY_TYPES = {"Point", "Location", "MultiPoint", "Line", "MultiLine", "Polygon", "MultiPolygon"}
COORDINATE = re.compile(r"^(lat|latitude|lon|lng|long|longitude)$|^location_(address|city|state|zip)$")


def schema_fields(field_names, datatypes):
    """Normalised column field names that say something about content. Dropped:
    Socrata's `:@computed_region_*` columns (added to every point dataset),
    geometry columns and bare coordinates. They only say "has a location", and
    left in they made every mapped dataset look alike. Address, ward and
    neighbourhood columns stay: they are join keys."""
    fields = set()
    for f, t in zip(field_names, datatypes):
        name = normalise_field(f)
        if f.startswith(":") or t in GEOMETRY_TYPES or COORDINATE.match(name) or not name:
            continue
        fields.add(name)
    return fields


def clean_text(s):
    s = re.sub(r"<[^>]+>|https?://\S+", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


def build_units(raw, inventory):
    """One unit per real dataset, or per series. A series is represented by its most
    recently updated member for text, and by the union of members' columns for schema."""
    by_id = {a["resource"]["id"]: a for a in raw}
    groups = {}
    for r in inventory:
        if r["role"] != "candidate":
            continue
        groups.setdefault(r["series_key"] or r["id"], []).append(r)
    missing = [r["id"] for g in groups.values() for r in g if r["id"] not in by_id]
    if missing:
        raise RuntimeError(f"{len(missing)} inventory ids not in the raw snapshot, e.g. {missing[:3]}")

    units = []
    for key, members in sorted(groups.items()):
        rep = max(members, key=lambda r: (r["data_updated_at"], r["id"]))
        res, cls = by_id[rep["id"]]["resource"], by_id[rep["id"]]["classification"]
        fields = set()
        for m in members:
            r = by_id[m["id"]]["resource"]
            fields |= schema_fields(r.get("columns_field_name") or [], r.get("columns_datatype") or [])
        units.append({
            "unit": key, "representative_id": rep["id"], "name": rep["name"],
            "category": rep["category"], "n_members": len(members),
            "member_ids": ";".join(sorted(m["id"] for m in members)),
            # Category is left out on purpose: the clusters get compared with it later.
            "text": clean_text(" ".join([res["name"], " ".join(cls.get("domain_tags") or []),
                                         res.get("description") or ""])),
            "fields": sorted(fields),
        })
    return units


def text_matrix(units):
    vec = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=2, max_df=0.5,
                          ngram_range=(1, 2))
    X = vec.fit_transform(u["text"] for u in units)
    return X, None


def schema_matrix(units):
    """IDF-weighted, binary field-name vectors: a shared `row_id` counts for little,
    a shared `neighbourhood_number` for a lot."""
    vec = TfidfVectorizer(analyzer=lambda fields: fields, binary=True, min_df=1)
    X = vec.fit_transform(u["fields"] for u in units)
    return X, dict(zip(vec.get_feature_names_out(), vec.idf_))


def cosine(X):
    S = (X @ X.T).toarray().astype(np.float32)
    np.fill_diagonal(S, 0.0)
    return S


def top_neighbours(S, units, signal, k, idf=None):
    rows = []
    for i, u in enumerate(units):
        order = np.argsort(-S[i], kind="stable")[:k]
        for rank, j in enumerate((j for j in order if S[i, j] > 0), start=1):
            shared = ""
            if idf is not None:
                common = set(u["fields"]) & set(units[j]["fields"])
                shared = ";".join(sorted(common, key=lambda f: (-idf[f], f))[:5])
            rows.append({"unit": u["unit"], "signal": signal, "rank": rank,
                         "neighbour": units[j]["unit"], "neighbour_name": units[j]["name"],
                         "score": round(float(S[i, j]), 4), "shared_fields": shared})
    return rows


def category_agreement(S, units, k=5):
    """Share of each unit's top-k neighbours in its own portal category, against the
    share a random pick would give. Units with no category are skipped (counted)."""
    cats = np.array([u["category"] for u in units])
    hits, chance, used = [], [], 0
    for i in range(len(units)):
        if not cats[i]:
            continue
        nn = [j for j in np.argsort(-S[i], kind="stable")[:k] if S[i, j] > 0]
        if not nn:
            continue
        used += 1
        hits.append(np.mean(cats[nn] == cats[i]))
        chance.append((np.sum(cats == cats[i]) - 1) / (len(units) - 1))
    return {"k": k, "units_scored": used, "same_category_share": round(float(np.mean(hits)), 3),
            "chance_share": round(float(np.mean(chance)), 3)}


def signal_agreement(A, B, k=10):
    iu = np.triu_indices_from(A, 1)
    rho = spearmanr(A[iu], B[iu]).statistic
    jac = []
    for i in range(len(A)):
        a = {j for j in np.argsort(-A[i])[:k] if A[i, j] > 0}
        b = {j for j in np.argsort(-B[i])[:k] if B[i, j] > 0}
        if a and b:
            jac.append(len(a & b) / len(a | b))
    return {"spearman_pairwise": round(float(rho), 3), f"top{k}_jaccard_mean": round(float(np.mean(jac)), 3),
            "units_with_both": len(jac)}


def run(raw, inventory, k=10):
    units = build_units(raw, inventory)
    Xt, _ = text_matrix(units)
    Xs, idf = schema_matrix(units)
    St, Ss = cosine(Xt), cosine(Xs)

    field_df = np.asarray((Xs > 0).sum(axis=0)).ravel()
    df_of = dict(zip(sorted(idf), field_df))  # get_feature_names_out() is sorted
    for i, u in enumerate(units):
        u["n_text_terms"] = int(Xt[i].nnz)
        u["n_schema_fields"] = len(u["fields"])
        u["n_schema_fields_shared"] = sum(1 for f in u["fields"] if df_of[f] > 1)
        flags = []
        if not St[i].any():
            flags.append("text:no_neighbour")
        if not u["fields"]:
            flags.append("schema:no_fields")
        elif not Ss[i].any():
            flags.append("schema:no_shared_field")
        u["flags"] = ";".join(flags)

    neighbours = top_neighbours(St, units, "text", k) + top_neighbours(Ss, units, "schema", k, idf)
    summary = {
        "n_units": len(units),
        "n_series_units": sum(1 for u in units if u["n_members"] > 1),
        "n_member_datasets": sum(u["n_members"] for u in units),
        "text_vocabulary": Xt.shape[1], "schema_fields": Xs.shape[1],
        "flags": {f: sum(1 for u in units if f in u["flags"].split(";"))
                  for f in ("text:no_neighbour", "schema:no_fields", "schema:no_shared_field")},
        "category_agreement": {"text": category_agreement(St, units),
                               "schema": category_agreement(Ss, units)},
        "signal_agreement": signal_agreement(St, Ss),
    }
    return units, neighbours, St, Ss, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw_dir")
    ap.add_argument("--inventory", help="default: data/processed/inventory/<snapshot date>.csv")
    ap.add_argument("--out", default=str(ROOT / "data/processed/similarity"))
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    raw_dir = Path(args.raw_dir)
    inv_path = Path(args.inventory or ROOT / f"data/processed/inventory/{raw_dir.name}.csv")
    with gzip.open(raw_dir / "catalog.json.gz", "rt", encoding="utf-8") as f:
        raw = json.load(f)
    with open(inv_path, newline="", encoding="utf-8") as f:
        inventory = list(csv.DictReader(f))

    units, neighbours, St, Ss, summary = run(raw, inventory, args.k)
    out = Path(args.out) / raw_dir.name
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "units.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=UNIT_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(units)
    with open(out / "neighbours.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=NEIGHBOUR_FIELDS)
        w.writeheader()
        w.writerows(neighbours)
    np.save(out / "text_sim.npy", St)
    np.save(out / "schema_sim.npy", Ss)
    summary = {"snapshot": raw_dir.name, "inventory": str(inv_path.resolve().relative_to(ROOT)), **summary}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    log.info("similarity path=%s %s", out, json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
