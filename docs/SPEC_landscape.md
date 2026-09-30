# SPEC — Edmonton Open Data Landscape

Starter spec, 2026-09-30. Candidates to test, not commitments — nothing here is
locked until it has a row in `docs/DECISIONS.md`.

## Purpose

Map the structure of Edmonton's open data catalogue as a whole, so datasets can
be explored by how they relate to each other rather than one at a time.

- **In scope:** similarity between datasets, metrics across the catalogue, and
  the meta-structure (clusters, gaps, links).
- **Non-goal:** replicating the City's own per-dataset exploration tools (e.g.
  311 Explorer, the portal's built-in previews).

## Core questions

1. Which datasets are most alike, and by what measure (topic, schema, geography,
   time coverage)?
2. What clusters emerge, and how do they compare with the portal's own categories?
3. Where is the catalogue dense or sparse, and what looks missing?
   *Needs an external reference — see pitfall 7.*
4. How are size, update frequency, age and column counts distributed?
5. Which datasets share fields or keys, and so could be joined?
6. How does the catalogue change over time (additions, removals, updates)?

## Data sources

data.edmonton.ca (Socrata): SODA API plus catalogue metadata.

- **Pull:** name, description, category, tags, column names and types, row
  counts, update frequency, created/updated dates, licence.
- **Snapshots:** store each harvest with its date. The catalogue API keeps no
  history, so an unsnapshotted week is lost for good.
- **Attribution:** Open Government Licence – City of Edmonton; confirm exact
  terms and wording before publishing.
- **Status:** unofficial; built on City of Edmonton open data, not affiliated
  with the City.

## Harvest pitfalls (from spec review — confirm in milestone 1)

Based on general Socrata knowledge, not yet checked against this portal.

1. **Catalogue ≠ datasets.** Filtered views, maps, charts, stories and external
   links sit alongside the datasets they come from. Derived views share their
   parent's columns and description, so they would dominate nearest-neighbour
   results. Filter by asset type and link each view to its parent before any
   similarity work.
2. **Yearly series** ("Property Assessment 2019 / 2020 / …") form trivial tight
   clusters. Collapse to one entry per series, or flag them.
3. **Field locations.** The Discovery API (`api.us.socrata.com/api/catalog/v1`)
   likely carries name, description, category, tags, columns and dates, but not
   row counts — those need `/api/views/{id}.json` or a SODA `count(*)` per
   dataset. "Update frequency" is a publisher-entered custom field: treat it as
   *claimed*, and measure *actual* frequency from snapshots.
4. **Column summaries as a middle ground.** The views API often exposes
   per-column summaries (null counts, min/max, top values). That gives time
   coverage and cheap join-key value overlap without pulling rows.
5. **Generic column names** (`id`, `latitude`, `longitude`, `location`, `year`)
   swamp schema similarity. Weight rare columns up (IDF-style). A shared name is
   not a shared key — only value overlap (pitfall 4) separates the two.
6. **Geographic coverage** is rarely in the metadata and almost everything is
   city-wide. Infer the spatial unit from columns (point, polygon, neighbourhood,
   ward) instead — that is what decides joinability anyway.
7. **"What's missing" needs a reference**: another city's catalogue (Calgary also
   runs Socrata) or a standard list of expected municipal datasets. So the
   city-comparison work is a dependency of core question 3, not a side project.
8. **Small n.** Likely hundreds to low thousands of real datasets once views are
   removed. A small local embedding model runs fine on the ARM CPU; cluster
   quality metrics will be noisy, so agreement with portal categories (ARI/NMI)
   is the more honest measure than silhouette.

## Approach

Metadata first (no row-level data); build several similarity signals, then
combine and compare them.

1. Text similarity: embed titles, descriptions and tags.
2. Schema similarity: IDF-weighted overlap in column names and types.
3. Operational metrics: size, claimed vs. measured update frequency, age,
   column counts.
4. Coverage: time extent from date-column min/max; spatial unit from columns.
5. Structure: cluster on the signals, build a graph (datasets as nodes,
   similarity or shared fields as edges), compare with portal categories.

## Outputs

- **Landscape view:** 2D map of all datasets, coloured by cluster.
- **Graph view:** datasets linked by similarity or shared fields.
- **Metrics view:** distributions of size, freshness, age, schema width.
- **Neighbours:** closest relatives of any dataset — a lookup into the
  landscape, not a replacement for the City's tools.
- **Change log:** added / removed / updated between snapshots.

Notebooks first; a shareable static site later. Keep outputs as data files so a
site can read them.

## Scope and naming

- Name `edmonton-open-data-landscape`: no conflicts on PyPI, npm or web search;
  GitHub name search still to do.
- Edmonton only for now. City comparison expected to stay small; if it grows,
  split into its own project rather than renaming this one.

## Tech stack

Python; requests (Socrata), pandas, scikit-learn, a sentence-embedding model,
networkx. Storage: dated snapshot files (gzipped JSON raw, Parquet derived).
Front end undecided; notebooks first.

## Milestones

1a. Harvest a first catalogue metadata snapshot.
1b. Inventory by asset type; parent/derived and series de-duplication.
2. Descriptive metrics and an exploratory notebook.
3. Similarity signals and clustering.
4. Graph and landscape visualisation.
5. Scheduled snapshots to track change over time.
6. Publish, with attribution and an unofficial-status note.

## Open questions (with proposed answers — not locked)

| Question | Proposal |
|---|---|
| Metadata only, or sample rows? | Metadata + column summaries (pitfall 4); rows only when a specific question needs them. |
| Text vs. schema similarity, or weighted? | Keep separate first; report where they disagree (same topic/different schema and vice versa) — that is a finding. Weight later. |
| Snapshot cadence? | Weekly; gzipped, committed to the repo. |
| Notebooks or static site? | Notebooks through milestone 4; outputs as data files. |
| Where does city comparison live, when does it split? | Minimal reference catalogue here for core question 3; split if it grows past that. |
| Licence wording? | Confirm on the portal before publishing. |
| GitHub name conflicts? | To check. |
