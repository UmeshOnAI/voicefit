#!/usr/bin/env bash
# Creates one git worktree per agent, next to the main checkout.
# Run from the root of the voicefit repository after cloning.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
wt="$(dirname "$root")/voicefit-wt"

git fetch origin
for name in coder coder-ui reviewer tester; do
  if [ -d "$wt/$name" ]; then
    echo "exists: $wt/$name"
  else
    git worktree add --detach "$wt/$name" origin/main
  fi
done
git worktree list
echo "Copy .env.example to .env in the coder and tester worktrees and add the API key."
