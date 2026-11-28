# Findings: text length, boilerplate and hubness in the neighbour lists (2026-11-28)

**Question.** Units carry very different amounts of text and columns. Does that skew who
shows up in a unit's neighbour list? Do the standard fixes help on the labelled pairs?

**Data.** The 2026-10-02 snapshot: 920 units, its committed TF-IDF and embedding matrices,
and the 210 labelled pairs (`data/spotcheck/2026-10-02_*`).

**Literature and industry practice.** Notes are outside the repo, in
`research/edmonton-open-data-landscape/text_length_hubness_lit_2026-11-28.md`. They were
taken from search-result summaries, not the full papers.

**Status.** Measured. The precision result is **not settled**: 30 of the new pairs are
unlabelled (§4).

## 1. How uneven the inputs are
- **Text terms per unit** (TF-IDF vocabulary hits): median 80, 10th percentile 13, maximum
  485. 63 units have 10 or fewer.
- **Schema fields:** median 12, range 0–545. 11 units have none.
- **Boilerplate:** a sentence (digits folded) that appears in more than 3 units, the same
  ≤ 3 rule as the text variants (`RARE_TEXT_MAX_UNITS`).
  - 480 of 920 units contain some.
  - Removing it takes the median unit text from 92 words to 23.
  - Census and Insight Community descriptions are mostly boilerplate.

## 2. Hubness and the length lean, per method
k-skewness is the skew of how often each unit appears in other units' top 5. Higher means
a few hubs dominate. Nielsen & Hansen (2024) saw hubness reduction help every model above 3.

| Variant | k-skew | Biggest hub | Never in a top 5 | Times in others' top 5: ≤10 terms → 118+ terms |
|---|---|---|---|---|
| TF-IDF (current) | 3.01 | 42 | 9 | 4.8 → 4.1 |
| BM25, b=0.75 | 0.71 | 17 | 36 | 2.0 → 5.3 |
| BM25, b=0.3 | 1.14 | 26 | 49 | 1.5 → 7.0 |
| BM25, b=0 | 4.70 | 63 | 71 | 1.0 → 10.6 |
| BM25, b=0.3, boilerplate stripped | 2.72 | 48 | 66 | 1.8 → 7.0 |
| Embed (current) | 6.05 | 85 | 87 | 3.1 → 6.7 |
| Embed, boilerplate stripped | 1.95 | 32 | 54 | 3.0 → 6.4 |
| Embed, CSLS (k=10) | 1.20 | 21 | 11 | 4.5 → 5.0 |
| Embed, stripped + CSLS | 0.95 | 19 | 6 | 4.5 → 4.8 |
| RRF(TF-IDF, embed), k=60 | 4.49 | 66 | 65 | 3.4 → 5.2 |
| RRF(BM25 b=0.3, embed stripped) | 1.67 | 30 | 69 | 2.1 → 6.9 |

- **TF-IDF cosine already ignores length.** Units of every length turn up about equally
  often.
- **BM25, the industry default, leans toward long texts here.** That's at every `b` tried.
  As a more-like-this query, a long unit matches more of every other unit's terms.
- **Stripping boilerplate breaks up the embedding hubs** (k-skew 6.05 → 1.95). Long texts
  still appear twice as often as short ones, so **the length lean is not only boilerplate**.
- **CSLS removes the length lean.** It's a one-line rescoring that subtracts each
  candidate's mean similarity to its own 10 nearest neighbours. Under it:
  - units of every length turn up 4.5–5.0 times;
  - units in no top 5 fall from 87 to 11;
  - the biggest hub falls from 85 to 21.

## 3. The labelled pairs
- **Precision** = labelled yes ÷ labelled pairs in the top 5, with unsure counted as a miss.
- **Known-yes** = how many of the 128 yes pairs (17 units) each variant keeps in its top 5.
  Its ceiling is 85, five per unit.
- **Short** = the 7 sampled units with 25 or fewer text terms.

| Variant | Labelled (17 units) | Precision (17) | Known-yes kept | Labelled, short units | Precision, short units |
|---|---|---|---|---|---|
| TF-IDF (current) | 85/85 | 0.859 | 73 | 35/35 | 0.743 |
| BM25, b=0.75 | 64/85 | 0.859 | 55 | 23/35 | 0.696 |
| Embed (current) | 85/85 | 0.918 | 78 | 35/35 | 0.857 |
| Embed, stripped | 73/85 | 0.945 | 69 | 25/35 | 0.920 |
| Embed, CSLS | 74/85 | 0.946 | 70 | 29/35 | 0.931 |
| Embed, stripped + CSLS | 73/85 | 0.945 | 69 | 27/35 | 0.926 |
| RRF(TF-IDF, embed) | 77/85 | 0.935 | 72 | 29/35 | 0.862 |

- **The current rows reproduce the locked tally** (73/85 and 78/85, `docs/DECISIONS.md`
  2026-11-20). So the scoring matches the one `spotcheck score` uses.
- **Every new variant scores higher on the pairs that are labelled, short units most of
  all** (embed 0.857 → 0.93).
- **But the comparison is biased toward the current methods.** All 210 labels were drawn from
  the current TF-IDF, schema and embed lists. A current method has every pair labelled, so
  any pair a new variant drops is a known pair it lost. A pair it adds is unlabelled and
  doesn't count. That's why "known-yes kept" falls for every variant, and it **can't be read
  as a loss** until the new pairs are labelled.

## 4. What would settle it
- **Label 30 pairs:** the union of the new top-5 pairs from the three embedding variants on
  the 20 sampled units. 17 are from stripped, 15 from CSLS, 17 from stripped + CSLS, with
  overlap.
- **Then score precision on full top-5 lists**, as the spot-check did, against the 70% /
  3-unit gate.
- **Run the expected-neighbour probe** with each variant as well. It doesn't depend on
  which lists the labels came from, so it is the fairer test of the length lean.

## 5. What this does not show
- **One draw of 20 units**, 7 of them short. That's about ±6–9 points per signal
  (2026-11-20 row).
- **CSLS was tested at k=10 only.** Mutual proximity and f-norm (the paper's best) were not
  tried. Nor was BM25 with each field (title, tags, description) scored separately, which is
  how search engines use it.
- **The boilerplate rule is one rule** (exact sentences, digits folded, > 3 units). A
  near-duplicate rule would remove more.

## Reproduce
- Scripts: `tools/lenexp/build.py` and `tools/lenexp/evaluate.py`, run from the repo root
  with an output folder as the one argument (outputs are not committed).
- `build.py` builds the BM25 matrices and the stripped embeddings: about 90 s at batch 16,
  ~1 GB.
- `evaluate.py` prints both tables.
