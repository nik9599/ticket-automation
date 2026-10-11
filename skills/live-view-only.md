# DEFAULT live-environment whitelist (any repo, any product): the ONLY allowed actions
Used whenever a repo has no own `skills/playbooks/<repo>-live-allowed-actions.md` (owner-taught, local, not in git).
Applies to EVERY environment that is not the ticket's own repo test environment: production admin, customer-facing sites and accounts, other teams'
"test" or "demo" environments, with production OR local code. Anything not on the ALLOWED list is forbidden: do it on the test environment instead.
When unsure whether a click is allowed: it is NOT. Closing a modal: use the X icon. Never click a modal's action button.

## ALLOWED (look only)
- Navigation: menus, page tabs, Back links, pagination, opening a detail page.
- Reading: scrolling, expanding sections, hovering tooltips, reading settings, "View" / "View details" pages, DevTools Network (GET requests).
- Search boxes and list filters, only to narrow a list.
- Open then close with X, changing nothing: edit modals, editors, confirm dialogs, previews.

## FORBIDDEN (examples, not complete)
- Any button that saves, confirms or creates: Save, Update, Apply, Submit, Confirm, Create, Add, Delete, Remove, Clone, Import, Export/Send,
  Generate, Enable/Disable, Activate/Deactivate, Publish, Redeem, Claim, Join / Sign up, Pay / Checkout.
- Changing any setting control (checkbox, toggle, radio, select, text field on a settings page): some save immediately. A Save bar appeared by
  accident -> click Discard, never Save, and tell the user.
- Account or record actions: cancel, pause, resume, skip, reschedule, edit, refund, charge, send email/SMS, bulk actions.
- Signing in with a password, entering codes, completing a checkout or a form.
- Anything that sends POST / PUT / PATCH / DELETE or a GraphQL mutation. Keep DevTools Network open; an unexpected non-GET request -> stop,
  ledger note, tell the user.

## Making it stricter or more exact for a repo
Teach a playbook: copy `skills/playbooks/_template-playbook.md` to `skills/playbooks/<repo>-live-allowed-actions.md`, list the exact allowed
clicks for that product, and add a row to `skills/playbooks/INDEX.md`. A repo playbook may only be narrower or more specific than this file.
