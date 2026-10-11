# STEP 4: verify the fix locally (one ticket or one PR group, Opus).

> LIVE RULE (whole step): the live check runs on the ticket repo's test environment. Live environments: view only (skills/live-view-only.md),
> every step logged in evidence/<id>/live-log.md. See guardrails.md.

WHERE: no worktrees, no patches. In the repo's MAIN checkout, `git checkout <ticket branch>` (from the ledger); before switching, `git status --short`
may only show local-only files (profile `local_only_files`), anything else -> needs-human. Do NOT commit here: code problems go back to step 3
(`ledger.py set <id> --stage fixing --note "<what failed>"`), which continues on the same branch.

Input: TICKET_ID, TICKET_REPO, TICKET_BASE_BRANCH. Stage flow: fixed-local -> verifying -> verified (or back to fixing, or needs-human).
No push, no PR, no merge, no tracker comment. No sudo, ever.

1. `ledger.py show <id>`, `ledger.py set <id> --stage verifying`. Read `evidence/<id>/handover.md` first (surface, root cause, files, copies, repro,
   "Needs live check", repro spec), then the ledger note. `git diff origin/<base>...HEAD --name-only` must list only the intended files.
   Run `{{AUTOMATION_DIR}}/tools/check_staged.sh`.
2. Static + regression checks (always):
   a. `git diff origin/<base>...HEAD`: minimal and matches the root cause. Anything unrelated -> back to fixing.
   b. grep every importer/consumer of each changed component/function/style; read each and say whether the change can affect it (props, defaults,
      other surfaces, twins in the surface map).
   c. Typecheck/lint for the touched area only (profile commands).
   d. Profile `commands.test_gate`: ALL pass. Never edit tests.
      SKIP RULE: if the note has `TESTED: <hash> ...`, `git rev-parse HEAD` equals it and the tree has no tracked changes except local-only files,
      step 3 already ran these on exactly this code: copy the counts ("from step 3, same commit <hash>") instead of re-running.
2b. Risk tier ("Needs live check"): `no` = pure logic fully covered by new unit tests: write verify.md ("logic-only, covered by <specs>; no screen
    changes"), set `verified`, stop (no dev server, no browser). `yes` or missing = live check below. Disagree with a `no` (the diff touches
    something visible): do the live check and say why.
    REUSE THE REPRO: if `evidence/<id>/repro.spec.ts` exists, re-run it against the local code (same steps as before) instead of a new script.
3. Live check on the TEST environment, for the ticket's surface, exactly as `<project_dir>/project.md` "Verify a change" describes (dev server, local
   extension/dev mode, local proxy ... whatever the project documents), one surface at a time.
   - Never kill a dev server or process you did not start; port busy -> wait, then needs-human.
   - A method project.md does not describe, or one that needs a login / CLI session / system change you cannot do: needs-human with the exact
     command or setup {{OWNER_NAME}} must run. Never change system files (hosts, sudoers, certificates) yourself.
   - Local-only edits a method needs (e.g. pointing a dev config at the test environment) stay uncommitted and are restored after.
   - BEFORE screenshots come from step 2 (`evidence/<id>/shots/before-*.png` + "BEFORE:" notes). Do not redo them; take the AFTER on the same screen,
     same size: `evidence/<id>/shots/after-*.png` (max 1280 wide). Only if step 2 left none for a surface: take the before now with production code.
   - Behavioural bugs: also a short video or GIF of the full flow (under 3 MB).
   - Backend-only parts are not verified here (front-end only).
3b. MUST-KEEP CHECK (bugs): check every "Must keep working" row of `evidence/<id>/root-cause.md` on the local code + test environment (old feature,
   newer feature, bug case). Note "MATRIX LIVE: <row> ok/fail" per row; any fail = not verified.
3c. NEVER COME BACK: re-check the bug on every variant in root-cause.md and in every changed copy; run the lock test. A variant still broken, or a
   symptom-only fix (delay, CSS hide, one-account special case) = not verified.
3d. READABILITY REVIEW: read the source diff. Not verified if it has comments saying WHAT the code does, ticket ids/dates in comments,
   commented-out code, nested ternaries, unclear names, or a new abstraction used once. Send it back:
   `ledger.py set <id> --stage classified --force --note "READABILITY: <file:line> <problem>"`.
4. Verdict. All must hold: (1) the problem no longer happens (after vs before), (2) no new problem in the regression check (adjacent screens/flows,
   listed consumers, no new console errors: capture before/after), (3) nothing else in the diff is affected.
   - Pass -> `{{AUTOMATION_DIR}}/evidence/<id>/verify.md` (what was checked, commands + results, before/after paths, consumers reviewed, gate counts,
     what was NOT verified), `ledger.py set <id> --evidence <each file> --stage verified --note "<2-3 lines>"`.
   - Problem found -> `ledger.py set <id> --stage fixing --note "<exact failure + evidence path>"` (an attempt; 2 attempts then needs-human).
   - Cannot verify (environment/access) -> `--stage needs-human --note "<what is missing>"`. Claiming it works without proof is never ok.
5. Clean up what you started: stop your dev servers, restore local-only files you changed for the run, undo any local override the project method
   switched on (and confirm it is off), close the browser tabs you opened. If the profile has a `cleanup_check`, run it: it must print its `ok` text.
6. Final message: ticket id, verdict, one line per check, evidence paths, cleanup state, anything not verified.

## Screenshots for the PR
Every verified ticket needs BEFORE (production / base branch) and AFTER (local code) screenshots of the same screen, per surface touched, in
evidence/<id>/shots/ as before-*.png / after-*.png. Step 5 puts them in the draft PR under ## Screenshots.

## Display-only bugs that need the live data
When a bug is only about how data is SHOWN and the live data is what triggers it, and project.md documents a way to show local code against a live
page in view mode: after the AFTER run on the test environment, open the live page in VIEW MODE ONLY (navigation clicks only, logged in
live-log.md), screenshot, crop or blur all personal data, save `after-live-*.png`, and put it in the PR ("After, live environment with this branch,
view only"). Then undo the local override and confirm it is off. Not documented -> skip it and write "live data check: not available".

## Fixes that cannot be reproduced on the test environment
Verify what can be verified (unit tests, the build, the changed screen renders on the test environment), mark the ticket verified-with-limits, and let
step 5 open the draft PR stating plainly: "Not reproducible on the test environment; change made from the ticket description and code; needs a
live check."
