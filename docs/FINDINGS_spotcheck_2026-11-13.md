# Findings: neighbour spot-check audit, 2026-11-13

One run of `docs/AUDIT_spotcheck.md` (decision audit, `project-audit` skill).
Model: `claude-fable-5-2`, effort `high`. The brief suggested Fable 5.1; the
condition it sets (not the model that built the spot-check, Opus 5.5) holds.

Scope as run: the 2026-10-02 sample (`data/spotcheck/2026-10-02_pairs.csv`,
210 pairs, 20 units) and the 65 labels in the labelling artifact, read on
2026-11-13. **The labels were read, never written.** Every figure below was
computed in this run from the pairs file, the labels, and
`data/processed/similarity/2026-10-02/` and `data/processed/programmes/2026-10-02/`.

## Verdicts

| Level | Verdict | In one line |
|---|---|---|
| L0 the question | CONDITIONAL | Precision on top-5 is a fair gate, but the spec asked for *expected* neighbours, and one "yes" covers two different lists (topic, join). |
| L1 the sample | CONDITIONAL | Good enough to catch a gross failure, reported per stratum. Too small to separate signals closer than about 6 points; programme units are 44% of the catalogue and 15% of the sample. |
| L2 pair construction | **UNSOUND for programme units**, sound for the other 17 | The pairs are raw top-5 lists. The approved design removes same-programme siblings, which are 95–96% of a programme unit's top 5, so the list the site will show for those units is not in the sample. |
| L3 the labels | CONDITIONAL | Outside the graffiti unit there is no "no" at all: 41 yes, 9 unsure. Unsure is unscored and falls unevenly on the signals. The page also shows which signal found each pair, and a running tally. |
| L4 the decision rule | **UNSOUND** | There is no rule: no pass mark for the gate and no margin for choosing a signal. At this n a few points is noise. |
| L5 the code | SOUND | `score` equals the page tally, ids are stable, the sample reproduces. Two small gaps: no label export exists, and the planned export drops the timestamp. |

L2 is unsound only for the 3 sampled programme units (38 pairs), so L3–L5 were
still evaluated for the other 17 units (172 pairs), which sibling removal can't touch.

## What to settle before labelling more pairs

1. **What "Unsure" means** (L3). Either "I can't tell from the titles" stays
   unscored, or it counts as a miss. Decide now, because it changes how the
   remaining 145 pairs get labelled, and it moves the signals more than
   anything else measured so far.
2. **Whether the page should hide the signal badges and the tally** until a
   pair is labelled (L3). A page change only; it touches no labels.
3. **The decision rule** (L4), written down before the next tally is read.
4. The 14 unlabelled same-programme pairs (the Masks unit p011–p019 and
   p185–p188, plus p169) are worth labelling **only as evidence on sibling
   removal** (L2). They can't score what the site will show.

The 131 unlabelled pairs in the 17 non-programme units stay valid once 1–3 are settled.

## L0: is "would a user want this suggested?" the right question? CONDITIONAL

- **Sharpest argument against.** The spec's success check is "a hand-labelled
  sample of ~20 datasets with their **expected** neighbours" (§Outputs). What
  was built labels only what the signals returned. The project's own headline
  failure is a recall failure that this instrument can't see: the graffiti
  survey's top 5 are judged, but nothing records that the two Graffiti Audit
  units should be there. They were found because the owner happened to know
  they exist.
- A precision-only design also makes every new variant cost new labels, since
  only pairs it shares with an old variant are already judged.
- **One "yes" covers two lists.** The page says "same topic, or a sensible
  table to join, both count". The panel shows neighbours and join partners as
  separate lists (spec, §Outputs), and join partners carry "shares a column
  name" until a `distinct` query confirms them. So schema's precision here is
  not a gate on the join list, and a schema-only "yes" can't be told apart
  from a topic "yes".
- **Never measured:** units with an empty or short list. Across the catalogue
  70 units have fewer than 5 schema neighbours and 24 have none; in the sample
  3 units have 0, 1 and 2. Precision ignores an empty list.
