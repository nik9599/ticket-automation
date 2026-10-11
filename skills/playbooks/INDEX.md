# Playbook index (step 2: replicate and classify)
Read this file FIRST in step 2 (after the project files), then open every playbook whose trigger matches the ticket and follow it. Name the playbooks you used in the ledger note
("PLAYBOOKS: a.md, b.md") and in the handover file. If nothing matches, continue with the standard flow and write "PLAYBOOKS: none".
Order: guardrails.md > the playbook that matches the ticket most specifically > the standard flow in replicate_classify.md.

Playbooks are owner-taught and describe YOUR projects, so they are local and not in git (only this INDEX and `_template-playbook.md` are).
A playbook named in a skill or in guardrails that does not exist on this machine: skip it. For live environments use `skills/live-view-only.md`
unless a `<repo>-live-allowed-actions.md` playbook exists here.

## Adding a playbook (after the owner shows you a ticket type, e.g. in a Loom)
1. Copy `_template-playbook.md` to `<short-name>.md` (When it applies / Steps / Record in the ledger).
2. Add one row below.
3. Run one sample ticket of that type with `python3 run.py --ticket <id>`.

| Trigger (ticket title, tags, description, Intercom, video) | Playbook |
|---|---|
| any action on a live environment (view mode only) | `<repo>-live-allowed-actions.md` if present, else ../live-view-only.md |
