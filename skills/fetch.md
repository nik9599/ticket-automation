# STEP 1: fetch (global)

> LIVE RULE (whole step): read-only everywhere. The only environment where anything may change is the ticket repo's test environment, and this step
> changes nothing at all. See guardrails.md.

FIRST COMMAND OF EVERY RUN: `python3 {{AUTOMATION_DIR}}/ledger.py batch start` (opens the batch note "Batch-N · <date>"; `ledger.py add/set` fill it
with every ticket that needs {{OWNER_NAME}}; cleanup at the end writes the "· Analytics" note).

Goal: top up each enabled repo's queue to its batch size with fresh tickets. Read-only on ClickUp. No code, no comments.
Inputs (prompt): automation defaults, the clickup block, and every enabled repo's config (ticket_match, focus_keywords, profile with
`surface_keywords` / `focus_keywords` / `surfaces`). Ledger CLI: `python3 {{AUTOMATION_DIR}}/ledger.py`.

Step 0, reconcile (before topping up): for every ledger ticket whose stage is NOT moved-out/done/done-config/done-be/skipped (so INCLUDING needs-info,
needs-human, pr-draft and every in-progress stage), read its current ClickUp status. If it is no longer the configured status (a person moved or
closed it), run `ledger.py set <id> --stage moved-out --force --note "ClickUp status now <status>"` then `ledger.py cleanup --id <id>`
(its local branch stays). Never touch the ClickUp ticket itself. Every later step re-checks the status right before posting anything.

SPEED RULES:
- Reconcile with as few calls as possible: ONE `clickup_filter_tasks` query (all statuses, the configured list), match by id; `clickup_get_task`
  only for a ticket that query did not return.
- Rank first, check later: sort candidates by the ranking below using only cheap fields (title, tags, priority, task order), THEN check them IN
  GROUPS OF 5: in ONE turn send all read calls for 5 candidates as parallel tool calls (clickup_get_task with description,
  clickup_get_task_comments, and `gh search prs <id> --owner {{GITHUB_OWNER}} --json url,state,title`; next turn the clickup_get_threaded_comments
  calls for comments with replies). Decide the 5, run their `ledger.py add/set` together, then the next group if room is left. Never one ticket
  per turn. Do not read comments for candidates below the last group you needed.
- IMPROVEMENTS ARE QUEUED, NOT SKIPPED: an IMPROVEMENT = a tag contains "feature" or "improvement" and no tag contains "bug", OR the ticket asks for
  a new capability rather than reporting a defect. It goes through the TICKET FILTER like any clean ticket and ranks in the "improvement" tier.
  Record `ledger.py set <id> --note "IMPROVEMENT (tag <tag>)"` after `add`; list improvements separately in the report.

For each enabled repo:
1. room = batch_size - `ledger.py open-count --repo <repo>`. If room <= 0, skip this repo. open-count leaves out tickets that only wait on
   {{OWNER_NAME}} (pr-draft, preprod-wait, preprod-verified), so old drafts never block new tickets.
   ROOM IS A HARD CAP: every ticket put in stage queued this run (new `add` or re-queue) uses 1 room. Never queue more than `room` for a repo.
   Handle every enabled repo; in the report list room and added count for each.
