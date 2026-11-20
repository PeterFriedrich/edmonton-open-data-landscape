#!/usr/bin/env bash
# Weekly catalogue snapshot (M1b), run from the opc crontab (installed by the
# `server` session; line recorded in TODO.md M1b). Any failing step must exit non-zero: cron's
# `|| gh issue create` is the only way a failure reaches a human.
#
# Runs in its own worktree on origin/master, so it never touches whatever branch
# a session has checked out in the main clone. Raw snapshot -> private repo;
# reduced copy -> this repo's master (owner decision 2026-10-02: straight to master).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WT="$REPO/.cron-worktree"
PRIVATE="$REPO/data/raw/private-snapshots"
PY="$REPO/.venv/bin/python"

exec 9>/tmp/eodl-snapshot.lock
flock -n 9 || { echo "$(date -u +%FT%TZ) another run holds the lock; skipping"; exit 0; }

cd "$REPO"
if [ -f .env ]; then set -a; . ./.env; set +a; fi
echo "$(date -u +%FT%TZ) weekly snapshot start"

git fetch -q origin master
if [ -d "$WT" ]; then
  git -C "$WT" checkout -q --detach origin/master
  git -C "$WT" reset -q --hard origin/master
else
  git worktree add -q --detach "$WT" origin/master
fi

git -C "$PRIVATE" pull -q --ff-only
# The warm step below runs master's src/search.py here; point it at the main clone's
# snapshots and search cache, which the MCP service reads (same symlinks as its worktree).
ln -sfn "$PRIVATE" "$WT/data/raw/private-snapshots"
ln -sfn "$REPO/data/processed/search" "$WT/data/processed/search"

DATE="$(date -u +%F)"
cd "$WT"
"$PY" -m src.harvest --out "$PRIVATE" --date "$DATE"
"$PY" -m src.reduce_snapshot "$PRIVATE/$DATE" --out "$WT/data/snapshots"

git -C "$PRIVATE" add "$DATE"
git -C "$PRIVATE" commit -q -m "Snapshot $DATE (weekly cron)"
git -C "$PRIVATE" push -q origin HEAD

git -C "$WT" add "data/snapshots/$DATE"
git -C "$WT" commit -q -m "Weekly reduced snapshot $DATE"
git -C "$WT" push -q origin HEAD:master

# Embed the new snapshot here, not in the MCP service: it never embeds inside a request
# (src/mcp_server.py) and serves the previous snapshot until this has run. ~3.5 min, <1 GB.
# After the pushes, so a failure here still leaves the snapshot saved (and still opens an issue).
"$PY" -m src.search --source edmonton --include-hidden warm > /dev/null
echo "$(date -u +%FT%TZ) search cache warmed: edmonton $DATE"

echo "$(date -u +%FT%TZ) weekly snapshot done: $DATE"
