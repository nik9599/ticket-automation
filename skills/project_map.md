# STEP 0: project profile (runs per repo on the first run, when the profile is stale, or on `run.py --map <repo>`; only after the owner allowed the scan)

Goal: write everything this automation must know about ONE repo, so no project-specific fact has to live in the generic skills.
Steps 1-5 read your output for every ticket. You only READ the repo. You only WRITE inside `<project_dir>` (given in the repo config, = {{AUTOMATION_DIR}}/projects/<repo>/).
No branch, no commit, no install, no dev server, no browser, no tracker, no Slack.

Input (prompt): repo name and its config from settings.json (path, ticket_match, test_environment, review_files, focus_keywords) plus the old profile if any.

## 1. Read (origin only)
- `git -C <path> fetch -q origin` (if it fails, use the local origin refs and say so). Base branch = `git -C <path> symbolic-ref --short refs/remotes/origin/HEAD`
  (strip `origin/`), unless the repo config sets base_branch. Work from `git ls-tree -r --name-only origin/<base>` and `git show origin/<base>:<file>`,
  never the working tree (the owner may have local edits).
- Read fully: README*, CLAUDE.md / AGENTS.md / CONTRIBUTING*, docs/ index files, every package manifest (package.json, pyproject, pom.xml, build.gradle,
  Gemfile, go.mod, composer.json, Makefile) and their scripts, CI config (.github/workflows/*), test configs (jest/vitest/playwright/pytest...), .gitignore,
  example env files. Docs win over your guesses.
- `git log --oneline -30 origin/<base>` for active areas; `git ls-tree -d` of the top 3 levels for the layout.

## 2. Decide
- Surfaces = the separately deployed or separately used UIs/apps (e.g. admin app, customer-facing area, storefront script, browser/mobile extension,
  embedded widgets) + `backend` if the repo has server code. Name them with short lowercase keys. 2-8 surfaces is normal.
- Backend paths: server code, migrations, infra. This automation only changes front-end code, so these are "never edit" for fixes.
- Commands: take EVERY command from the manifests/CI; never invent one. If something is missing (no unit tests, no lint), write "" and say so.
- Local-only files: files a developer edits locally that must never be committed (dev config pointed at a test environment, local proxy/interceptor
  files, per-developer app config). Evidence: docs, .gitignore comments, `*.local.*`, example files. When unsure, leave it out.
- Existing test paths: a regex matching this repo's test files (step 3 may add new tests, never change existing ones).
- Focus keywords: words in ticket titles that point at the most customer-visible surfaces (only if docs or folder names make it clear).
- Guard action words: URL words that mean a state-changing action in this product (e.g. cancel, delete, refund, publish); used by tools/guard.js.

## 3. Write
1. `<project_dir>/profile.json` (valid JSON, exactly these keys):
```
{
  "repo": "<name>", "scanned_at": "<YYYY-MM-DD>", "scanned_commit": "<full sha of origin/<base>>", "base_branch": "<base>",
  "summary": "<one line>",
  "context_docs": ["<repo-relative doc paths worth reading>"],
  "surfaces": { "<key>": { "code": "<main folder>", "what": "<one line>", "runs_in": "<where users see it>", "map": "<key>.md", "user_facing": true } },
  "backend_paths": ["..."], "never_change": ["<generated / vendored / deprecated / migration paths>"],
  "generated_files": [ { "source": "...", "output": "...", "rebuild": "<command>" } ],
  "local_only_files": ["<regex>"], "existing_tests_regex": "<regex>",
  "commands": { "install": "", "start": "", "test_related": "<use {files} for the changed files>", "test_all": "", "test_gate": "<suite that must always pass, or empty>",
                "lint": "", "typecheck": "", "format": "", "build": "" },
  "extra_allowed_tools": ["Bash(<command prefix>:*)", "..."],
  "focus_keywords": [], "surface_keywords": { "<key>": ["<ticket words that point at this surface>"] },
  "guard_action_words": [],
  "deploy_notes": { "<key>": "<what deploys it>" },
  "live_environment": "<what live / customer environments are for this product and how tickets name them>"
}
```
   `extra_allowed_tools` = one `Bash(<prefix>:*)` per non-empty command (e.g. `Bash(npm run lint:*)`), nothing broader than the command itself
   (never `Bash(npm:*)`, never sudo, never rm).
2. `<project_dir>/project.md` from `{{AUTOMATION_DIR}}/projects/_template-project.md` (keep its headings).
3. `<project_dir>/<surface>.md` for every surface except backend, from `{{AUTOMATION_DIR}}/projects/_template-surface.md`. The Feature -> file -> twin table
   is the most useful part: 10-25 rows, concrete paths (search the same API path / label key / component name in the other surface folders).
4. Re-scan: keep every line of "Rules that cost time before" and "Deprecated / do not change" from the old files unless the code proves it wrong
   (list those in your report). Add matching lines from `python3 {{AUTOMATION_DIR}}/tools/lessons.py show --repo <repo> --surface <key>` (may be empty). Keep `lessons.md` and `test-baseline.md` in project_dir as they are (they are the repo's learned memory).
5. Every path you wrote must exist on origin/<base>: `python3 {{AUTOMATION_DIR}}/tools/check_project.py <repo>` and fix every MISSING line.

## Rules
- Plain short lines, repo-relative paths. A map is 60-150 lines.
- No secrets, tokens, passwords, customer data, customer/merchant names or production URLs with ids in these files.
- If the repo cannot be understood well enough (no docs, no manifests), write what you know, set `"summary": "PARTIAL: <why>"` and say so.

## End
One line per file: `WROTE <file> (<n> lines)`, then `MAP DONE <repo>` (or `MAP FAILED <repo>: <why>`).
