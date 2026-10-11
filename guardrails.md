# Guardrails (prepended to every automation step; do not relax)

**TOP RULE: never perform any action on a live environment.** The ONLY place where anything may be changed, submitted or clicked beyond viewing is the
TICKET'S OWN REPO test environment (repo config -> `test_environment`, from settings.json). Every other site, store, account, admin or customer area,
including one a ticket calls a "test" or "demo" environment, and the test environment of ANOTHER repo, is a LIVE environment: view only.
On a live environment the only clicks allowed are in `{{AUTOMATION_DIR}}/skills/live-view-only.md` (navigate, read, search/filter, open a modal and
close it with X), or the stricter local playbook `skills/playbooks/<repo>-live-allowed-actions.md` if present.

**TWO KINDS OF KNOWLEDGE.** These rules and the skills are generic. Everything about the ticket's repo (surfaces, folders, commands, local-only files,
how to run and verify it, its live environments) is in the GENERATED project files: `<project_dir>/profile.json`, `<project_dir>/project.md`,
`<project_dir>/<surface>.md` (project_dir is in the repo config; step 0 writes them). Read them; never guess repo facts the profile does not state.
Files under `skills/playbooks/` are owner-taught and local; one named anywhere that does not exist on this machine: skip it, write
"playbook <name> not present" in the note. A missing playbook never makes a live environment less protected.

## Repo scope
- The repo is in $TICKET_REPO and in the prompt's repo config. Read `project.md` and the profile's `context_docs` first; work only inside the folders
  of the ticket's surface (profile `surfaces.<key>.code`).
- A rule in project.md belongs to that repo only. Never apply one repo's facts, tools or test environment to another repo.
- If a live check would need setup the project files do not describe (CLI login, local backend, proxy), do the code + test checks and set
  needs-human for the live part.
- The profile's `commands.test_gate` (if not empty) is required for every change, like a security suite.

## Live environments and live data: look, never touch
- STRICT: a live environment is ALWAYS view mode only. If you get stuck there (a click/action would be needed, a page is blocked, a permission is
  denied), STOP that execution and record needs-human. Never do the task another way and never look for a workaround.
- Even when a ticket names a "test record" / "test account" / "test order" on a live environment: those ids are for LOOKING only.
  FORBIDDEN there: any modal's action/confirm button, Save/Update/Apply/Confirm/Submit, create/edit/delete of any record, changing a setting control,
  injecting scripts or hooks into the page, and anything that sends POST / PUT / PATCH / DELETE or a GraphQL mutation. To see an action's API call
  or a flow, reproduce it on the TEST environment (copy the live settings there). If the evidence can only come from the live environment, stop:
  needs-human.
- Do not enter passwords on a live environment for anything beyond viewing, and never change anything there.
- Running LOCAL code against a live page (a local proxy / override the project documents) does NOT relax anything: still view only. Debug code
  may only log, never send requests.
- Every step on a live environment is logged as it happens in `evidence/<id>/live-log.md` (skills/root_cause.md Part A). A visit without a log is not allowed.
- RECORD ID IN EVERY SCREENSHOT: every screenshot of a record page (before / after / evidence, live or test) is a FULL-SCREEN capture where the
  record id is visible (header or URL). Crop names/emails/addresses only, never the id. Write the record id in the ledger note of every step that opens one.
- Any state-changing action is allowed only on the configured test environment. If the repo has no test_environment.url: needs-info
  ("no test environment configured").
- Never use or print real customer data (emails, addresses, phone, tokens, JWTs). Do not paste secrets into comments, PRs or logs.

## Git and code
- NO WORKTREES: all code changes happen in the repo's MAIN checkout (repo config -> path). The developer does not use the repo while the automation
  runs. One ticket = one LOCAL branch from origin/<base_branch> (`git checkout -b <branch> origin/<base_branch>`; base in $TICKET_BASE_BRANCH).
  The developer later tests each ticket by switching to its branch; PRs always target <base_branch>.
- LOCAL-ONLY FILES (profile `local_only_files`) stay uncommitted and carry over between branches. Never commit, stage, revert, stash or reset them.
  Any OTHER uncommitted change found before switching branches = not ours -> stop with needs-human (never stash/reset/clean/discard it).
- Never `git stash` (except the path-limited test trick in skills/fix.md, popped immediately), never `git reset --hard`, never `git clean`,
  never `git checkout -- .`, never delete a branch you did not create, never touch another ticket's branch except to check it out for verify/PR.
- Never push to the base branch. Never merge. PRs are DRAFT only, base = origin/<base_branch>.
- Branch name: `python3 {{AUTOMATION_DIR}}/ledger.py branchname --id <id> --title "<title>"` (lowercase, within the configured length).
- Commit message: title `<short issue name> - <ticket link>` (2-4 lowercase words, " - ", the link; no colon, no verb phrase), blank line, "Files:" with
  EVERY changed file one per line (`git diff --cached --name-only`), then the Co-Authored-By trailer(s) from the session attribution reminder.
  One commit per ticket; no emojis; no paths outside the repo.
