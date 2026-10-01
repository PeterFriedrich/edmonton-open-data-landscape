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
- **Retrieved:** 2026-10-01 **probe only**: one Discovery page (`limit=100`) plus
  views for `24uj-dj8v` (dataset), `ex39-rsw7` (map), `8jwm-dd74` (filter).
  Raw responses are kept locally in `data/raw/probe_2026-10-01/` (gitignored), along
  with the probe script. The full harvest hasn't run yet (M1a).
- **Size:** `resultSetSize` = **2088** assets, all types. The Discovery page was
  677 KB per 100 assets (≈14 MB raw for the full catalogue, before gzip). Views
  responses were 5–56 KB each.
- **Asset types on page 0:** dataset 54, map 23, story 12, filter 6, chart 4, file 1.

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
the spec assumes. So the portal's **Terms of Use** document is the actual
licence text for most assets, and it is still unread (TODO: licence item).
