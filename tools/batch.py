#!/usr/bin/env python3
"""Batch notes for the owner in Apple Notes (folder = NOTES_FOLDER in settings.json). Owner rule 2026-10-11.

  python3 ledger.py batch start    # first thing in a run: opens note "Batch-N · <date>" (N = runs started that day)
  python3 ledger.py batch finish   # end of run: writes note "Batch-N · <date> · Analytics" and closes the batch
  python3 ledger.py batch status   # open batch + counts
  python3 ledger.py batch sync     # rewrite both notes from the JSON (e.g. after a run where Notes was not reachable)

While a batch is open, every `ledger.py add` / `set` stage change is recorded in state/batches/<date>-<n>.json.
When a ticket lands in a stage that needs the owner, the batch note gets its full ClickUp URL and what is needed,
under the step it came from. The JSON is the source; the notes are rewritten from it, so a Notes failure never
breaks the ledger or the run."""
import html, json, os, re, subprocess, sys, time, datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import config  # settings.json -> {{KEY}} values
BATCHES = Path(os.environ.get("TICKET_STATE_DIR", HERE / "state")) / "batches"
CURRENT = BATCHES / "current.json"
FOLDER = config.settings().get("NOTES_FOLDER") or "Ticket Automation"
STALE_HOURS = 6

S2, S3, S4, S5, S6 = "Step 2 · replicate", "Step 3 · fix", "Step 4 · verify", "Step 5 · PR", "Step 6 · preprod"
STEPS = ["Step 1 · fetch", S2, S3, S4, S5, S6]
# stage a ticket LEAVES -> the step that was running
STEP_OF = {"queued": S2, "replicating": S2, "replicated": S2, "not-reproducible": S2, "classified": S3, "fixing": S3,
           "fixed-local": S4, "verifying": S4, "verified": S5, "pr-draft": S6, "preprod-wait": S6, "preprod-verified": S6}
# stages where a step is actually working (time in them = step time); the rest is queue wait or waiting on the owner
WORK = {"replicating": S2, "replicated": S2, "fixing": S3, "verifying": S4, "verified": S5}
QUEUE = {"queued", "classified", "fixed-local"}
NEEDS_YOU = {"needs-info": "Needs info", "needs-human": "Needs you", "not-reproducible": "Not reproduced",
             "failed": "Failed", "pr-draft": "Draft PR ready: review and test"}
WHY = [(r"timed? ?out", "hit the step timeout"), (r"max attempts", "hit max attempts"),
       (r"denied|permission|classifier", "a permission was denied, so it waited or worked around it"),
       (r"\bloom\b", "watched a Loom video"), (r"intercom", "read the Intercom conversation"),
       (r"live env|live-log|customer site", "looked at a live environment (view only)"), (r"sign-?in|saml|login", "test-environment sign-in"),
       (r"dev server|npm start|localhost:\d+", "started the local dev server"), (r"playwright|e2e", "ran Playwright / e2e"),
       (r"jest|test:security|\d+ suites", "ran test suites"), (r"pre-existing|baseline", "had to prove failures were pre-existing"),
       (r"\btsc\b", "ran the type check"), (r"not reproduc|NOT REPRODUCED", "could not reproduce"),
       (r"screenshot|frames", "read screenshots / video frames"), (r"copies:|twins|callers", "checked copies of the code"),
       (r"retr(y|ied)|again", "retried")]


def now():
    return dt.datetime.now().astimezone()


def iso(d=None):
    return (d or now()).strftime("%Y-%m-%dT%H:%M:%S%z")


def parse(s):
    try:
        return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")
    except (TypeError, ValueError):
        return None


def load(p):
    return json.loads(p.read_text())


