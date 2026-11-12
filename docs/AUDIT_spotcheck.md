# Audit brief: the neighbour spot-check

A reusable, read-cold instrument for a **decision audit** (`project-audit` skill,
family (a)). It holds the grounding order and the questions, never the findings.
Findings go in `docs/FINDINGS_spotcheck_<date>.md`, which must end with a
non-empty `What this run got wrong` section, plus a row in `docs/AUDIT_LEDGER.md`.

**Why this target first:** the spot-check is the gate on whether any neighbour
list is shown (spec, Outputs), and it decides TF-IDF vs embeddings
(`TODO.md` text-signal variants item). Labelling is part-done (65 of 210 on
2026-10-16), so a design flaw found now costs only the remaining labels; found
after scoring, it costs all of them.

**Run it on a different model from the one that built it** (built on Opus 5.5).
Suggested: Fable 5.1 (`/model claude-fable-5-1`). Record the model in the ledger row.

## Grounding order (read before writing any finding)

1. `docs/AUDIT_LEDGER.md` and `docs/ASSUMPTIONS.md` (known premises aren't new findings).
2. The latest `session-summary/` file.
3. `docs/SPEC_landscape.md` §Outputs (the spot-check gate, the programme section).
4. **Full bodies** of every `docs/DECISIONS.md` row on the spot-check, signals,
   embeddings or programmes: at least 2026-10-02 (embeddings), 2026-10-16
   (labelling rule) and 2026-11-03 (programmes). Don't truncate them.
5. `TODO.md` items: spot-check, text-signal variants, programme detection.
6. `src/spotcheck.py` (`STRATA`, `pick_units`, `build_pairs`, `extend`, `score`)
   and `tests/test_spotcheck.py`.
7. `data/spotcheck/2026-10-02_pairs.csv`, through a short python summary, not `Read`.
8. The labels: the labelling artifact's `labels` collection
   (https://claude.ai/artifact/Ts8cWLqtyQCGJMkkm4SYaA; read them with `ArtifactData`, not by writing).
   **Read-only. Never write labels during an audit.**

## Decision stack (evaluate top-down; an UNSOUND level makes the ones below moot)

- **L0: Is "would a user want this suggested?" the right question?** Is precision
  on top-5 neighbours what the site needs, or should coverage, join usefulness
  or recall-like measures count? What would a user see that this never measures?
- **L1: The sample.** 20 units over strata `Surveys 2, Census 1, (none) 2,
  series 2, one per next 13 categories`. Does it represent what users will look
  up? Is 20 units (210 pairs, correlated within a unit) enough to separate
  signals whose precision may differ by a few points? Report the interval you'd
  expect at the current n, per signal.
- **L2: Pair construction.** Pairs are de-duplicated across signals and `extend`
  adds embed pairs later. Is the comparison fair between signals (the same
  units, the same k, pairs seen once)? Does a pair found by two signals count
  for both?
- **L3: The labels.** One labeller; "unsure" is unscored; the 2026-10-16 rule
  says a same-programme sibling alone is "no"; since 2026-11-03 the page shows
  a same-programme tag. Does any of these bias one signal over another? (The
  embed signal and TF-IDF both favour programme siblings, perhaps unequally.)
  Does showing the tag change verdicts compared with the 65 labels made without it?
- **L4: The decision rule.** The planned choice is across {TF-IDF, embed} ×
  {raw, stripped}. What difference is big enough to act on at this n? Is
  there a stated threshold, and should there be one before scoring?
- **L5: The code.** Does `score` compute what the page's tally shows? Are
  ids stable across `extend`? Are the labels exported without loss?

For each level: SOUND / CONDITIONAL / UNSOUND, the sharpest argument against it,
and the evidence that would change the verdict.

## Out of scope

The similarity signals' own code (`src/similarity.py`, `src/embeddings.py`)
except where it changes what the spot-check measures, and programme detection
except as it affects labelling (it has its own ledger candidate).
