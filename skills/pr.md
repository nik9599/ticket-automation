# STEP 5: draft PR (one ticket or one group)

> LIVE RULE (whole step): nothing is changed on any live environment. See guardrails.md.

Input: TICKET_ID, branch (a local branch in the repo's main checkout, from origin/<base_branch>). Stage flow: verified -> pr-draft.
Obey guardrails.md: draft only, base = <base_branch>, never merge, check_staged.sh ok, test gate passed.

## Title
`<Area>: <what now works, in plain words> (<ticket id>)`, e.g. `Order list: keep the chosen filters visible after going back (abc123)`.
Area = the screen/feature in user words. No "fix:" prefixes, no emojis.

## Body (markdown, these sections in this order)
- `Ticket: <https://app.clickup.com/t/{{CLICKUP_TEAM_ID}}/<id>>`
- `Environment: <the environment / record named in the ticket>` (or "internal request")
- `## Problem` - what the user sees, 2-4 plain sentences.
- `## Root cause` - where in the code and why; "Not a bug, a missing option" for a feature.
- `## Fix` - files changed and what each does; then a small table `| | <base> | this branch |` for the behaviour, plus a row for what is unchanged.
- `## Verification` - new tests (file, what they check, "this branch: N/N pass, <base>: N/N fail"), test gate counts, related existing tests, live check
  on the test environment (what was opened, what was seen). Then `Not verified:` as a bullet list. Be honest.
- `## Known limits` - edge cases left as they are, side findings.
- `## Deploy` - from the profile's `deploy_notes` for each touched surface.
- `## Screenshots` - Before and After, one line each saying what it shows. Upload the images in the PR description (browser), confirm they render
  (`gh pr view <n> --json body` shows the attachment URLs), then `ledger.py set <id> --evidence-uploaded`.
- Last lines: the PR attribution footer from the session reminder.

## Commands
`git push -u origin <branch>`, then `gh pr create --draft --base <base_branch> --head <branch> --title "<title>" --body-file <file>`.
Record `ledger.py set <id> --stage pr-draft --pr <url>`.
No GitHub login available (e.g. a VM session): write the body to `{{AUTOMATION_DIR}}/pending-prs/<branch>.md` and tell {{OWNER_NAME}} the two commands to run.

## Tracker line after the PR
Right after the draft PR exists, ONE ClickUp comment with exactly: `UI changes done`. One per ticket; for a grouped PR, one on each ticket.
Re-read the ticket status first; not the configured status any more -> post nothing.

## GROUPING: tickets that change the same file go in ONE draft PR
List each ready ticket's files (`git diff --name-only origin/<base>...<branch>`). Tickets sharing any file form a group (transitively). Per group: in
the main checkout (clean apart from local-only files) a new branch from origin/<base>, cherry-pick each ticket's commit in order (one commit per
ticket, each with its own message), resolve conflicts carefully, rerun the new tests + the test gate, then ONE draft PR:
- Title `<Area>: <what now works> (<id1>, <id2>)`; body: one `Ticket:` line per ticket, Problem / Root cause / Fix / Verification per ticket
  (`### <id>`), shared Known limits / Deploy / Screenshots.
- `ledger.py set <each id> --stage pr-draft --pr <url>`.
Tickets with no shared file get their own PR. Create the draft PR right after verify passes; then inform {{OWNER_NAME}} (ticket, PR link, what
changed, anything not verified).

## Earlier PR on request
If {{OWNER_NAME}} asks for the PR before verify: create it with "Screenshots: to be added" and "Not verified" filled honestly, run step 4, then update
the body (`gh pr edit --body-file`) with screenshots and results.

## Clean up after the PR
When the draft PR exists AND its screenshots render: `ledger.py set <id> --evidence-uploaded` for every ticket in it, then `ledger.py cleanup --id <id>`
(deletes the ticket's logs, screenshots, pending-prs files and findings; id, title, stage and PR link stay). Delete video work folders you made.
Never delete local branches unless {{OWNER_NAME}} asks.

## Slack (skills/slack_dm.md, one per trigger per ticket)
- The diff touches one of the repo's `review_files` (settings.json) and REVIEWER_* is set: after the draft PR exists, ONE review DM to the reviewer.
- The ledger says "NOT REPRODUCED ON TEST ENVIRONMENT": after the draft PR exists, ONE DM to {{OWNER_NAME}}: ticket link, PR link, one line on the change,
  "Needs a check on the live environment (could not reproduce on the test environment)."