- **Condition.** Add a small expected-neighbour probe: for each of the 20
  units, the owner names up to 3 datasets that ought to appear, and each
  variant reports their rank. It needs no pair labels and it is the only
  measure that can compare raw with stripped on the graffiti kind of failure.
- **Would change the verdict:** to SOUND with the probe in place; to UNSOUND
  if the owner decides the neighbour list is for finding things already
  suspected to exist, where recall is the main measure.

## L1: the sample. CONDITIONAL

- **Representation.** Surveys and Census are 423 of 920 units (46%) and 3 of
  20 sampled (15%). Units in a detected programme are 407 of 920 (44%) and
  also 3 of 20. A pooled precision therefore weights the stratum where the
  signals fail at about a third of its catalogue share. That may be right for
  what people look up (nobody knows; there is no usage data), but then the
  number is "precision on a sample tilted toward non-survey units", and it
  should be reported per stratum, which `score` doesn't do.
- **23 categories holding 86 units** can't be drawn by the category stratum
  (it takes the 13 largest after Surveys, Census and uncategorised).
- **The series stratum drew the same family twice:** both units are Council
  and Committee Meetings, and one is the other's first text neighbour (p043).
  The pool has 40 units, 14 of them in City Administration. The sample holds
  19 topics, not 20.
- **One draw.** Seeds 1, 2 and 3 share 3, 1 and 0 units with seed 0.
- **Interval at the current n** (65 labels; unit-level bootstrap, unsure dropped):

  | Signal | Yes / judged | Units | 95% interval |
  |---|---|---|---|
  | text | 28 / 33 = 85% | 8 | 56–100% |
  | schema | 19 / 23 = 83% | 7 | 52–100% |
  | embed | 20 / 23 = 87% | 8 | 61–100% |

  The three intervals are the same interval. All 12 "no" labels sit in one unit.
- **Interval expected with all 210 labelled** (simulation: 20 units × 5,
  precision 85–95% outside two failing units, the two signals sharing 54 of
  100 slots as text and embed do): one signal's precision ±6 to ±9 points; the
  difference between two equally good signals lands within ±4 to ±6 points 95%
  of the time. The unit-to-unit spread in that simulation is assumed, because
  the labels can't estimate it yet.
- **Sharpest argument against:** text and embed differ on only 46 slots each.
  The whole TF-IDF-vs-embeddings choice rests on those 92 pairs, 25 of them
  labelled.
- **Condition.** Use the sample as a gross-failure gate, per stratum. Don't
  read a pooled difference under about 6 points as a result.
- **Would change the verdict:** a second draw (another seed) giving the same
  per-stratum picture would make it SOUND for the gate. Separating signals
  3 points apart would take roughly four times the units.

## L2: pair construction. UNSOUND for programme units; sound for the rest

- **What holds.** Every unit has exactly 5 text and 5 embed neighbours at
  ranks 1–5; a pair found by two signals is one row and counts for both
  (`test_shared_neighbour_is_one_pair_with_both_ranks`); `extend` kept
  p001–p165. Text against embed is a fair comparison on the same units and k.
- **What doesn't.** `docs/DECISIONS.md` 2026-11-03 approved that
  "same-programme siblings leave the neighbour list", and rejected leaving
  them in. The sample was drawn before that, from raw top-5 lists:
  - 37 of 210 pairs are same-programme, all in 3 units (Graffiti 15 of 15,
    Masks 13 of 13, Census 9 of 10).
  - Across the catalogue, 95% (text), 96% (schema) and 96% (embed) of the
    top-5 slots of the 407 programme units are siblings. For 346, 337 and 356
    of those units the whole stored top 10 is siblings.
  - With siblings removed, the top 5 of the three sampled programme units
    (text and embed, 30 slots) contains 2 pairs that are in the sample.
  So for 44% of the catalogue the sample scores a list the owner has already
  decided not to show, and holds almost none of the list that will be shown.
- **The plan in `TODO.md` under-counts the relabelling.** Step (3) says to
  "label only the pairs [the stripped variants] newly surface". With siblings
  removed, the *raw* arms surface new pairs too, so all four arms need a fresh
  draw for programme units. The raw-vs-stripped axis is then decided on 3 units.