def save(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp"); tmp.write_text(json.dumps(d, indent=1)); tmp.replace(p)


def current():
    if not CURRENT.exists():
        return None, None
    try:
        p = BATCHES / load(CURRENT)["file"]
        return p, load(p)
    except (OSError, ValueError, KeyError):
        return None, None


# ---------------- Apple Notes ----------------
_CREATE = '''on run argv
  tell application "Notes"
    if not (exists folder (item 1 of argv)) then make new folder with properties {name:(item 1 of argv)}
    set n to make new note at folder (item 1 of argv) with properties {body:(item 2 of argv)}
    return id of n
  end tell
end run'''
_UPDATE = '''on run argv
  tell application "Notes" to set body of note id (item 1 of argv) to (item 2 of argv)
end run'''


def _osa(script, *args):
    try:
        r = subprocess.run(["osascript", "-e", script, *args], capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def write_note(note_id, body):
    """Update the note; create it if it is new or was deleted. Returns the note id (None if Notes is unreachable)."""
    if note_id and _osa(_UPDATE, note_id, body) is not None:
        return note_id
    return _osa(_CREATE, FOLDER, body)


def e(s):
    return html.escape(str(s or ""))


def mn(x):
    return f"{x:.1f}" if x < 10 else f"{x:.0f}"


def link(u):
    return f'<a href="{e(u)}">{e(u)}</a>' if u else ""


# ---------------- recording (called from ledger.py) ----------------
def needed_text(stage, t, note):
    if stage == "pr-draft":
        return f"Draft PR {t.get('pr_url') or '(link not recorded yet)'}" + (f" · branch {t['branch']}" if t.get("branch") else "")
    note = note or next((n["text"] for n in reversed(t.get("notes") or [])), "")
    parts = re.findall(r"(?:NEEDED:|OPEN DECISIONS?|DECISION:|BLOCKER: (?!none)|For BE team|needs? (?:the owner|owner|live)|Needs the owner|needs? " + re.escape(config.settings().get("OWNER_NAME", "owner")) + r")[^|]*", note, re.I)
    return (" | ".join(p.strip() for p in parts) or note).strip()[:600]


def record(t, frm, to, minutes, note):
    """One stage change. Never raises: the ledger must not break because of notes."""
    try:
        p, b = current()
        if not b:
            return
        ev = {"ts": iso(), "ticket": t["id"], "repo": t.get("repo"), "title": t.get("title"), "link": t.get("link"),
              "from": frm, "to": to, "minutes": round(minutes or 0, 1), "note": (note or "")[:1500],
              "attempts": (t.get("attempts") or {}).get(frm, 0)}
        if to in NEEDS_YOU:
            ev["step"] = STEP_OF.get(frm, "Other")
            ev["needed"] = needed_text(to, t, note)
        b["events"].append(ev); save(p, b)
        if to in NEEDS_YOU:
            b["note_id"] = write_note(b.get("note_id"), batch_body(b)); save(p, b)
    except Exception as ex:  # noqa: BLE001
        print(f"(batch note not updated: {ex})", file=sys.stderr)


# ---------------- note bodies ----------------
def batch_body(b):
    L = [f"<h1>{e(b['title'])}</h1>",
         f"<div>Started {e(b['started'][11:16])}" + (f" · finished {e(b['finished'][11:16])}" if b.get("finished") else " · running") + "</div><br>"]
    latest = {}
    for ev in b["events"]:
        if "needed" in ev:
            latest[(ev["ticket"], ev["step"])] = ev
    # a ticket that later moved on (e.g. needs-human -> verified) stays listed: the owner reads the batch after the run
    any_ = False
    for step in STEPS + ["Other"]:
        rows = [ev for (tid, s), ev in latest.items() if s == step]
        if not rows:
            continue
        any_ = True
        L.append(f"<h2>{e(step)}</h2><ul>")
        for ev in rows:
            L.append(f"<li><b>{e(ev['title'])}</b> ({e(ev['repo'])}, {e(NEEDS_YOU[ev['to']])})<br>{link(ev['link'])}"
                     f"<br>What I need: {e(ev['needed'])}</li>")
        L.append("</ul>")
    if not any_:
        L.append("<div>Nothing needs you in this batch so far.</div>")
    if b.get("finished"):
        L.append(f"<br><div>Time per step and slow tickets: note “{e(b['title'])} · Analytics”.</div>")
    return "".join(L)


def step_minutes(b):
    """{step: {ticket: minutes}} from work-stage time inside this batch (clipped to the batch window)."""
    start = parse(b["started"])
    out, wait, why = {}, {}, {}
    for ev in b["events"]:
        when = parse(ev["ts"])
        cap = (when - start).total_seconds() / 60 if when and start else ev["minutes"]
        m = min(ev["minutes"], max(cap, 0))
        if ev["from"] in WORK:
            s = WORK[ev["from"]]
            out.setdefault(s, {}).setdefault(ev["ticket"], 0)
            out[s][ev["ticket"]] += m
            why.setdefault((s, ev["ticket"]), []).append(ev)
        elif ev["from"] in QUEUE:
            wait[ev["ticket"]] = wait.get(ev["ticket"], 0) + m
    adds = [parse(ev["ts"]) for ev in b["events"] if ev["from"] is None]
    if adds and start:
        out["Step 1 · fetch"] = {"all": (max(adds) - start).total_seconds() / 60}
    return out, wait, why


def reasons(evs, mins, avg):
    text = " ".join(ev.get("note", "") for ev in evs)
    pts = []
    if avg and mins > avg * 1.3:
        pts.append(f"{mins / avg:.1f}× the step average ({avg:.0f} min)")
    att = max((ev.get("attempts") or 0) for ev in evs)
    if att > 1:
        pts.append(f"ran {att} times (retry)")
    seen = set()
    for rx, label in WHY:
        if label not in seen and re.search(rx, text, re.I):
            pts.append(label); seen.add(label)
    last = next((ev["note"] for ev in reversed(evs) if ev.get("note")), "")
    if last:
        pts.append("last note: " + last[:220] + ("…" if len(last) > 220 else ""))
    return pts or ["no notes recorded for this step"]


def previous_avgs(exclude):
    """Average minutes per step over earlier finished batches (for 'faster/slower than usual')."""
    acc = {}
    for f in BATCHES.glob("*-*.json"):
        if f.name == exclude:
            continue
        try:
            for s, v in (load(f).get("summary") or {}).items():
                a = acc.setdefault(s, [0, 0]); a[0] += v["total"]; a[1] += v["tickets"]
        except (OSError, ValueError, KeyError):
            pass
    return {s: t / n for s, (t, n) in acc.items() if n}


def analytics_body(b, file_name):
    per, wait, why = step_minutes(b)
    prev = previous_avgs(file_name)
    start, end = parse(b["started"]), parse(b.get("finished")) or now()
    tickets = {ev["ticket"]: ev for ev in b["events"]}
    final = {}
    for ev in b["events"]:
        final[ev["ticket"]] = ev["to"]
    L = [f"<h1>{e(b['title'])} · Analytics</h1>",
         f"<div>{e(b['started'][11:16])} → {e(iso(end)[11:16])} · {mn((end - start).total_seconds() / 60)} min wall time · {len(tickets)} tickets</div>"]
    outc = {}
    for s in final.values():
        outc[s] = outc.get(s, 0) + 1
    L.append("<div>Ended as: " + e(", ".join(f"{k} {v}" for k, v in sorted(outc.items()))) + "</div><br>")
    L.append("<h2>Time per step</h2><ul>")
    summary = {}
    for s in STEPS:
        if s not in per:
            continue
        vals = per[s]; tot = sum(vals.values()); n = len(vals); avg = tot / n if n else 0
        summary[s] = {"total": round(tot, 1), "tickets": n}
        cmp_ = ""
        if s in prev and prev[s]:
            d = (avg - prev[s]) / prev[s] * 100
            cmp_ = f" · {abs(d):.0f}% {'slower' if d > 0 else 'faster'} than earlier batches ({prev[s]:.0f} min)"
        L.append(f"<li><b>{e(s)}</b>: {mn(tot)} min" + (f" over {n} tickets, avg {mn(avg)} min" if s != STEPS[0] else "") + e(cmp_) + "</li>")
    if wait:
        L.append(f"<li><b>Waiting between steps</b> (queue): {mn(sum(wait.values()))} min</li>")
    L.append("</ul>")
    b["summary"] = summary
    L.append("<h2>Slowest ticket per step, and why</h2>")
    for s in STEPS[1:]:
        if s not in per or not per[s]:
            continue
        vals = per[s]; avg = sum(vals.values()) / len(vals)
        tid, m = max(vals.items(), key=lambda kv: kv[1])
        t = tickets[tid]
        L.append(f"<h3>{e(s)}: {mn(m)} min</h3><div><b>{e(t['title'])}</b><br>{link(t['link'])}</div><ul>")
        for r in reasons(why.get((s, tid), []), m, avg if len(vals) > 1 else 0):
            L.append(f"<li>{e(r)}</li>")
        L.append("</ul>")
    L.append("<h2>Every ticket (minutes per step)</h2><ul>")
    for tid, t in tickets.items():
        row = [f"{s.split(' · ')[1]} {mn(per[s][tid])}" for s in STEPS[1:] if tid in per.get(s, {})]
        if wait.get(tid):
            row.append(f"waiting {mn(wait[tid])}")
        L.append(f"<li>{e(t['title'][:70])} → {e(final[tid])}" + (f": {e(', '.join(row))}" if row else "") + f"<br>{link(t['link'])}</li>")
    L.append("</ul>")
    return "".join(L)


# ---------------- commands ----------------
def start():
    p, b = current()
    if b:
        age_h = (now() - parse(b["started"])).total_seconds() / 3600
        if age_h < STALE_HOURS:
            print(f"batch already open: {b['title']}"); return
        finish()  # left open by a run that died; close it before starting a new one
    day = now().strftime("%Y-%m-%d")
    n = 1 + len(list(BATCHES.glob(f"{day}-*.json")))
    b = {"title": f"Batch-{n} · {day}", "started": iso(), "finished": None, "events": [], "note_id": None}
    p = BATCHES / f"{day}-{n}.json"
    b["note_id"] = write_note(None, batch_body(b))
    save(p, b); save(CURRENT, {"file": p.name})
    print(f"batch started: {b['title']}" + ("" if b["note_id"] else " (Notes not reachable; run `ledger.py batch sync` on the Mac later)"))


def finish():
    p, b = current()
    if not b:
        print("no open batch"); return
    b["finished"] = iso()
    b["analytics_id"] = write_note(b.get("analytics_id"), analytics_body(b, p.name))
    b["note_id"] = write_note(b.get("note_id"), batch_body(b))
    # analytics are in the note now; drop raw step notes so no ticket history piles up here (timings + needs stay)
    for ev in b["events"]:
        ev.pop("note", None)
    save(p, b)
    CURRENT.unlink(missing_ok=True)
    print(f"batch finished: {b['title']} (notes: batch + analytics)")


def sync():
    files = sorted(BATCHES.glob("*-*.json"), key=lambda f: f.stat().st_mtime)
    if not files:
        print("no batches"); return
    p = files[-1]; b = load(p)
    b["note_id"] = write_note(b.get("note_id"), batch_body(b))
    if b.get("finished"):
        b["analytics_id"] = write_note(b.get("analytics_id"), analytics_body(b, p.name))
    save(p, b); print(f"synced {b['title']}")


def status():
    p, b = current()
    if not b:
        print("no open batch"); return
    need = len({ev["ticket"] for ev in b["events"] if "needed" in ev})
    print(f"open: {b['title']} since {b['started'][11:16]} · {len(b['events'])} stage changes · {need} tickets need you")


def main(argv):
    {"start": start, "finish": finish, "sync": sync, "status": status}[argv[0] if argv else "status"]()


if __name__ == "__main__":
    main(sys.argv[1:])
