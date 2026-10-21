"""Fit-table guard: a project's answers to the change pipeline survive a template update.

``docs/CHANGE_PIPELINE.md`` §"This project's fit" holds one row per pipeline
step, which each project answers. When the template adds a row, ``copier
update`` returns the whole table as ONE conflict block: the project's answers
on one side, the template's ``not evaluated`` rows on the other (seen in a dry
run on ``edmonton-civic-map``, 2026-10-19). Taking either side whole loses
data silently, so this checks:

  1. **NO CONFLICT MARKERS** anywhere in the doc. A line starting with
     ``<<<<<<<`` or ``>>>>>>>`` is half a merge. (A bare ``=======`` is not
     flagged: it is also a Markdown heading underline, and never comes alone.)
  2. **EVERY TEMPLATE STEP, ONCE.** Each name in ``FIT_STEPS`` appears exactly
     once in the table's Step column, matched by name: the Stage cell is blank
     on continuation rows.
  3. **EVERY ROW ANSWERED.** The answer cell isn't empty.
  4. **NO ANSWER GOES BACK TO ``not evaluated``** (with ``--base <ref>``, which
     CI passes on a PR). Keeping the template's side of the conflict whole
     wipes every answer yet leaves a well-formed table, so only a comparison
     with the base shows it. A project stepping back writes ``later: <trigger>``,
     which is still an answer. Fails open: an unreadable ref skips this check.

Allowed on purpose: rows a project adds for its own steps (and a row whose step
the template later drops), and ``not evaluated``, which is counted, not failed:
a new project and the template itself start with every row unanswered.

``FIT_STEPS`` ships in this script, which projects don't edit, so ``copier
update`` delivers the new list cleanly with the new rows. In the template,
``test_template_table_matches_fit_steps`` fails a PR that changes the table
without the list. A missing doc passes.

Exit codes: 0 ok; 9 a check fails (2 is argparse's).

Usage:
    python scripts/check_fit_table.py
    python scripts/check_fit_table.py --base origin/master
    python scripts/check_fit_table.py --root /path/to/checkout
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

from check_decisions_log import cells

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = "docs/CHANGE_PIPELINE.md"
SECTION = "## This project's fit"

EXIT_OK = 0
EXIT_FAIL = 9

FIT_STEPS = [
    "Plan first for a new module, schema or CI change",
    "Reproduce before fixing",
    "A decision that protects a number is a test first",
    "Unproven premises indexed in `docs/ASSUMPTIONS.md`",
    "Verify, and show the output",
    "A moved published number shown old → new, with why",
    "Break each new or changed guard on purpose",
    "Review the diff with `/code-review` (trial)",
    "`/security-review` on this repo's risky paths (list them)",
    "A kind of finding seen twice is fixed at the source",
    "Commit each working unit",
    "A fresh branch from `origin/master` per PR",
    "`Code review:` line in the description (trial)",
    "Pre-existing findings go to `TODO.md` or a ledger, not this PR",
    "A bug-fix PR names its cause",
    "The description carries `Tested:` and `Undo:`",
    "`Risk:` tier set by this repo's path list (list them)",
    "Sync note for claude.ai-synced files",
    "CI green, and `master` requires the `test` check",
    "No timed PR check-ins",
    "The owner merges",
    "A push after the owner looked is announced on the PR",
    "Pre-push hook enabled (`git config core.hooksPath .githooks`)",
    "Work confirmed on `master` with `git merge-base`",
    "Template changes pulled by `copier update`",
    "Publish, with a gate before it ships",
    "Seen before the public build",
    "Watch and roll back",
    "Fixes after a merge are counted (the guardrail)",
    "Upstream data defects logged in `docs/DATA_ISSUES.md`",
]

MARKER = re.compile(r"^(<{7}|>{7})(\s|$)")
SEPARATOR = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
UNANSWERED = re.compile(r"^\W*not evaluated", re.I)


def fit_rows(md: str) -> list[tuple[int, list[str]]] | None:
    """(lineno, cells) for each body row of the first table under SECTION, or
    None when the section is missing. Stops at the next `## ` heading."""
    lines = md.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == SECTION), None)
    if start is None:
        return None
    rows, seen_table = [], False
    for i in range(start + 1, len(lines)):
        line = lines[i]
        if line.startswith("## "):
            break
        if line.startswith("|"):
            seen_table = True
            if not SEPARATOR.match(line):
                rows.append((i + 1, cells(line)))
        elif seen_table and not MARKER.match(line) and line.strip() != "=======":
            break  # the table ended; markers inside it don't end it
    return rows[1:]  # drop the header


def at_ref(root: Path, ref: str) -> str | None:
    """The pipeline doc as committed at ``ref``, or None when git can't say."""
    try:
        r = subprocess.run(["git", "-C", str(root), "show", f"{ref}:{PIPELINE}"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def answered(rows: list[tuple[int, list[str]]]) -> set[str]:
    return {r[1] for _, r in rows if len(r) > 2 and r[2].strip() and not UNANSWERED.match(r[2])}


def check(root: Path = ROOT, base: str | None = None) -> tuple[list[str], int]:
    """(failures, rows still `not evaluated`). With ``base``, also fail on an
    answer that ``base`` had and this checkout lost to `not evaluated`."""
    path = root / PIPELINE
    if not path.is_file():
        return [], 0
    md = path.read_text(errors="ignore")
    failures = [f"{PIPELINE}:{n}  conflict marker `{l[:7]}`: an unfinished merge"
                for n, l in enumerate(md.splitlines(), 1) if MARKER.match(l)]
    rows = fit_rows(md)
    if rows is None:
        return failures + [f"{PIPELINE}  no `{SECTION}` section"], 0
    where: dict[str, list[int]] = {}
    unanswered = 0
    for lineno, row in rows:
        step = row[1] if len(row) > 1 else ""
        answer = row[2] if len(row) > 2 else ""
        where.setdefault(step, []).append(lineno)
        if not answer.strip():
            failures.append(f"{PIPELINE}:{lineno}  `{step}` has no answer")
        elif UNANSWERED.match(answer):
            unanswered += 1
    for step in FIT_STEPS:
        if step not in where:
            failures.append(f"{PIPELINE}  missing row `{step}`: a merge may have dropped it")
    for step, lines in where.items():
        if len(lines) > 1:
            failures.append(f"{PIPELINE}:{lines[1]}  `{step}` repeats line {lines[0]}")
    if base:
        old = at_ref(root, base)
        if old is None:
            print(f"NOTE  can't read {PIPELINE} at `{base}`; skipped the comparison")
        else:
            now_open = {r[1] for _, r in rows if len(r) > 2 and UNANSWERED.match(r[2])}
            failures += [f"{PIPELINE}:{where[s][0]}  `{s}` was answered at `{base}` and is now "
                         f"`not evaluated`: copy the answer back (a merge may have taken the template's side)"
                         for s in sorted(answered(fit_rows(old) or []) & now_open)]
    return failures, unanswered


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--base", help="git ref to compare answers against (CI: the PR's base branch)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    failures, unanswered = check(args.root, args.base)
    for f in failures:
        print(f"FAIL  {f}")
    if failures:
        print(f"\n{len(failures)} failure(s) in {PIPELINE}")
        return EXIT_FAIL
    note = f"; {unanswered} row(s) still `not evaluated`" if unanswered else ""
    print(f"OK  {PIPELINE}: every template step has one answered row, no conflict markers{note}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