- **The labels already collected argue against removing every sibling.** Of
  the 23 labelled sibling pairs, 10 are "yes": 9 of 9 on the Census unit, and
  p007 and p199 on Graffiti. Removal takes out all 9 Census neighbours the
  owner judged good. `TODO.md` expects the same on the Masks unit (p185, p186).
- **Removal alone doesn't fix the graffiti case.** Computed from the stored
  matrices with siblings removed: the Graffiti Audit units move from rank
  ~295 to 14–15 (text) and 12–21 (embed), still outside the top 5. The slots
  above them go to surveys the detection doesn't catch ("… - Insight
  Community", "… - Edmonton Insight Survey", "Measuring Progress
  Questionnaire - …"). The Census unit's text list falls to scores of 0.07–0.10
  by slot 3 (General Building Permits, Per Capita Water Consumption); embed
  finds the 2016 Federal Census dwelling tables.
- **Fix.** Decide the open owner question (c), how neighbours are treated
  before scoring, then draw programme-unit pairs after sibling removal for
  every arm. Keep the existing sibling labels as the evidence for whether
  removal should be total, by programme, or a ranking inside "where it sits".
- **Would change the verdict:** SOUND if siblings stay in the neighbour list
  after all (reopening 2026-11-03), since the raw lists are then what is shown.

## L3: the labels. CONDITIONAL

- **Unsure is doing the work of "no" outside programmes.** The 65 labels are
  43 yes, 12 no, 10 unsure. All 12 "no" are on the Graffiti unit, all for
  siblings. The other 50 labels are 41 yes, 0 no, 9 unsure. So outside one
  unit every signal scores 100%, and every non-programme pair the owner did
  not accept is unscored. This is an inference from the pattern; no pair was
  re-judged in this run.
