# Change pipeline

The path every change takes in this repo, in order. **Read it before you open
your first PR of a session.** Each step says what to run and when to stop and
ask the owner. The rules themselves live in `CLAUDE.md` and the scripts named
here; this doc puts them in sequence and doesn't restate them.

**What it's for:** spend the owner's attention only where a person is
needed (plans, the stop-and-ask points, calls a guard can't make) and let
guards and review catch the rest. Saving review time is no saving if it comes
back as fixes after a merge, so that count is the guardrail (step 4.5).
Weigh a step you'd skip or a row you'd answer `no` against it.

Step status, meaning which steps a hook or CI enforces and which hold only
while you remember them, lives in two places. In the template it's the README
(§"How a change goes, and where each step stands"), and a PR that changes a
step changes both. In a project it's §"This project's fit" below, since a
project's README doesn't carry the template's table.

The steps marked *per project* are filled in by each project, because the
template has no data to publish. A project replaces those placeholders in its
own copy; `copier update` keeps that edit.

## 1. Before the PR

1. **Plan first when the change is a new module, a data contract or output
   schema change, or a CI change** (`CLAUDE.md` §"Comments & Scope"). Send the
   plan to the owner and wait. Routine edits don't need one.
   - **Offer an explainer in one line** when the plan touches a part of the
     code the owner hasn't worked in: a written explainer of that slice, or a
     page (an Artifact) that shows it visually. The owner asked to be reminded
     that this exists. Offer it; don't make it unasked.
2. **Reproduce before you fix.** An open TODO item can be stale: re-measure
   its stated cause first.
   - **Search `docs/DECISIONS.md` before changing a behaviour or a number**,
     for the file, function or term you're about to change. Say what it found
     in the plan or the description, or "no decision found". Checking "when
     it feels settled" misses the case where it doesn't: `edmonton-tax-viz`
     reverted a change whose own fix says "it was decided, and I had not read
     the row".
3. **A decision that protects a number is a test first.** Write the guard,
   then the `docs/DECISIONS.md` row that cites it.
4. **A number that rests on something unproven gets a row in
   `docs/ASSUMPTIONS.md`**, pointing at the evidence.
5. **Verify, and show the output.** Run `python -m pytest tests -q` and every
   `scripts/check_*.py`. Say what ran and what it returned, not that it passed.
   Run them after your last edit, and on the built output when something is
   served: a check from before the final edit verified a different file.
   - Passing tests are not the result in a data project. **A change that moves
     a published number shows the old and new value and why it moved.** Build
     both sides from one raw data pull, or a data refresh is blamed on the
     code change. Show totals and the largest movers, not every row: a
     citywide total can move 0.2% while one area moves 130%.
   - *Per project*: which tiers count as published (served data, numbers in
     the page copy, report figures), and the command that prints them.
6. **Break each new or changed guard on purpose.** Revert the fix or mutate
   the check, confirm its test goes red, then restore it. A test that passes
   either way guards nothing; on template PR #37 this caught one.
7. **Review the diff** (*trial*: follow it where the owner has started the
   trial; TODO J in the template decides whether it becomes the rule). Run
   `/code-review` on a diff that touches code, at the level below. Fix or resolve each finding with a reason. Docs-only diffs skip
   this step.
   - `medium`: a change to a published number, a data contract or `src/`.
   - `low`: tooling, guards, tests.
   - `ultra`: only when the owner starts it; it is billed.
   - One round per PR. Re-review only after a substantial fix, and only on
     the new diff.
   - **Fix the class, not the line.** When you fix a finding, search for the
     same pattern elsewhere (another hand-kept copy of a list, the same
     unchecked call) and fix every instance, or say why one stays. Note it on
     the `Code review:` line ("fixed, 2 more instances by grep").
   - **A real finding this diff didn't introduce is pre-existing.** Don't fix
     it in this PR (the smallest-change rule); open a `TODO.md` item, or a
     `docs/DATA_ISSUES.md` / `docs/ASSUMPTIONS.md` row if it is about data.
     Old silent errors surface here, and without a home they either swell
     the PR or get dropped.
   - **Security review on risky paths** (*per project*: each repo lists its
     own). Run `/security-review` too when the diff touches
     `.github/workflows/`, a deploy script, or a secret or token; adds a data
     file to a public repo; or renders outside data as HTML. Handle its
     findings like the ones above, on the same `Code review:` line
     ("security: 0 findings"). Other diffs skip it. This repo's list: the
     template defaults above.
8. **A kind of finding seen twice is fixed at the source**, not by hand a
   third time. When `/code-review` or an audit flags the same kind of problem
   on a second PR, fix it at the source in that PR, or tell the owner why not.
   - Prefer a guard or hook. A `CLAUDE.md` or `REVIEW.md` line is for when no
     mechanism fits: in `edmonton-tax-viz` a written rule twice failed to stop
     pushes to merged branches, and only `.githooks/pre-push` did. Say which
     you chose and why.
   - Twice can be a coincidence. Before proposing a guard, say how often this
     kind of problem actually occurs; a "why not" answer gives that rate too.
9. **Commit each working unit** with a descriptive message.

## 2. The PR

1. **Branch fresh from `origin/master` for every PR.** The owner merges within
   minutes, and a branch whose PR merged is dead (`.githooks/pre-push` blocks
   pushing to it).
2. **The description opens with these lines**, after the Sync note if 2.3
   applies. They put what the session saw in front of the owner at merge
   time, without the transcript.
   - `Risk:` the tier, set by the paths the diff touches, not by judgment:
     the highest tier any path reaches, and that path ("high
     (`.github/workflows/tests.yml`)"). *Per project*: each repo lists its
     own paths in the fit table. Template defaults:
     - **high:** `.github/workflows/`, deploy and publish scripts, a secret or
       token, a data contract or output schema, `src/` code behind a
       published number;
     - **medium:** other `src/`, `scripts/`, tests that change;
     - **low:** docs, `TODO.md`, handoffs, tests only added.
   - `Code review:` (*trial*, with 1.7) the level, the finding count, and
     what happened to them ("medium, 4 findings: 2 fixed, 1 intended, 1
     pre-existing, now a TODO item"), or "skipped (docs only)".
   - `Tested:` what ran and what it returned (step 1.5), and old → new for
     any published number that moved. Then "not covered: …", naming what no
     test or guard checked ("not covered: the served page; only the JSON was
     checked"), or "not covered: nothing known". The owner can't read the
     evidence without knowing what the checks would miss, and a published
     number in the not-covered part is the cue to read the diff.
   - `Undo:` "revert", or "revert, then …" when a revert alone leaves
     something behind: served data to rebuild and redeploy, commits or a
     deploy a workflow already made, a claude.ai Project to re-sync, files
     built downstream in a changed shape.
   - `Cause:` a bug fix only: the cause in one line, apart from the symptom,
     then the step that should have caught it: "missed by: step 1.5", or
     "missed by: none (found by <audit>)" when no step was meant to.
     Step 1.8 spots repeats by cause and by the step that missed them, not by
     symptom. Don't guess a step: in `edmonton-tax-viz`, 10 of 19 recent
     fixes were found by an audit that no step stands in for.
3. **A PR that changes a claude.ai-synced file** (`docs/BRIEF.md`,
   `docs/SPEC_*.md`, `docs/ARCHITECTURE.md`, `data/DATA.md`) opens with
   "After merge: press Sync in the claude.ai Project." and the paths, one per
   line (`docs/CLAUDE_WEB.md`).
4. **CI must be green**: `.github/workflows/tests.yml` runs pytest and the
   guards, and `master` requires the `test` check. Don't merge around a red
   check; fix it.
5. **Push proactively; don't watch the PR on a timer.** No `/loop`,
   `ScheduleWakeup` or trigger to re-check it. Check it at your next real turn
   (`.claude/skills/steward/SKILL.md`).

## 3. Merging

1. **The owner merges.** Don't merge your own PR unless the owner asked you to.
   What the `Risk:` tier asks:
   - **low:** merge on green.
   - **medium:** as usual.
   - **high:** `/code-review` (and `/security-review` where 1.7's paths say)
     has run, the description names the files or hunks to read, and the
     owner reads the diff before merging. There is one person, so no tier
     needs two; an agent's approval never stands in for the owner's.
     Offer the same one-line explainer as step 1.1 for the slice the diff
     changes.

   *Trial from 2026-10-19:* the tier is a label only and the owner still
   merges every PR. If, after about two weeks, no low-tier PR needed anything
   after the owner looked, sessions may merge their own low-tier PRs on green
   (template TODO M), with a circuit breaker: a fix to a self-merged PR's
   tests or to a number it published stops self-merge until the owner turns
   it back on.
2. **A push after the owner has looked says so.** If you push to a PR the
   owner has already looked at or approved, comment on the PR before they
   merge: "new commit since you looked: <what it changes>". Their look
   covered the commit they saw, not this one.
3. **Before every push to an existing branch, check whether its PR merged**
   (`gh pr view --json state`). If it did, branch again from `origin/master`.
4. **After a merge, confirm the work landed**:
   `git merge-base --is-ancestor <sha> origin/master`. A merged PR is
   necessary, not sufficient.

## 4. After the merge

1. **Template changes reach projects by `copier update`**, run by each
   project's own session. The `template_drift.py` hook tells them at session
   start.
2. **Publish** (*per project*): what ships, when, and what gates it. For
   example, a weekly workflow that reruns the pipeline and blocks on verified
   notebooks before deploying.
3. **Staging** (*per project*): whether anything is seen before the public
   build, such as a specialist or internal build.
4. **Watch and roll back** (*per project*): where breakage surfaces (automated
   GitHub issues, a failing scheduled run) and how to undo it (`git revert`,
   then redeploy). Read open issues at session start: `gh issue list --state
   open`.
   - **A warning that only reaches a log is not detection.** Make it fail, or
     file an issue. In `edmonton-tax-viz`, failed runs and deploys were fixed
     in 15 to 30 minutes, but a road class billed wrong for about 70 days
     while its warning printed on every run to a log nobody read.
5. **Count fixes after a merge** (*per project*): how the project would notice
   that a lighter step (a skipped review, a looser guard) is costing more
   fixes later. A fix to a recently merged change, or a wrong published number
   found after it shipped, is the cost that review time was meant to save.
6. **An upstream data defect found on the way** goes in `docs/DATA_ISSUES.md`,
   with whether the publisher has been told.

## When to stop and ask

- A plan-first change (step 1.1).
- A finding you'd resolve as "intended" that changes a published number.
- Anything that would push to `master`, rewrite history, or delete data.
- A permission your session was denied. Take it to the owner; don't ask
  another session to do it.

## This project's fit

Each project answers this table for itself; the template ships every row as
`not evaluated`. Replace it with one of:
- `adopted`, plus the mechanism (`tests.yml`, a hook, a habit);
- `later: <trigger>`, the event that would make it worth doing;
- `no: <reason>`;
- `n/a`, plus why it can't apply.

**When to answer:** at project creation, and in any `copier update` that adds
or changes a row here (`docs/COPIER.md` §"When the session-start notice
appears"). List the new answers in that PR's description. An honest `no` is
the point: it shows the owner a gap, such as `master` with no required check.

| Stage | Step | This project |
|---|---|---|
| Before the PR | Plan first for a new module, schema or CI change | not evaluated |
| | Reproduce before fixing | not evaluated |
| | A decision that protects a number is a test first | not evaluated |
| | Unproven premises indexed in `docs/ASSUMPTIONS.md` | not evaluated |
| | Verify, and show the output | not evaluated |
| | A moved published number shown old → new, with why | not evaluated |
| | Break each new or changed guard on purpose | not evaluated |
| | Review the diff with `/code-review` (trial) | not evaluated |
| | `/security-review` on this repo's risky paths (list them) | not evaluated |
| | A kind of finding seen twice is fixed at the source | not evaluated |
| | Commit each working unit | not evaluated |
| The PR | A fresh branch from `origin/master` per PR | not evaluated |
| | `Code review:` line in the description (trial) | not evaluated |
| | Pre-existing findings go to `TODO.md` or a ledger, not this PR | not evaluated |
| | A bug-fix PR names its cause | not evaluated |
| | The description carries `Tested:` and `Undo:` | not evaluated |
| | `Risk:` tier set by this repo's path list (list them) | not evaluated |
| | Sync note for claude.ai-synced files | not evaluated |
| | CI green, and `master` requires the `test` check | adopted: branch protection on `master` since 2026-10-21 requires `test`; `enforce_admins: false` so the weekly cron push lands (first check: cron run 2026-10-23) |
| | No timed PR check-ins | not evaluated |
| Merging | The owner merges | not evaluated |
| | A push after the owner looked is announced on the PR | not evaluated |
| | Pre-push hook enabled (`git config core.hooksPath .githooks`) | not evaluated |
| | Work confirmed on `master` with `git merge-base` | not evaluated |
| After the merge | Template changes pulled by `copier update` | not evaluated |
| | Publish, with a gate before it ships | not evaluated |
| | Seen before the public build | not evaluated |
| | Watch and roll back | not evaluated |
| | Fixes after a merge are counted (the guardrail) | not evaluated |
| | Upstream data defects logged in `docs/DATA_ISSUES.md` | not evaluated |