- Before every `git commit` and before opening a PR run `{{AUTOMATION_DIR}}/tools/check_staged.sh` in the repo; if it prints BLOCKED, unstage that file
  (`git restore --staged <file>`, never discard a local-only file) and re-check. Stage files by explicit path (never `git add -A` / `git add .`).
- TEST GATE: after ANY code change, run the profile's `commands.test_gate` (if set) from the repo root on the ticket's branch. ALL must pass before a
  commit is pushed or a PR is opened. If it fails, FIX THE SOURCE FILE; NEVER change EXISTING tests (profile `existing_tests_regex`): no editing,
  deleting, skipping, renaming or loosening. ADDING new tests for the fix is required. After 2 failed rounds: needs-human with the failing test names.
  Save the pass counts in the ledger note and the PR body. Run heavy suites one at a time (machine load).
- Never edit paths in the profile's `never_change` or `backend_paths` (front-end only; see "Tracker comments").
- NEVER merge, never push to the base branch, never enable auto-merge: {{OWNER_NAME}} reviews each draft PR and merges.

## Communication
- Support-desk conversations (e.g. Intercom) are READ-ONLY context. Never post, reply or add notes there.
- ClickUp: READ-ONLY except the comments listed under "Tracker comments". Never change status, assignee, priority or fields.
- Slack: only the recipients and triggers in skills/slack_dm.md.
- If unsure, or the ticket lacks detail, set needs-info / needs-human with a clear note. A flagged ticket is a good outcome; a guessed fix is not.

## Code quality and notebook (steps 3-5)
- Readable by any developer in one read, minimum comments (default none; only a short WHY). Details: skills/fix.md "Simple, readable code".
- Smallest change, clear names, follows the surrounding style, no dead code.
- Every fix adds NEW tests (unit and/or e2e against the test environment or localhost only, no hard-coded links/tokens/passwords) and runs the
  EXISTING related tests to prove old behaviour is intact. Existing e2e specs that target a live environment are never run.
- After every ticket, add short plain lessons with `tools/lessons.py`; read the matching surface lessons before starting. No secrets in it.

## Discipline
- One ticket per session. Stop after 2 failed attempts on any stage (the ledger enforces this).
- Always record progress with ledger.py (stage, verdict, surface, files, evidence) so a crashed run can resume.
- Be honest in notes: say "not reproduced" when it was not reproduced.

## Housekeeping
- Heavy per-ticket files (logs, evidence screenshots) are deleted by `ledger.py cleanup` once a ticket is finished (draft PR with link recorded,
  config-only fix done, or the ticket moved out of the configured status). The small ledger record stays.
- The PR step embeds before/after screenshots, confirms they rendered (`gh pr view <n> --json body`), then `ledger.py set <id> --evidence-uploaded`.
- Keep screenshots small; never write scratch files into the repo (use {{AUTOMATION_DIR}}/evidence/<id>/).
- NEVER DELETE anything that helps the agent improve: `memory/`, `guardrails.md`, `skills/`, `tools/`, `pipeline.json`, `automation.json`, READMEs,
  playbooks, `projects/`, `state/tickets/` ledger records, and Claude's own memory folder. Cleanup only removes evidence, logs, caches, scratch files.
- The only per-ticket history kept after finish is the live-environment log (moved to state/live-logs/<id>/, deleted after
  automation.json defaults.live_log_retention_days).
- Batch notes: the run starts with `ledger.py batch start`. Tickets that need {{OWNER_NAME}} are added by `ledger.py set`; write what you need as
  `NEEDED: ...` / `OPEN DECISION: ...` / `BLOCKER: ...` in the note.
- Backups: before editing any automation file, copy it to ONE `<file>.bak` next to it (overwrite the old one). Never dated or numbered copies.

## Tracker comments (ClickUp)
- Default: never comment. No progress notes, no stage talk. Findings go to the ledger and the final report.
- CONFIG verdict (no code change needed): exactly ONE clean comment saying it is a configuration matter, which setting and value, and the exact
  menu path where it is. Then `ledger.py set <id> --stage done-config`.
- BACKEND: this automation never changes backend code (profile `backend_paths`, migrations, server APIs). If a ticket needs a backend change, post ONE
  comment starting "For BE team:" (problem, suspected backend place, suggested change; no secrets/customer data). Pure backend -> comment only,
  stage `done-be`. Mixed -> first prove whether a front-end-only change fixes it completely; if yes, front-end fix and NO BE comment; if only partly,
  fix the front-end part and comment the rest. Never mark a ticket for BE without proving a front-end change cannot fix it.
- UI TEXT: a ticket that asks to change/clarify UI text but does not give the exact new wording -> do NOT invent text, no PR. ONE comment asking for
  the exact text: each place the text appears (plain screen name) with its CURRENT text quoted, plus any behaviour question. Stage needs-info.
- After a ticket's draft PR is created: ONE comment with exactly the line `UI changes done`.
- Re-read the ticket's status right before posting anything; if it is no longer the configured status, post nothing (stage moved-out).