2. Query ClickUp (clickup_filter_tasks) on the configured list, status and assignee. Page until you have all. If the connector fails, report and stop.
3. Drop a task if ANY of these hold:
   - `ledger.py known <id>` says yes.
   - a comment contains "[auto-done]", "[auto-triage]" or a PR link.
   - an earlier agent or developer already investigated it ("Investigated", "Skipping for now", "Root cause found", "flagging", "draft PR",
     "not safely fixable"): `ledger.py add` then `ledger.py set <id> --stage skipped --note "<why>"`, next candidate.
   - CLEAN-TICKET RULE: pick ONLY clean tickets. Skip (ledger add + `--stage skipped --note "<why>"`) if ANY comment (incl. replies) is written by a
     DEVELOPER: {{CLICKUP_ASSIGNEE}}, {{OWNER_NAME}}, {{REVIEWER_NAME}}, {{DEVELOPER_NAMES}}, or any other user who writes about code, a fix, a root cause
     or a timeline ("checking", "need N weeks") - even a one-word "checking". Support-team notes (forwarded links, summaries) do NOT make it unclean.
     Also skip if a PR already exists: `gh search prs <ticket id> --owner {{GITHUB_OWNER}} --json url,state,title`, plus any pull-request link in the
     ticket. Any open, draft or merged PR -> skip with note "PR exists: <url>". Also skip if another developer is assigned and has commented.
     When unsure whether a comment is from a developer, skip and list it in the report.
   - TICKET FILTER (for each candidate above the cut, after the clean and PR checks, BEFORE `add`; ticket text, tags and attachment list only).
     A ticket that fails it does NOT use room:
     - CLEAR FEATURE REQUEST = DOABLE: the request is clear, names WHERE it should go, and the feature ALREADY EXISTS elsewhere in the product.
       Queue it; `ledger.py set <id> --note "CLEAR FEATURE: copy <existing place> to <new place>"`.
     - DETAILED NEW FEATURE = DOABLE when ALL hold: (a) WHAT it must do, clear enough to write a test from; (b) WHERE it goes (screen / menu /
       setting / surface); (c) the RULES (when it shows or applies, success / error behaviour); (d) the exact UI TEXT for anything new (or reuse);
       (e) front-end only, or the backend data it needs already exists. Queue it; note "DETAILED FEATURE: <one line> | WHERE: <place> | RULES: <list>".
     - FEATURE REQUEST WITHOUT ENOUGH DETAIL (any of (a)-(e) missing, or new backend work): `ledger.py add` then `--stage needs-info --note
       "FEATURE REQUEST: <ask> | MISSING: <what/where/rules/text/BE> | NEEDED: product/dev decision on the spec"`. No room used. Never invent spec or text.
     - DATA-DISPLAY REQUEST ("show X on screen Y"): queue it with `--note "TRIAGE: data-display - <what data, which screen>"`; step 2 checks
       whether the screen already receives the data.
     - EMPTY TICKET (no description, attachment, video, support link or environment link): `ledger.py add` then `--stage needs-info --note
       "EMPTY TICKET: missing <item>"`. No room used.
     - Otherwise it is a defect report: queue it.
   - UNMAPPED RESCUE: before listing a task as Unmapped, take a distinctive screen/setting name from it and
     `git grep -il '<name>' origin/<base_branch>` in each enabled repo. If exactly ONE repo has it, map it there (note "MAPPED BY CODE: <file>");
     zero or several -> Unmapped.
   - it matches no repo, or more than one (report under "Unmapped/Ambiguous"; do not guess).
4. Match a task to a repo with its `ticket_match`: title_prefixes (case-insensitive prefix), tags, exclude_title_prefixes.
5. Rank. A FOCUS task = its title or tags contain one of the repo's `focus_keywords` (settings) or the profile's `focus_keywords`. If the title alone
   is unclear, read the description and use the profile's `surfaces` (what / runs_in) to decide. Pick in the order of `defaults.ranking_tiers`
   (an improvement goes ONLY to the improvement tier; inside it sort by priority then oldest). Inside a tier sort by `defaults.ranking` (bug tags,
   overdue due date, oldest; use task order oldest-first as the created-date proxy). Show each picked task's tier in the report.
6. For the top `room` tasks: `ledger.py add --id <id> --repo <repo> --title "<title>" --link <url> --tags a,b --priority <p> --created <date>`,
   then `ledger.py set <id> --note "FOCUS: <yes|no> (<tier>) - SURFACE GUESS: <profile surface key or unknown> - <one-line reason>"`.

Finish with a short report: per repo room, added (ids + titles), filtered to needs-info (ids + reason), skipped and why, unmapped list.
NEVER change anything in ClickUp in this step: no status, assignee, priority, fields, comments or tags. Only filter/get/search/comments (read).
