#!/usr/bin/env bash
# Run in the repo (on the ticket branch) BEFORE every commit and before opening a PR:  check_staged.sh
# Exit 1 (BLOCKED) if, in the staged files or the branch diff vs origin/<base>:
#   - a local-only file is touched (profile.json local_only_files of $TICKET_REPO), or
#   - an EXISTING test file is modified, deleted or renamed (profile.json existing_tests_regex). Adding NEW test files is allowed.
set -u
AUTO="$(cd "$(dirname "$0")/.." && pwd)"
prof() { [ -n "${TICKET_REPO:-}" ] && python3 "$AUTO/config.py" profile "$TICKET_REPO" "$1" 2>/dev/null; }
BASE="${TICKET_BASE_BRANCH:-$(prof base_branch)}"; BASE="${BASE:-main}"
BLOCK="$(prof local_only_files | python3 -c 'import json,sys
try: print("|".join("(%s)" % p for p in json.load(sys.stdin)))
except Exception: print("")')"
BLOCK="${BLOCK:-^\.env(\..+)?$}"
TESTS="$(prof existing_tests_regex)"
TESTS="${TESTS:-(\.(spec|test)\.[a-z]+$|(^|/)(test|tests|__tests__|e2e|spec)/|_test\.[a-z]+$|(^|/)test_[^/]+$)}"
status="$( { git diff --cached --name-status; git diff --name-status "origin/$BASE...HEAD" 2>/dev/null; } | sort -u)"
fail=0
while IFS=$'\t' read -r st a b; do
  [ -z "${st:-}" ] && continue
  paths="$a"; [ -n "${b:-}" ] && paths="$a"$'\n'"$b"
  while IFS= read -r f; do
    if printf '%s' "$f" | grep -Eiq "$BLOCK"; then echo "BLOCKED: local-only file must never be committed: $f"; fail=1; fi
  done <<< "$paths"
  case "$st" in
    A*) ;;   # new file: fine, even if it is a test
    *) while IFS= read -r f; do
         if printf '%s' "$f" | grep -Eq "$TESTS"; then echo "BLOCKED: existing test file changed ($st): $f  (add NEW tests only; never edit, delete, rename or loosen existing ones)"; fail=1; fi
       done <<< "$paths" ;;
  esac
done <<< "$status"
if [ "$fail" -ne 0 ]; then echo "Fix: local-only file -> git restore --staged <file> (keep the local edit). Existing test -> git restore --staged <file>; git checkout origin/$BASE -- <file>"; exit 1; fi
echo "check_staged: ok"
