# SCOPE — what this project deliberately does not do

The one hand-kept input to the Claude web brief (`scripts/make_brief.py`, setup
in `docs/CLAUDE_WEB.md`). Everything else in the brief is generated from files
the repo already maintains; this is the list an outside reviewer can't derive —
ideas that were considered and turned down, so they stop coming back as
recommendations.

One bullet each: **the thing**, then why not, and a pointer if a decision row
or doc holds the argument. A turned-down idea that has a locked decision needs
no bullet here — the brief already carries `docs/DECISIONS.md`.

## Out of scope

- **Per-dataset exploration tools** (row browsers, dashboards for a single dataset, a 311 Explorer clone) — the City already provides these; this project's unit of analysis is the catalogue. `docs/SPEC_landscape.md`.
