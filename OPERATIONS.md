# Operations

Day-to-day commands and behaviour. Setup and the big picture are in [README.md](README.md).

## Run
| Command | What it does |
|---|---|
| `python3 run.py` | Step 0 check for every enabled repo, then fetch + every enabled step for every enabled repo |
| `python3 run.py --dry-run` | Print what it would run; changes nothing |
| `python3 run.py --repo <name> --step <step> --limit 2` | One repo, one step, at most 2 tickets |
| `python3 run.py --ticket <id> [--requeue]` | Only this ticket (fetch adds it first if it is new) |
| `python3 run.py --map <name>` | Re-scan that repo into `projects/<name>/` (asks permission) |
| `python3 run.py --board` | Ticket states and disk use |
| `python3 run.py --cleanup` | Delete logs and evidence of finished tickets |
| `touch STOP` | Stop at the next ticket boundary (remove the file to run again) |

One Claude session at a time, one ticket per session, one repo at a time. The runner waits while the machine is busy
(`automation.json` `max_load_per_core`) and keeps a lock in `state/.lock`.

## Step 0 and scan permission
At the start of every run, each enabled repo's `projects/<repo>/` is checked:
- **missing** (first run): the repo can't run until it is scanned.
- **stale**: older than `profile_max_age_days`, a path it names no longer exists on origin, or many files changed since the scan.
- **ok**: used as it is.

When a scan is needed, `SCAN_PERMISSION` in `settings.json` decides:
- **`ask`** (default): asks `Allow the scan? [y/N]` in the terminal. Without a terminal (scheduled runs, Slack triggers) it does not scan; it prints the `--map` command to run yourself.
- **`always`**: scans without asking.
- **`never`**: doesn't scan.

When a scan is refused, a stale profile is still used, and a repo with no profile is skipped for that run.

Commands:
- `python3 config.py check` shows the profile state of every repo.
- `python3 tools/check_project.py` lists paths in the project files that no longer exist on origin.

## Videos in tickets (watch skill)
Step 2 runs `python3 <watch skill>/scripts/watch.py <url> --engine <WATCH_ENGINE> --question ... --out-dir evidence/<id>/video` and reads the frames.
`python3 config.py check` reports when the skill is missing or not set up; fix it with `/watch` once in an interactive Claude Code session.
Headless runs cannot answer the skill's setup questions, so setup must be done beforehand. A private video (login needed) usually cannot be
downloaded: step 2 then falls back to the browser and notes a BLOCKER.

## Stages
queued -> replicating -> replicated -> classified -> fixing -> fixed-local -> verifying -> verified -> pr-draft -> done.

Side exits:
- `needs-info`, `needs-human`, `not-reproducible`
- `done-config`: one config comment on the ticket
- `done-be`: one "For BE team:" comment
- `skipped`: already handled, or the owner said leave it
- `moved-out`: the ticket left the configured status

If the owner says "leave this" for a ticket:
```bash
python3 ledger.py set <id> --stage skipped --force --note "Skipped by owner"
```

## Ledger
`python3 ledger.py` with:
- `board`, `show <id>`, `set <id> --stage ... --note ...`, `next`, `open-count`
- `branchname`, `recover`, `cleanup [--id <id>]`, `disk`
- `timings [--since YYYY-MM-DD] [--id X]`
- `batch start|finish|status|sync`

Ticket records are in `state/tickets/*.json`.

## What a run leaves behind
- `state/timings.csv`: one line per Claude session (step, repo, ticket, seconds, exit code).
- `state/stage-timings.csv`: one line per stage change.
- `state/digest-latest.md`: end-of-run digest (ready to test with checkout commands, needs you, ended without a fix, where the time went).
- Apple Notes (`NOTES_FOLDER`): "Batch-N · <date>" with every ticket that needs you, and an "· Analytics" note with minutes per step. `ledger.py batch sync` rewrites the notes if Notes was not reachable.
- `tools/audit.py` runs after every fix and verify session. A violation sets the ticket to needs-human and stops the run. It checks:
  - no local-only file committed;
  - no existing test changed;
  - the working tree is clean;
  - the profile's optional `cleanup_check`.

## Testing and PR flow
1. Leave the repo alone while the automation runs. Only local-only files (profile `local_only_files`) may stay modified.
2. Each fix is one commit on its own local branch from origin/<base>.
3. After verify passes, the draft PR is opened. Test any branch with `git checkout <branch>`.
4. Tickets that share a file are grouped into one draft PR (one commit per ticket).
5. Once the PR's screenshots render, `ledger.py cleanup` deletes the ticket's logs, screenshots and findings, plus its Claude session transcripts. Only the id, title, stage and PR link stay. Live-environment logs are kept for `live_log_retention_days`.

## Local-only mode
If the owner asks to keep code local: the ticket branch is made, but the change stays uncommitted on it.

## Running from the Claude app on a VM (known quirks)
- Connect both this folder and the repo folder, and allow file deletion on both. git must be able to remove its own `.lock` files.
- `git fetch` may have no GitHub login inside a VM: the run uses the local origin refs. Fetch on the host first for the newest base.
- Without a GitHub login the PR step writes the body to `pending-prs/<branch>.md` and gives you the commands to run.

## Backups
Before editing an automation file: one `<file>.bak` next to it, overwritten each time. No dated or numbered copies. `*.bak` is git-ignored.