- **It falls unevenly on the signals:**

  | Signal | Unsure / labelled | Unsure dropped | Unsure = no | Unsure = yes |
  |---|---|---|---|---|
  | text | 4 / 37 | 85% | 76% | 86% |
  | schema | 5 / 28 | 83% | 68% | 86% |
  | embed | 1 / 24 | 87% | 83% | 88% |

  The spread between signals is 4 points with unsure dropped and 15 with
  unsure counted as a miss. The 2026-10-16 rule made exactly this argument
  ("unsure pairs are left out of precision, so marking programme siblings
  unsure would hide exactly the cases where the signals match on boilerplate")
  but applied it only to programme siblings.
- **Argument for counting it as a miss:** a visitor sees the neighbour list as
  titles too. If the owner can't tell from the titles why a dataset is
  suggested, neither can they.
- **The labeller isn't blind.** Each row shows which signal found the pair,
  its rank and its score, text pairs first, and the sticky bar shows a running
  "Text yes / Columns yes / Meaning yes" tally. The tally is also not
  comparable while labelling is partial: embed's 23 judged pairs come from a
  different mix of units than text's 33.
- **The tag.** All 65 labels predate it (50 on 2026-10-02, 15 on 2026-10-16;
  the tag went live 2026-11-03). No pair has a label from both conditions, so
  its effect can't be measured from the data, and only 14 tagged pairs remain
  unlabelled. Under the L2 fix those pairs stop counting toward signal
  precision, which makes the question moot.
- **The Census "yes" labels are consistent with the rule**: it says a sibling
  *alone* is "no", and those 9 are the same table at another geography or
  year. They conflict with sibling removal, not with the labelling rule (L2).
- **One labeller, one pass.** Nothing measures how repeatable a verdict is.
  Four labels (p001, p005, p008, p198) were written by a session at the
  owner's request on 2026-10-16 (handoff 2026-10-30); their timestamps are
  the round `04:30:00.000Z`.
- **Conditions.** (1) Settle unsure, and have `score` report both bounds
  either way. (2) Hide provenance and the tally while labelling. (3) Re-label
  about 20 already-labelled pairs blind, a few weeks apart, as a repeatability check.
- **Would change the verdict:** UNSOUND if the owner confirms the 9 unsure
  pairs are misses and the scoring stays as it is; SOUND once (1) and (2) are done.

## L4: the decision rule. UNSOUND

- **There isn't one.** The spec says the sample is "scored before any
  neighbour output is shown": a score, with no pass mark. `TODO.md` says to
  "keep whichever lifts text precision on the labelled pairs": any lift, with
  no margin. `docs/DECISIONS.md` has no row on either.
- **At this n the margin matters.** Two equally good signals differ by up to
  4–6 points by chance (L1), the choice of unsure treatment moves the gap by
  11 points (L3), and there are four arms, with the stripped ones labelled
  later and knowingly. Without a rule set first, any outcome can be read as a win.
- **Fix: write the rule before the next tally is read**, as a `DECISIONS.md`
  row. A draft for the owner to edit:
  - *Gate*, per stratum, unsure counted as the owner decides in L3: a signal's
    list is shown only if precision is at least X and at most N of the 20
    units have no good neighbour. The owner picks X and N now.
  - *Choice*: TF-IDF is the default, since it needs no model download. Switch
    to embeddings only if they win by at least 10 points on precision or on
    the expected-neighbour probe (L0); otherwise keep TF-IDF.
- **Would change the verdict:** SOUND once a row exists that states a margin
  wider than the noise band.

## L5: the code. SOUND

- **`score` matches the page.** On the 65 labels both give text 85% of 33,
  schema 83% of 23, embed 87% of 23.
- **Ids are stable.** Re-running `sample` (seed 0) and then `extend` on
  `data/processed/similarity/2026-10-02/` reproduces all 210 rows: ids, units,
  neighbours and ranks. The page's `PAIRS` equals the CSV field for field (the
  page groups extended pairs under their unit; the ids don't change).
- **Gap: no export exists.** Nothing in `src/`, `scripts/` or `tools/` writes
  a labels file, and none was ever committed. The artifact's `labels`
  collection is the only copy. The planned format (`pair_id,verdict`) drops
  `at`, which is the only thing that separates labels made before and after
  the rule and the tag.
- **Gap: a unit whose judged pairs are all unsure** has no entry in
  `per_unit`, so it isn't counted in `units_with_no_good_neighbour`. No unit
  is in that state today.
- `score` reports pooled figures only (L1 asks for per stratum).

## What this run got wrong

- **The first interval was wrong.** I started from a design-effect estimate
  (about ±14 points per signal, ±10 for a difference). It ignored that text
  and embed share 54 of their 100 slots, which cancels in the difference. The
  simulation gave ±6–9 and ±4–6. That figure still rests on an assumed
  unit-to-unit spread, so treat "about 6 points" as the right size, not a measurement.
- **I nearly reported the 9 Census "yes" labels as breaking the 2026-10-16
  rule.** The row's body says a sibling *alone* is "no". Reading only the
  bolded part of the row would have published a finding the repo had already decided.
- **I nearly told the owner not to label the Masks unit.** Those labels can't
  score the shown list, but they are the evidence on whether sibling removal
  is right, and `TODO.md` already says the owner judges siblings for that reason.
- **"Unsure means no" is an inference.** It rests on 0 "no" against 9 unsure
  outside the Graffiti unit. I opened no portal page and re-judged no pair,
  so some of the 9 may be honest can't-tells.
- **Not checked:** that stripping boilerplate leaves the 17 non-programme
  units' lists nearly unchanged (asserted; the variant isn't built); how
  repeatable the owner's verdicts are; the schema signal after sibling removal.
- **Negative claims, and how each was checked.** "No export exists": found the
  reader (`score` takes a labels CSV) and no writer, and `git log --all` shows
  no labels file ever committed. "No decision rule": read every
  `DECISIONS.md` row in full and searched the spec, `TODO.md` and the archive
  for a threshold. "No 'no' outside Graffiti": counted from the labels.
- **Token hygiene.** Reading the artifact returned much of the page's `PAIRS`
  constant into the session. The brief says to summarise the pairs, not read
  them; the page copy should have gone straight to a file.
- **Model.** The run was queued for Fable 5.1 and ran on `claude-fable-5-2`.
