"""Guards on the M3b clustering (`src/clustering.py`).

Every unit gets exactly one cluster per signal. Agreement with categories is
reported again without dominant categories, which otherwise inflated ARI from
~0.25 to ~0.88. The ARI interval comes from subsets without replacement:
resampling with replacement pushed ARI's interval above the point value.
"""
import numpy as np

from src import clustering as cl


def blocks(sizes, categories, noise=0.05, seed=0):
    """Similarity matrix with one tight block per group, plus unit dicts."""
    rng = np.random.default_rng(seed)
    labels = np.repeat(np.arange(len(sizes)), sizes)
    S = np.where(labels[:, None] == labels[None, :], 0.8, 0.05) + rng.uniform(0, noise, (len(labels),) * 2)
    S = ((S + S.T) / 2).astype(np.float32)
    np.fill_diagonal(S, 0)
    units = [{"unit": f"u{i}", "name": f"Dataset {i}", "category": categories[l]} for i, l in enumerate(labels)]
    return units, {"text": S, "schema": S.copy()}


def test_every_unit_gets_one_cluster_per_signal():
    units, sims = blocks([6, 5, 4], ["A", "B", "C"])
    assignments, clusters, _ = cl.run(units, sims, k=3, n_boot=20, n_sub=3)
    assert [a["unit"] for a in assignments] == [u["unit"] for u in units]
    for signal in cl.SIGNALS:
        assert all(isinstance(a[f"cluster_{signal}"], int) for a in assignments)
        assert sum(c["size"] for c in clusters if c["signal"] == signal) == len(units)


def test_dominant_categories_are_reported_separately():
    units, sims = blocks([30, 3, 3, 3], ["Big", "B", "C", "D"])
    _, _, summary = cl.run(units, sims, k=4, n_boot=20, n_sub=3)
    assert summary["dominant_categories"] == {"Big": 30}
    text = summary["signals"]["text"]
    assert text["all_categorised"]["n"] == 39
    assert text["without_dominant"]["n"] == 9


def test_ari_interval_brackets_the_point_value():
    # Many small clusters, two per category: the shape where resampling WITH
    # replacement put the whole interval above the value (0.604 vs [0.631, 0.683]).
    units, sims = blocks([5] * 40, [f"c{i // 2}" for i in range(40)])
    _, _, summary = cl.run(units, sims, k=40, n_boot=200, n_sub=2)
    m = summary["signals"]["text"]["all_categorised"]
    lo, hi = m["ari_ci95"]
    assert lo <= m["ari"] <= hi, m


def test_uncategorised_units_are_counted_not_scored():
    units, sims = blocks([5, 5], ["A", ""])
    _, _, summary = cl.run(units, sims, k=2, n_boot=20, n_sub=3)
    assert summary["uncategorised_units"] == 5
    assert summary["signals"]["text"]["all_categorised"]["n"] == 5
