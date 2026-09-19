#!/usr/bin/env bash
# Copies the production state that CI keeps on the jobsalert-state branch into data/,
# so the local dashboard shows what the scheduled runs have seen and sent.
# Usage: scripts/sync_state.sh [branch]
set -euo pipefail
branch="${1:-jobsalert-state}"
cd "$(dirname "$0")/.."
git fetch --depth=1 origin "$branch"
mkdir -p data
for f in $(git ls-tree --name-only FETCH_HEAD); do
  git show "FETCH_HEAD:$f" > "data/$f"
  echo "updated data/$f"
done
