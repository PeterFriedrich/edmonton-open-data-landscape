# Data Sources

Reference for raw input files. Update this file when you discover column name
quirks, encoding issues, or anything unexpected. Do not rely on memory — write it
down here. A defect in the *publisher's* data goes in `docs/DATA_ISSUES.md`,
with a status saying whether they have been told.

**Download completeness:** an API that pages or caps (`$limit` on Socrata, for
instance) truncates *silently* — it returns exactly that many rows with no
error. Every downloader verifies its row count against the live server count
and fails hard on a mismatch.

**Vintage:** record, per source, the dataset id, the retrieval timestamp and
the publisher's own last-updated stamp. A guard must measure the DATA (row
counts, max date in the file), never a metadata string that can go stale
while the guard stays green.

## Sources

### data.edmonton.ca catalogue metadata (Socrata)
- **Publisher / URL:** City of Edmonton, https://data.edmonton.ca. Two endpoints:
  Discovery API `https://api.us.socrata.com/api/catalog/v1?domains=data.edmonton.ca`
  (paged with `limit`/`offset`), and per asset `https://data.edmonton.ca/api/views/{id}.json`.
- **Retrieved:** first full listing **2026-10-02 04:31–04:32 UTC**, by
  `python -m src.harvest`: 21 pages × 100, 2088 unique ids = `resultSetSize`, no
  duplicates, no app token. Raw: private repo
  `PeterFriedrich/edmonton-open-data-landscape-snapshots`, `2026-10-02/` (cloned at
  `data/raw/private-snapshots/`). Public reduced copy: `data/snapshots/2026-10-02/`.
  The manifest's `code_sha` is the master commit the harvester branch started from;
  the harvester itself was not yet committed. Earlier probe (2026-10-01, 1 Discovery
  page + 3 views calls) is kept locally in `data/raw/probe_2026-10-01/`.
- **Size:** raw listing 1.72 MB gzipped (~14 MB raw); reduced public copy 0.67 MB
  gzipped. Weekly that is ~90 MB/yr private and ~35 MB/yr public. Views responses
  (not harvested) were 5–56 KB each in the probe.
- **Retention (proposed):** keep every weekly snapshot in both repos; revisit if
  the private repo passes 1 GB.
- **Wayback Machine:** the CDX index has **no captures** of
  `data.edmonton.ca/data.json` (checked 2026-10-02, any status). No pre-project
  history to backfill from that source.

**Whole-catalogue survey (2026-10-02 snapshot, 2088 assets):**
- **Types:** dataset 1421, map 279, chart 179, filter 108, story 61, href 21,
  file 18, calendar 1. Columns only on datasets (1421) and filters (108).
- **Parents:** 606 assets have `parent_fxf` (19 have more than one); no dataset
  has one. 31 parent ids are not in the listing (private or deleted parents).
- **`provenance`:** all 2088 are `official`. The Discovery API may leave out
  community assets by default; unchecked (M1c).
- **Licence (`metadata.license`):** "See Terms of Use" 1873, none 203, "Canada
  Open Government Licence" 12. 75 descriptions mention a licence.
- **Attribution:** City of Edmonton 1389, none 469, EPCOR 72, Statistics Canada 31,
  Alberta Health Services 24, Environment Canada 11, others.
- **Categories:** Surveys 463, Vehicle Speed 341, Census 212, none 174, City
  Administration 131, Externally Sourced Datasets 107, … The three biggest look
  like yearly/per-site series (pitfall 2), so the "real dataset" count will be far
  below 1421 once M1c collapses series.
- **Custom-field fill (of 2088):** Update Frequency 2008, Automated or Manual
  1829, Primary Dataset or View 1820, Duplicates Removed 1716, Verified for
  Accuracy 1713, Internal or External 1440, Purpose 1169, Period of Coverage
  1105, Coordinate System 953, Date Made Public 853, KPI Field 2 309, Date
  Updated 264, Dataset Dependencies 199, Datum 196, Job Scheduling 138, Date
  Created 112, plus rare story/admin keys.
- **Claimed update frequency:** Not Updated (Historical Only) 1025, Weekly 373,
  When Necessary 210 (+14 "When necessary"), Daily 155, Monthly 74, Annually 73
  (+19 "Annual"), X times per day 24, Hourly 22, Quarterly 9, Near Real-Time 7,
  Bi-Weekly 2.
- **Actual data updates (datasets, `data_updated_at`):** 438 within 7 days, 439
  within 14, 450 within 30, 552 within 365. The frequent updaters are a stable
  set of ~440.
- **Columns per dataset:** median 17, mean 20.8, none empty.

