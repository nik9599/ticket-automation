# SKILL: root cause + regression research (bug tickets, any repo)

Why : a bug must be fixed so that the OLD behaviour and every NEWER feature built on the same code keep working.
To do that we must know WHERE the code breaks, WHY it breaks THIS time, and WHICH change made it break, before anyone writes a fix.
"The cause looks clear from the code" is not enough: one fix that creates a new issue is worse than no fix.

Used by: step 2 (MANDATORY for every bug ticket once the issue is seen on the test environment or a live one, and for every bug that could not be
reproduced but has a likely cause), and step 3 (reads the output, must respect "Must keep working"). Read-only: no repo edits, no Save anywhere.
Repo = the ticket's repo (repo config path). Always search `origin/<base>` after `git fetch -q origin <base>` (base = $TICKET_BASE_BRANCH).

## Part A. Live environment: view only, log every step
View-only on a live environment is allowed (allowed clicks: skills/live-view-only.md, or the repo's live-allowed-actions playbook). Every single
step there is logged, in order, in `{{AUTOMATION_DIR}}/evidence/<id>/live-log.md`:
```
| # | time | environment | URL (no tokens/query secrets) | action (navigate / read / open modal / close X / scroll) | what I saw | non-GET requests seen |
```
- Write the row right after the step, not at the end from memory.
- "non-GET requests seen" must be "none". Any POST/PUT/PATCH/DELETE or GraphQL mutation: stop at once, log it,
  `ledger.py set <id> --note "LIVE ALERT: <request>"`, and send the blocker DM (skills/slack_dm.md trigger 2).
- No personal data in the log (names, emails, addresses, phone); a record id is fine.
- Finish with `ledger.py set <id> --evidence evidence/<id>/live-log.md --note "LIVE LOG: <n> steps, view only, non-GET none"`.
- Never type into fields, never click Save/Update/Confirm or a modal's action button, never inject scripts. Debug logs only through local code
  with a method project.md or a playbook documents, and those steps are logged too.

## Part B. Where does it break? (breaking point)
1. Write the symptom in one line: expected vs actual, on which screen, for which data (record type, setting, surface, locale, device).
2. Follow the data from the screen back to its source and write the chain with file:line:
   rendered element -> component/function that decides it -> the data it reads (props / state / API field / injected config) -> where that data comes from.
   Find the element by a unique class or text (`git grep -n '<class or label>' origin/<base> -- <surface paths>`).
3. Mark the FIRST hop where the value or the decision becomes wrong. That is the breaking point: `BREAKS AT: <file>:<line> <function> - <what goes wrong>`.
4. Prove it: a local debug log value, a repro on the test store, the Network response, or a unit-level reasoning with the exact input that triggers it.
   Write "PROVEN BY: <repro | debug log | network | code-only>". code-only = say how sure (certain / likely).

## Part C. Why now? (what change made it break)
Find the commit that introduced the breaking line or removed the old protection:
- `git log -L <start>,<end>:<file> origin/<base> | head -200`  (history of exactly those lines)
- `git log -S '<key identifier or string>' --oneline origin/<base> -- <file or folder>`  (when the code appeared or vanished)
- `git blame -w origin/<base> -L <start>,<end> -- <file>`
- For each suspect commit: `git show <sha> --stat`, `git show <sha> -- <file>`, and its PR (run gh inside the repo): `gh pr list --search <sha> --state merged --json number,title,url`
  then `gh pr view <n> --json title,body,mergedAt` to learn WHY that change was made (the newer feature it serves).
- Compare old vs new: `git show <sha>^:<file>` vs `git show <sha>:<file>` around the breaking point.
Classify it:
- **regression**: worked before <sha> (<PR title, date>), broke because <reason>.
- **never worked**: the case was never handled (e.g. a plan type / setting combo added later elsewhere); name the missing case.
- **data / config**: code is right, the user's data or setting triggers a valid path; say which setting (then the verdict may be config).
- **external**: a platform / third-party change; say what and the evidence.
Also check if the same symptom was fixed before: `gh search prs --owner {{GITHUB_OWNER}} "<keywords>" --json url,title,state` and `git log --grep '<keyword>' origin/<base>`.
A previous fix that got undone, or a fix in one copy but not its twin, is a common cause.

## Part D. Hypotheses (do not stop at the first plausible cause)
List 2-3 candidate causes. For each: evidence for, evidence against, how you tested it, result (confirmed / ruled out).
Only one may be "confirmed". If none can be confirmed, say "CAUSE UNPROVEN" and choose needs-info / needs-human instead of guessing.

## Part E. Impact: what must keep working
1. Callers and users of the breaking function/component/field: `git grep -n '<name>' origin/<base> -- <every surface code root from the profile>`.
   List every place, and which feature/screen it serves.
2. Twins: the same rule in other copies (duplicated blocks, another surface, server vs client, another repo). From the surface maps.
3. Feature matrix (the old feature AND the newer feature from Part C, and nearby options):
```
| Case | Settings / data | Behaviour today | Must be after fix |
| old feature: ...            | ... | ok      | unchanged |
| new feature (PR #n): ...    | ... | ok      | unchanged |
| the bug case                | ... | broken  | fixed     |
```
   Include on/off of the related settings, record types, surfaces, locales, mobile.
4. Fix boundary: the smallest place to fix it so every row holds. Say why fixing it elsewhere (e.g. reverting the PR) would break a row.

## Part E2. Never come back 
Goal of every bug fix: the same issue must NEVER come back as long as nobody changes that code again. So the research must cover the whole bug class,
not only the reported case:
1. Variants: list every input that reaches the breaking point (all record types, settings on/off, surfaces, locales/currencies, mobile/desktop,
   empty/null/long values, first load vs after navigation, slow network). Mark which ones break today. The fix must cover ALL breaking variants.
2. Every copy: the same logic in twins (duplicated blocks, generated/minified files, other surfaces). A fix in one copy only = it comes back.
3. Root, not symptom: reject fixes that only hide the symptom: a setTimeout/delay, a retry loop, a CSS hide, a try/catch that swallows the error,
   a special case for one customer/record id, a data fix on one account. Say in root-cause.md why the chosen fix boundary removes the cause.
4. Lock test: name the permanent regression test that will FAIL if the bug ever comes back (bug case + each variant), kept in the repo.

## Part F. Output
Write `{{AUTOMATION_DIR}}/evidence/<id>/root-cause.md` with these headings:
`Symptom` / `Breaks at` / `Proven by` / `Why now (commit, PR, date, type)` / `Hypotheses` / `Callers and twins` / `Must keep working (feature matrix)` / `Fix boundary` / `Tests step 3 must add` (one per matrix row that the change can affect: bug case + old + new) / `Live log` (path or "no live visit").
Then: `ledger.py set <id> --evidence evidence/<id>/root-cause.md --root-cause "<2-4 sentences: breaks at, why now, fix boundary>" --note "ROOT CAUSE: <type> - <sha/PR> | MUST KEEP: <n> cases"`.
Copy `Breaks at`, `Why now`, `Must keep working` and `Tests step 3 must add` into handover.md (sections of the same names).

## Self-check (all yes before you leave)
- Breaking point is a file:line, and it says how it was proven.
- Why-now names a commit/PR (or says never-worked / data / external with evidence).
- At least 2 hypotheses, exactly one confirmed (or CAUSE UNPROVEN).
- Feature matrix lists the old feature, the newer feature and the bug case.
- Every live-environment step is in live-log.md with non-GET = none.
