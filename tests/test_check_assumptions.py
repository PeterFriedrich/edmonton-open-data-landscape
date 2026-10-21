"""Tests for scripts/check_assumptions.py: a malformed index row fails the gate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_assumptions as ca  # noqa: E402

HEADER = ("| ID | Assumption | Status | If wrong (rough size) | Evidence and test |\n"
          "|----|------------|--------|-----------------------|-------------------|\n")


def _repo(tmp_path, rows: str, header: str = HEADER, tests: str = ""):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ASSUMPTIONS.md").write_text("# Assumptions index\n\n" + header + rows)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text(tests)
    return tmp_path


def test_this_repo_index_passes():
    assert ca.check(ca.ROOT) == []


def test_missing_doc_passes(tmp_path):
    assert ca.check(tmp_path) == []


def test_good_rows_pass(tmp_path):
    repo = _repo(tmp_path,
                 "| A1 | x | SUPPORTED (2025 only) | one year | `data/DATA.md` |\n"
                 "| A2 | y | **VERIFIED** | — | `test_year_rule` |\n",
                 tests="def test_year_rule():\n    pass\n")
    assert ca.check(repo) == []


def test_unknown_status_fails(tmp_path):
    failures = ca.check(_repo(tmp_path, "| A1 | x | PROBABLY | small | `data/DATA.md` |\n"))
    assert len(failures) == 1 and "PROBABLY" in failures[0] and "ASSUMPTIONS.md:5" in failures[0]


def test_verified_row_needs_real_test(tmp_path):
    failures = ca.check(_repo(tmp_path, "| A1 | x | VERIFIED | — | `test_renamed_away` |\n"))
    assert len(failures) == 1 and "names no existing test" in failures[0]


def test_unproven_row_needs_size(tmp_path):
    failures = ca.check(_repo(tmp_path, "| A1 | x | UNVERIFIED |  | `data/DATA.md` |\n"))
    assert len(failures) == 1 and "no size" in failures[0]


def test_row_needs_evidence(tmp_path):
    failures = ca.check(_repo(tmp_path, "| A1 | x | ACCEPTED | 0.1 pp | — |\n"))
    assert len(failures) == 1 and "no evidence" in failures[0]


def test_repeated_id_fails_across_tables(tmp_path):
    other = ("\n## Second table\n\n| # | Premise | Status | Size | Build | Evidence |\n"
             "|---|---|---|---|---|---|\n| A1 | z | ACCEPTED | 03 | public | `a.md` |\n")
    failures = ca.check(_repo(tmp_path, "| A1 | x | ACCEPTED | small | `b.md` |\n" + other))
    assert len(failures) == 1 and "already used on line 5" in failures[0]


def test_extra_columns_found_by_name(tmp_path):
    header = "| # | Lens | Premise | Status | Size | Build | Evidence |\n|---|---|---|---|---|---|---|\n"
    assert ca.check(_repo(tmp_path, "| B1 | Money | x | UNVERIFIED | unknown | full | `a.md` |\n",
                          header=header)) == []


def test_table_without_size_column_fails(tmp_path):
    header = "| ID | Assumption | Status | Evidence |\n|---|---|---|---|\n"
    failures = ca.check(_repo(tmp_path, "| A1 | x | ACCEPTED | `a.md` |\n", header=header))
    assert failures == ["docs/ASSUMPTIONS.md:3  table has no size (\"If wrong\" or \"Size\") column"]


def test_table_without_status_is_not_index(tmp_path):
    header = "| Term | Meaning |\n|---|---|\n"
    assert ca.check(_repo(tmp_path, "| A1 | anything |\n", header=header)) == []


# Each case below passed the first version of the guard (code review of PR #36).

def test_one_dash_separator_is_a_table(tmp_path):
    header = "| ID | Assumption | Status | Size | Evidence |\n|:-|-|-|-|-|\n"
    failures = ca.check(_repo(tmp_path, "| A1 | x | PROBABLY | small | `a.md` |\n", header=header))
    assert len(failures) == 1 and "PROBABLY" in failures[0]


def test_status_header_found_anywhere(tmp_path):
    header = "| ID | Assumption | Current status | Size | Evidence |\n|---|---|---|---|---|\n"
    failures = ca.check(_repo(tmp_path, "| A1 | x | BOGUS | small | `a.md` |\n", header=header))
    assert len(failures) == 1 and "BOGUS" in failures[0]


def test_status_must_be_the_whole_word(tmp_path):
    failures = ca.check(_repo(tmp_path, "| A1 | x | VERIFIED_PENDING | — | `test_year_rule` |\n",
                              tests="def test_year_rule():\n    pass\n"))
    assert len(failures) == 2 and "VERIFIED_PENDING" in failures[0] and "no size" in failures[1]


def test_format_guard_is_not_proof(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check_doc_citations.py").write_text("")
    failures = ca.check(_repo(tmp_path, "| A1 | x | VERIFIED | — | checked by check_doc_citations.py |\n"))
    assert len(failures) == 1 and "names no existing test" in failures[0]


def test_test_named_outside_evidence_is_not_proof(tmp_path):
    failures = ca.check(_repo(tmp_path, "| A1 | like test_year_rule | VERIFIED | — | `a.md` |\n",
                              tests="def test_year_rule():\n    pass\n"))
    assert len(failures) == 1 and "names no existing test" in failures[0]


def test_id_column_found_by_name(tmp_path):
    header = "| Lens | ID | Premise | Status | Size | Evidence |\n|---|---|---|---|---|---|\n"
    rows = "| Money | A1 | x | ACCEPTED | 03 | `a.md` |\n| Money | A2 | y | ACCEPTED | 03 | `b.md` |\n"
    assert ca.check(_repo(tmp_path, rows, header=header)) == []


def test_blank_id_fails_once_per_row(tmp_path):
    rows = "|  | x | ACCEPTED | small | `a.md` |\n|  | y | ACCEPTED | small | `b.md` |\n"
    failures = ca.check(_repo(tmp_path, rows))
    assert failures == ["docs/ASSUMPTIONS.md:5  row has no ID", "docs/ASSUMPTIONS.md:6  row has no ID"]


def test_filler_is_blank(tmp_path):
    failures = ca.check(_repo(tmp_path, "| A1 | x | UNVERIFIED | n/a | – |\n"))
    assert len(failures) == 2 and "no size" in failures[0] and "no evidence" in failures[1]


def test_fenced_example_is_skipped(tmp_path):
    example = "```\n" + HEADER + "| A9 | example | PROBABLY |  |  |\n```\n\n"
    assert ca.check(_repo(tmp_path, "", header=example + HEADER)) == []
