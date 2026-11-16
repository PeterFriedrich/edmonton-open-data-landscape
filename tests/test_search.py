"""Guards on catalogue search (`src/search.py`). Vectors are hand-made, so no model is needed."""
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from src import search


def test_rank_orders_by_combined_score_and_column_names_count():
    units = [{"unit": u, "text": t, "fields": f} for u, t, f in [
        ("a", "road maintenance areas", []),
        ("b", "property assessment", ["neighbourhood_name", "assessed_value"]),
        ("c", "graffiti survey", []),
    ]]
    texts = [search.unit_text(u) for u in units]
    tfidf = TfidfVectorizer().fit(texts)
    X = tfidf.transform(texts)
    E = np.eye(3, dtype=np.float32)
    # Embedding favours "a"; TF-IDF on a column name ("neighbourhood") favours "b" enough to win.
    hits = search.rank("neighbourhood assessed value", units, E, np.array([0.6, 0.5, 0], np.float32),
                       tfidf, X, k=2)
    assert [u["unit"] for _, u in hits] == ["b", "a"]
