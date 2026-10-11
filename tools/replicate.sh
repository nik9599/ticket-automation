#!/usr/bin/env bash
# Scaffold + run a throwaway Playwright repro for one ticket, outside the repo's main tree.
#   replicate.sh <repo_path> <ticket_id> [spec_file]
# Layout: <automation>/evidence/<id>/{repro.spec.ts, shots/, results/, playwright.config.ts, node_modules -> repo/node_modules}
# Env: TEST_BASE_URL (test environment origin), TEST_HOST (its host name, used by the network guard), GUARD_ACTION_WORDS (profile guard_action_words, comma-separated).
set -euo pipefail
AUTO="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${1:?repo path}"; ID="${2:?ticket id}"; SPEC="${3:-repro.spec.ts}"
EV="$AUTO/evidence/$ID"
mkdir -p "$EV/shots" "$EV/results"
[ -e "$EV/node_modules" ] || ln -s "$REPO/node_modules" "$EV/node_modules"
[ -e "$EV/$SPEC" ] || cp "$AUTO/tools/repro.spec.template.ts" "$EV/$SPEC"
cat > "$EV/playwright.config.ts" <<CFG
import { defineConfig, devices } from '@playwright/test';
export default defineConfig({
  testDir: '.', outputDir: './results', timeout: 90_000, workers: 1, retries: 0, reporter: 'line',
  use: { ...devices['Desktop Chrome'], baseURL: process.env.TEST_BASE_URL, screenshot: 'off', trace: 'off' },
});
CFG
cd "$EV"
exec npx playwright test "$SPEC"