**Quirks (full listing):**
- **Custom-field values are inconsistent:** trailing spaces ("Internal " 198 vs
  "Internal" 175), synonyms ("Internally Sourced Data " vs "Internal", "Annual" vs
  "Annually"), case ("When Necessary"/"When necessary"), and a stray key
  `Quality-Indicators_Verified-for-Accuracy?`. Normalise in M1c; never compare
  raw strings.
- **The reduced public copy drops** custom keys outside its allow-list
  (`src/reduce_snapshot.py`); its manifest counts each one. Date Made Public /
  Date Updated / Date Created are factual and could be added to the allow-list.

**Where each field lives** (corrects spec pitfall 3). Discovery, `resource.*`
unless noted:

| Need | Discovery API | `/api/views/{id}.json` |
|---|---|---|
| name, description, attribution | `name`, `description`, `attribution` | `name`, `description` |
| category / tags | `classification.domain_category`, `.domain_tags` (`categories`/`tags` empty) | `category`, `tags` |
| columns | `columns_field_name` / `_name` / `_datatype` / `_description` / `_format` | `columns[]` |
| data / metadata updated | `data_updated_at`, `metadata_updated_at` (ISO) | `rowsUpdatedAt`, `viewLastModified` (epoch s) |
| created / published | `createdAt`, `publication_date` | `createdAt`, `publicationDate` |
| parent of a derived view | `parent_fxf` (list; 37 of 100 non-empty on p0) | `modifyingViewUid` (`parentUid` was null) |
| licence | `metadata.license` | `license.name`, `licenseId` |
| custom fields | `classification.domain_metadata` (flat `Section_Key` pairs) | `metadata.custom_fields` (nested) |
| usage | `page_views.*`, `download_count` | `viewCount`, `downloadCount` |
| **row count** | **absent** | **no field**; `cachedContents.count` on a column (e.g. `row_id` = 247010) |
| column summaries | absent | `columns[].cachedContents`: `non_null`, `null`, `count`, `cardinality`, `smallest`, `largest`, `top` |

**Quirks:**
- **Custom fields hold more than update frequency.** "Time Frame" has
  `Update Frequency` (claimed), `Period of Coverage` (free text, e.g. "January 1,
  2009 to present") and `Automated or Manual`. "General Information" has
  `Primary Dataset or View`, `Purpose` and `Internal or External`. "Quality
  Indicators" has `Duplicates Removed` and `Verified for Accuracy`. "Spatial" has
  `Datum` and `Coordinate System`. Coverage varies a lot between assets.
- **Top values are capped at 20** (the largest `top` list seen was 20, on a
  column with cardinality 247010). Spec pitfall 4 holds.
- **Not every column has a summary**: 24 of 34 columns on `24uj-dj8v`, 1 of 2 on
  `8jwm-dd74`.
- **Discovery and views column lists differ.** Discovery listed 38 columns for
  `24uj-dj8v` and views listed 34. The extra four are `location_address/_city/
  _state/_zip`, the sub-fields of a location column.
- **Maps have no columns** (`ex39-rsw7`: 0 in both endpoints). Their schema has
  to come from the parent (`parent_fxf` / `modifyingViewUid`).
- **External data is in the catalogue.** The `ex39-rsw7` map is "COVID-19 in
  Alberta" (custom field `Internal or External: External`), and there is a
  category "Externally Sourced Datasets".
- **The owner field is a placeholder:** `owner.display_name` = "Beta Test Site"
  on `24uj-dj8v`. Don't use it to identify a publisher.

**Licence (per asset):** on Discovery page 0, `metadata.license` was
**"See Terms of Use"** for 88 assets, **"Canada Open Government Licence"** for 5,
and missing for 7. The views API gives `licenseId` `SEE_TERMS_OF_USE` or null.
No asset on page 0 named the "Open Government Licence – City of Edmonton" that
the spec assumes. "See Terms of Use" points to the portal story
`data.edmonton.ca/stories/s/City-of-Edmonton-Open-Data-Terms-of-Use/msh8-if28/`.
Per the 2026-10-01 research report (`docs/SPEC_landscape.md` Review log), that
page holds the Open Government Licence – City of Edmonton. Neither has been
read live yet.
- **Third-party licences show up only in descriptions** (e.g. "licensed under
  the Open Government Licence – Alberta"). The licence field can't tell City
  assets from third-party ones. Other signals: category "Externally Sourced
  Datasets", custom field `Internal or External`, `attribution`.
- **`provenance`** (Discovery `resource.provenance`, views `provenance`):
  `official` vs community (user-created) views. The probe's 3 assets were all
  `official`; the full-catalogue split is unknown.
- **Personal information in column summaries:** `cachedContents.top` and
  `smallest`/`largest` can hold individuals' names and addresses (e.g. Business
  Licences rental-licence holders). Never publish them unfiltered (spec, Data
  sources).
