#!/usr/bin/env python3
"""Writes dashboard/data.js for the static pipeline view (index.html). No server; stdlib only.

  python3 dashboard/build.py           # write data.js once
  python3 dashboard/build.py --watch   # rewrite only when ticket files change (checks every 5s)

Then open dashboard/index.html in a browser; it reloads data.js every 5s.
"""
import json, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUTO = HERE.parent
STATE = AUTO / "state"
PROJECTS = Path.home() / ".claude" / "projects"
STEP_RE = re.compile(r"Run the (\w+) step for ClickUp ticket (\w+)")


def ps():
    out = subprocess.run(["ps", "-ax", "-o", "pid=,etime=,command="], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3:
            rows.append({"pid": int(parts[0]), "etime": parts[1], "cmd": parts[2]})
    return rows


def running_steps(rows):
    """ticket id -> {pid, step, etime} for every `claude -p` step that run.py started."""
    found = {}
    for r in rows:
        if "claude -p" in r["cmd"]:
            m = STEP_RE.search(r["cmd"].replace("\\012", " "))
            if m:
                found[m.group(2)] = {"pid": r["pid"], "step": m.group(1), "etime": r["etime"]}
    return found


def run_lock(rows):
    try:
        lock = json.loads((STATE / ".lock").read_text())
    except Exception:
        return None
    return {"pid": lock.get("pid"), "alive": any(r["pid"] == lock.get("pid") for r in rows)}


def last_activity(ticket):
    """Newest tool call or text in the running step's transcript."""
    sessions = ticket.get("sessions") or []
    if not sessions:
        return None
    s = sessions[-1]
    path = PROJECTS / re.sub(r"[^A-Za-z0-9]", "-", s.get("cwd", "")) / f"{s.get('id')}.jsonl"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        f.seek(0, 2); f.seek(max(0, f.tell() - 200_000))
        lines = f.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get("type") != "assistant":
            continue
        for block in reversed(ev.get("message", {}).get("content", []) or []):
            if block.get("type") == "tool_use":
                inp = block.get("input", {})
                detail = inp.get("description") or inp.get("command") or inp.get("file_path") or inp.get("pattern") or inp.get("url") or ""
                return {"ts": ev.get("timestamp"), "what": f"{block.get('name')}: {str(detail)[:160]}"}
            if block.get("type") == "text" and block.get("text", "").strip():
                return {"ts": ev.get("timestamp"), "what": block["text"].strip()[:200]}
    return None


def build():
    rows = ps()
    live = running_steps(rows)
    tickets = []
    for p in STATE.glob("tickets/*.json"):
        try:
            t = json.loads(p.read_text())
        except Exception:
            continue
        item = {k: t.get(k) for k in ("id", "repo", "title", "link", "stage", "branch", "pr_url", "updated")}
        item["history"] = [{"ts": h.get("ts"), "from": h.get("from"), "to": h.get("to"), "note": (h.get("note") or "")[:4000]}
                           for h in (t.get("history") or [])[-12:]]
        item["running"] = live.get(t["id"])
        if item["running"]:
            item["activity"] = last_activity(t)
        tickets.append(item)
    tickets.sort(key=lambda t: t.get("updated") or "", reverse=True)
    tickets.sort(key=lambda t: not t["running"])
    try:
        events = (STATE / "events.log").read_text().splitlines()[-25:]
    except Exception:
        events = []
    data = {"built": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "auto_dir": str(AUTO), "run": run_lock(rows),
            "tickets": tickets, "events": [e[:400] for e in events]}
    tmp = HERE / "data.js.tmp"
    tmp.write_text("window.PIPELINE_DATA = " + json.dumps(data) + ";\n")
    tmp.replace(HERE / "data.js")


def stamp():
    files = list(STATE.glob("tickets/*.json")) + [STATE / ".lock"]
    return max((f.stat().st_mtime for f in files if f.exists()), default=0)


if __name__ == "__main__":
    build()
    if "--watch" in sys.argv:
        last = stamp()
        while True:
            time.sleep(5)
            cur = stamp()
            # rebuild on ledger change, and every 30s while a step runs (elapsed time / last action)
            if cur != last or (int(time.time()) % 30 < 5 and '"running": {' in (HERE / "data.js").read_text()):
                build(); last = cur
