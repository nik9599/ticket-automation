#!/usr/bin/env python3
"""Ticket ledger: the single source of truth for 'which ticket is at which stage'.

One JSON file per ticket in state/tickets/<id>.json (atomic writes, easy to inspect/edit).
Stdlib only. Run `python3 ledger.py --help`.
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config  # settings.json -> {{KEY}} values
STATE = Path(os.environ.get("TICKET_STATE_DIR", HERE / "state"))
TICKETS = STATE / "tickets"
EVENTS = STATE / "events.log"
STAGE_TIMINGS = STATE / "stage-timings.csv"
EVID = Path(os.environ.get("TICKET_EVIDENCE_DIR", HERE / "evidence"))
LOGS = STATE / "logs"
LIVE_LOGS = STATE / "live-logs"   # live-environment view logs of finished tickets, kept a few days

# stage -> allowed next stages
TRANSITIONS = {
    "queued":           ["replicating", "skipped", "needs-info"],
    "replicating":      ["replicated", "not-reproducible", "needs-info", "failed", "needs-human"],
    "replicated":       ["classified", "needs-info", "needs-human", "failed"],
    "not-reproducible": ["replicating", "needs-info", "needs-human"],
    "classified":       ["fixing", "done-config", "done-be", "needs-human"],
    "fixing":           ["fixed-local", "failed", "needs-human"],
    "fixed-local":      ["verifying", "fixing", "needs-human"],
    "verifying":        ["verified", "fixing", "failed", "needs-human"],
    "verified":         ["pr-draft", "needs-human"],
    "pr-draft":         ["preprod-wait", "done", "needs-human"],
    "preprod-wait":     ["preprod-verified", "failed", "needs-human"],
    "preprod-verified": ["done", "needs-human"],
    "failed":           ["queued", "needs-human"],
    "needs-human":      [],
    "needs-info":       ["queued"],
    "done-config":      [],
    "done-be":          [],
    "skipped":          ["queued"],
    "done":             [],
    "moved-out":        [],   # ticket status was changed in ClickUp (moved to another status by a person)
}
for _k, _v in TRANSITIONS.items():
    if _k != "moved-out" and "moved-out" not in _v and _k not in ("needs-human", "done", "done-config", "done-be"):
        _v.append("moved-out")

# in-progress stage -> stage to fall back to if a run died mid-way (see `recover`)
IN_PROGRESS = {"replicating": "queued", "fixing": "classified", "verifying": "fixed-local"}
TERMINAL = {"done", "done-config", "done-be", "skipped", "needs-human", "needs-info", "failed", "moved-out"}
# stages whose heavy artifacts (logs, evidence, worktree) can be deleted
# stages where the automation is finished and the ticket only waits on the owner; they do NOT use up fetch room,
# so every run gets fresh tickets (owner rule, 2026-10-10)
WAITING_ON_HUMAN = {"pr-draft", "preprod-wait", "preprod-verified"}
CLEAN_NEEDS_PR = {"pr-draft", "preprod-wait", "preprod-verified", "done"}
CLEAN_ANY = {"done-config", "done-be", "moved-out"}
ORDER = list(TRANSITIONS.keys())


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def path_for(tid):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", tid):
        sys.exit(f"bad ticket id: {tid!r}")
    return TICKETS / f"{tid}.json"


def load(tid):
    p = path_for(tid)
    if not p.exists():
        sys.exit(f"unknown ticket {tid} (use `add` first)")
    return json.loads(p.read_text())


def save(t):
    TICKETS.mkdir(parents=True, exist_ok=True)
    p = path_for(t["id"])
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(t, indent=2, sort_keys=False))
    os.replace(tmp, p)


def log(msg):
    STATE.mkdir(parents=True, exist_ok=True)
    with open(EVENTS, "a") as f:
        f.write(f"{now()} {msg}\n")


def _ts(s):
    return time.mktime(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))


def entered_at(t):
    """When the ticket entered its current stage (last real transition into it)."""
    for h in reversed(t["history"]):
        if h["to"] == t["stage"] and h["from"] != h["to"]:
            return h["ts"]
    return t["history"][0]["ts"] if t["history"] else None


def log_stage_timing(t, frm, to):
    """One line per stage change in state/stage-timings.csv: minutes spent in `frm` and since the ticket was added."""
    try:
        start = entered_at(t)
        first = t["history"][0]["ts"] if t["history"] else start
        mins = (time.time() - _ts(start)) / 60 if start else 0
        total = (time.time() - _ts(first)) / 60 if first else 0
        new = not STAGE_TIMINGS.exists()
        with open(STAGE_TIMINGS, "a") as fh:
            if new:
                fh.write("time,ticket,repo,from,to,minutes_in_from,minutes_since_added\n")
            fh.write(f"{now()},{t['id']},{t.get('repo')},{frm},{to},{mins:.1f},{total:.1f}\n")
    except (OSError, ValueError, KeyError):
        pass


def _batch(t, frm, to, note):
    """Record a stage change in the open batch (tools/batch.py -> Apple Notes). Never breaks the ledger."""
    try:
        sys.path.insert(0, str(HERE / "tools"))
        import batch
        start = entered_at(t) if frm else None
        mins = (time.time() - _ts(start)) / 60 if start else 0
        batch.record(t, frm, to, mins, note)
    except Exception:
        pass


def all_tickets():
    if not TICKETS.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(TICKETS.glob("*.json"))]


def max_attempts():
    try:
        cfg = config.load_repos()
        return int(cfg.get("defaults", {}).get("max_attempts", 2))
    except Exception:
        return 2


def branch_rules():
    try:
        d = config.load_repos().get("defaults", {})
    except Exception:
        d = {}
    return int(d.get("branch_max_len", 20)), bool(d.get("branch_lowercase", True))


# ---------------- commands ----------------
def cmd_add(a):
    p = path_for(a.id)
    if p.exists():
        print(f"exists {a.id} stage={json.loads(p.read_text())['stage']}")
        return
    t = {
        "id": a.id, "repo": a.repo, "title": a.title, "link": a.link or f"https://app.clickup.com/t/{config.settings()['CLICKUP_TEAM_ID']}/{a.id}",
        "tags": [x for x in (a.tags or "").split(",") if x], "priority": a.priority, "created": a.created,
        "stage": "queued", "verdict": None, "surface": None, "root_cause": None, "files": [],
        "branch": None, "worktree": None, "pr_url": None, "evidence": [], "attempts": {},
        "preprod_check_after": None, "evidence_uploaded": False, "cleaned": None, "notes": [], "history": [{"ts": now(), "from": None, "to": "queued", "note": "added"}],
        "updated": now(),
    }
    save(t)
    _batch(t, None, "queued", "added")
    log(f"add {a.id} repo={a.repo}")
    print(f"added {a.id} -> {a.repo}")


def cmd_set(a):
    t = load(a.id)
    cur = t["stage"]
    batch_ev = None
    if a.stage and a.stage != cur:
        if not a.force and a.stage not in TRANSITIONS.get(cur, []):
            sys.exit(f"illegal transition {cur} -> {a.stage} (allowed: {TRANSITIONS.get(cur)}); --force to override")
        if a.stage in IN_PROGRESS:
            n = t["attempts"].get(a.stage, 0) + 1
            if n > max_attempts() and not a.force:
                log_stage_timing(t, cur, "needs-human"); _batch(t, cur, "needs-human", f"max attempts on {a.stage}")
                t["history"].append({"ts": now(), "from": cur, "to": "needs-human", "note": f"max attempts on {a.stage}"})
                t["stage"] = "needs-human"; t["updated"] = now(); save(t)
                log(f"{a.id} {cur}->needs-human (max attempts {a.stage})")
                sys.exit(f"max attempts reached for {a.stage}; ticket moved to needs-human")
            t["attempts"][a.stage] = n
        log_stage_timing(t, cur, a.stage)
        batch_ev = (list(t["history"]), cur, a.stage)  # minutes in `cur` are measured before the history changes
        t["history"].append({"ts": now(), "from": cur, "to": a.stage, "note": a.note or ""})
        t["stage"] = a.stage
        log(f"{a.id} {cur}->{a.stage} {a.note or ''}".strip())
    elif a.note:
        t["history"].append({"ts": now(), "from": cur, "to": cur, "note": a.note})
    for k in ("verdict", "surface", "root_cause", "branch", "worktree", "pr_url", "preprod_check_after"):
        v = getattr(a, k)
        if v is not None:
            t[k] = v
    if a.evidence_uploaded:
        t["evidence_uploaded"] = True
    if a.file:
        t["files"] = sorted(set(t["files"]) | set(a.file))
    if a.evidence:
        t["evidence"] = t["evidence"] + [e for e in a.evidence if e not in t["evidence"]]
    if a.session:
        sid, _, cwd = a.session.partition("|")
        t.setdefault("sessions", []).append({"id": sid, "cwd": cwd})
    if a.note:
        t["notes"].append({"ts": now(), "text": a.note})
    t["updated"] = now()
    save(t)
    if batch_ev:
        # history snapshot for the minutes, current fields (pr_url, notes) for the "what I need" text
        snap = dict(t, history=batch_ev[0], stage=batch_ev[1])  # entered_at() needs the old stage + history
        _batch(snap, batch_ev[1], batch_ev[2], a.note)
    print(f"{a.id}: {t['stage']}")


def cmd_show(a):
    print(json.dumps(load(a.id), indent=2))


def cmd_next(a):
    stages = set(a.stages.split(","))
    out = [t for t in all_tickets() if t["repo"] == a.repo and t["stage"] in stages]
    out.sort(key=lambda t: t["updated"])
    for t in out[: a.limit or None]:
        print(t["id"])


def cmd_board(a):
    ts = [t for t in all_tickets() if not a.repo or t["repo"] == a.repo]
    repos = sorted({t["repo"] for t in ts})
    if not ts:
        print("(no tickets)"); return
    for r in repos:
        rt = [t for t in ts if t["repo"] == r]
        counts = {}
        for t in rt:
            counts[t["stage"]] = counts.get(t["stage"], 0) + 1
        print(f"\n== {r}: {len(rt)} tickets  " + "  ".join(f"{s}={counts[s]}" for s in ORDER if s in counts))
        for t in sorted(rt, key=lambda t: (ORDER.index(t["stage"]), t["id"])):
            extra = " ".join(x for x in [t.get("verdict") or "", t.get("surface") or "", t.get("pr_url") or ""] if x)
            print(f"  {t['id']:<12} {t['stage']:<17} {extra:<28} {t['title'][:60]}")


def cmd_open_count(a):
    print(sum(1 for t in all_tickets() if t["repo"] == a.repo and t["stage"] not in TERMINAL and t["stage"] not in WAITING_ON_HUMAN))


def cmd_known(a):
    print("yes" if path_for(a.id).exists() else "no")


def cmd_due(a):
    for t in all_tickets():
        if t["stage"] == "preprod-wait" and t.get("preprod_check_after") and t["preprod_check_after"] <= now():
            print(t["id"])


def cmd_recover(a):
    cutoff = time.time() - a.minutes * 60
    for t in all_tickets():
        if t["stage"] in IN_PROGRESS:
            ts = time.mktime(time.strptime(t["updated"][:19], "%Y-%m-%dT%H:%M:%S"))
            if ts < cutoff:
                back = IN_PROGRESS[t["stage"]]
                log_stage_timing(t, t["stage"], back)
                t["history"].append({"ts": now(), "from": t["stage"], "to": back, "note": "recovered after stall"})
                log(f"{t['id']} recover {t['stage']}->{back}")
                t["stage"] = back; t["updated"] = now(); save(t)
                print(f"recovered {t['id']} -> {back}")


def _size(p):
    p = Path(p)
    if not p.exists():
        return 0
    if p.is_file():
        return p.stat().st_size
    total = 0
    for root, _, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _mb(n):
    return f"{n / 1048576:.1f} MB"


def _repo_path(repo):
    try:
        return config.load_repos()["repos"][repo]["path"]
    except Exception:
        return None


def live_days():
    try:
        return int(config.load_repos().get("defaults", {}).get("live_log_retention_days", 2))
    except Exception:
        return 2


def cmd_cleanup(a):
    """Delete heavy per-ticket artifacts (logs, evidence, worktree) once a ticket is finished.
    Triggers: draft PR created (stage pr-draft or later, with a PR link), config-only fix, or the ticket was moved
    out of To Assign in ClickUp (stage moved-out). The tiny ticket record stays in the ledger as history."""
    freed = 0
    if not a.id and not a.dry_run:
        try:
            sys.path.insert(0, str(HERE / "tools")); import batch
            if batch.current()[1]:
                batch.finish()   # end of a run: analytics note before findings are compacted
        except Exception as e:
            print(f"  (batch finish failed: {e})")
    for t in all_tickets():
        if a.id and t["id"] != a.id:
            continue
        eligible = t["stage"] in CLEAN_ANY or (t["stage"] in CLEAN_NEEDS_PR and t.get("pr_url"))
        if not eligible or (t.get("compacted") and not a.id):
            continue
        tid = t["id"]
        items = []  # (label, path, kind)
        if LOGS.exists():
            for lf in LOGS.glob(f"*-{tid}.log"):
                items.append(("log", lf, "file"))
        ev = EVID / tid
        keep_evidence = t["stage"] not in CLEAN_ANY and not t.get("evidence_uploaded")
        if ev.exists():
            if keep_evidence:
                print(f"  {tid}: keeping evidence (not marked as uploaded to the PR yet)")
            else:
                for ml in ev.rglob("live-log*.md"):
                    items.append(("live-environment log (kept a few days in state/live-logs)", ml, "keep"))
                items.append(("evidence", ev, "dir"))
        if t.get("worktree") and Path(t["worktree"]).exists():
            items.append(("worktree", Path(t["worktree"]), "worktree"))
        if not keep_evidence:
            # Claude session history of this ticket's steps (run.py records it with --session)
            for ss in t.get("sessions") or []:
                proj = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", ss.get("cwd") or "")
                for f, kind in ((proj / f"{ss['id']}.jsonl", "file"), (proj / ss["id"], "dir")):
                    if ss.get("id") and f.exists():
                        items.append(("claude session history", f, kind))
        if not keep_evidence:
            # Patch and PR body are only needed until the PR has its screenshots; the PR branch keeps the code.
            pend = Path(os.environ.get("TICKET_PENDING_DIR", HERE / "pending-prs"))
            for f in [pend / f"{tid}.patch"] + ([pend / f"{t['branch']}.md", pend / f"{t['branch']}.patch", pend / f"grp-{t['branch']}.patch"] if t.get("branch") else []):
                if f.exists():
                    items.append(("pending-pr file", f, "file"))
        if not items:
            continue
        for label, p, kind in items:
            sz = _size(p)
            if a.dry_run:
                print(f"  [dry-run] {tid}: would delete {label} {p} ({_mb(sz)})")
                continue
            try:
                if kind == "keep":
                    dest = LIVE_LOGS / tid / p.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), str(dest)); os.utime(dest)   # 2-day clock starts now
                    print(f"  {tid}: moved {p.name} -> state/live-logs/{tid}/ (deleted after {live_days()} days)")
                    continue
                if kind == "file":
                    p.unlink()
                elif kind == "dir":
                    shutil.rmtree(p)
                else:
                    repo = _repo_path(t["repo"])
                    r0 = subprocess.run(["git", "-C", str(p), "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True, text=True)
                    if r0.returncode == 0 and r0.stdout.strip():
                        repo = str(Path(r0.stdout.strip()).parent)   # main repo this worktree belongs to
                    ok = False
                    if repo and Path(repo).is_dir():
                        r = subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", str(p)], capture_output=True, text=True)
                        ok = r.returncode == 0
                    if not ok and p.exists():
                        shutil.rmtree(p)
                        if repo and Path(repo).is_dir():
                            subprocess.run(["git", "-C", repo, "worktree", "prune"], capture_output=True)
                freed += sz
                print(f"  {tid}: deleted {label} ({_mb(sz)})")
            except (PermissionError, OSError) as e:
                print(f"  {tid}: could not delete {label} {p}: {e} (deleting may need approval)")
        if not a.dry_run:
            if not keep_evidence:
                t["evidence"] = []
            t["worktree"] = None if not (t.get("worktree") and Path(t["worktree"]).exists()) else t["worktree"]
            t["cleaned"] = now()
            if not keep_evidence:
                t["sessions"] = []
            if not keep_evidence and not t.get("compacted"):
                # Findings live in the PR / ClickUp now; keep only what fetch needs to never pick the ticket again.
                t["notes"] = [{"ts": now(), "text": f"Findings removed after finish (stage {t['stage']}, PR {t.get('pr_url') or '-'})."}]
                t["root_cause"] = None
                t["files"] = []
                t["compacted"] = now()
            t["history"].append({"ts": now(), "from": t["stage"], "to": t["stage"], "note": "cleaned logs/evidence/worktree"})
            t["updated"] = now(); save(t)
            log(f"{tid} cleaned")
    # prune old logs of any ticket
    days = 14
    try:
        days = int(config.load_repos().get("defaults", {}).get("log_retention_days", 14))
    except Exception:
        pass
    if not a.id and LOGS.exists():
        cutoff = time.time() - days * 86400
        for lf in LOGS.glob("*.log"):
            if lf.stat().st_mtime < cutoff:
                sz = lf.stat().st_size
                if a.dry_run:
                    print(f"  [dry-run] would delete old log {lf.name}")
                else:
                    try:
                        lf.unlink(); freed += sz
                    except OSError as e:
                        print(f"  could not delete {lf.name}: {e}")
    # live-environment logs: the only per-ticket history kept after finish, only for a few days (owner rule, 2026-10-11)
    if not a.id and LIVE_LOGS.exists():
        cutoff = time.time() - live_days() * 86400
        for d in LIVE_LOGS.iterdir():
            if d.is_dir() and max((f.stat().st_mtime for f in d.rglob("*")), default=0) < cutoff:
                if a.dry_run:
                    print(f"  [dry-run] would delete live-environment log {d.name} (older than {live_days()} days)")
                else:
                    freed += _size(d); shutil.rmtree(d, ignore_errors=True); print(f"  {d.name}: deleted live-environment log (older than {live_days()} days)")
    print(f"cleanup {'(dry-run) ' if a.dry_run else ''}done, freed {_mb(freed)}")


def cmd_batch(a):
    sys.path.insert(0, str(HERE / "tools"))
    import batch
    batch.main([a.action])


def cmd_disk(a):
    print(f"logs: {_mb(_size(LOGS))}   evidence: {_mb(_size(EVID))}   ledger: {_mb(_size(TICKETS))}")
    for t in all_tickets():
        e = _size(EVID / t["id"]); w = _size(t["worktree"]) if t.get("worktree") else 0
        if e or w:
            print(f"  {t['id']:<12} {t['stage']:<17} evidence {_mb(e)}  worktree {_mb(w)}")


def cmd_branchname(a):
    maxlen, lower = branch_rules()
    slug = re.sub(r"[^a-z0-9]+", "-", a.title.lower()).strip("-")
    suffix = a.id.lower() if lower else a.id
    room = maxlen - len(suffix) - 1
    slug = slug[: max(room, 0)].strip("-")
    name = f"{slug}-{suffix}" if slug else suffix
    print(name[:maxlen] if lower else name)


# stage -> report column (work = a step session running, wait = queued for the next step)
TIMING_COLS = [("replicating", "s2 replicate"), ("classified", "wait"), ("fixing", "s3 fix"), ("fixed-local", "wait"),
               ("verifying", "s4 verify"), ("verified", "wait"), ("pr-draft", None)]


def cmd_timings(a):
    """Per-ticket minutes per stage, from ticket history (covers tickets from before the csv existed)."""
    rows = []
    for t in all_tickets():
        h = [x for x in t["history"] if x["from"] != x["to"]]
        if a.id and t["id"] != a.id:
            continue
        if not any(x["to"] == "replicating" for x in h):
            continue
        spent, start, s4 = {}, None, None
        for i, x in enumerate(h):
            if x["to"] == "replicating" and start is None:
                start = x["ts"]
            if x["to"] == "verifying" and s4 is None:
                s4 = x["ts"]
            if i + 1 < len(h) and x["to"] in dict(TIMING_COLS):
                spent[x["to"]] = spent.get(x["to"], 0) + (_ts(h[i + 1]["ts"]) - _ts(x["ts"])) / 60
        if a.since and start[:10] < a.since:
            continue
        to4 = (_ts(s4) - _ts(start)) / 60 if s4 else None
        rows.append((start, t["id"], t["repo"], spent, to4, t["stage"]))
    rows.sort()
    cols = [c for c in TIMING_COLS if c[1]]
    print("start            | ticket       | repo         | " + " | ".join(f"{n:>12}" for _, n in cols) + " | to step 4 | now")
    f = lambda v: f"{v:12.1f}" if v is not None else f"{'-':>12}"
    for start, tid, repo, spent, to4, stage in rows:
        print(f"{start[:16]} | {tid:12} | {str(repo):12} | " + " | ".join(f(spent.get(st)) for st, _ in cols)
              + f" | {to4:9.1f} | {stage}" if to4 is not None else f"{start[:16]} | {tid:12} | {str(repo):12} | "
              + " | ".join(f(spent.get(st)) for st, _ in cols) + f" | {'-':>9} | {stage}")
    got = [r[4] for r in rows if r[4] is not None]
    if got:
        got.sort()
        print(f"\nreached step 4: {len(got)} | avg {sum(got)/len(got):.1f} min | median {got[len(got)//2]:.1f} | min {got[0]:.1f} | max {got[-1]:.1f}")
        for st, n in cols:
            v = [r[3][st] for r in rows if st in r[3]]
            if v:
                print(f"  {st:12} ({n}): avg {sum(v)/len(v):.1f} min over {len(v)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("add"); p.add_argument("--id", required=True); p.add_argument("--repo", required=True)
    p.add_argument("--title", required=True); p.add_argument("--link"); p.add_argument("--tags"); p.add_argument("--priority"); p.add_argument("--created"); p.set_defaults(f=cmd_add)
    p = sp.add_parser("set"); p.add_argument("id"); p.add_argument("--stage"); p.add_argument("--note")
    p.add_argument("--verdict", choices=["config", "code", "needs-info"]); p.add_argument("--surface", help="a surface key from the repo profile, backend or other")
    p.add_argument("--root-cause", dest="root_cause"); p.add_argument("--branch"); p.add_argument("--worktree"); p.add_argument("--pr", dest="pr_url")
    p.add_argument("--preprod-check-after", dest="preprod_check_after"); p.add_argument("--file", action="append"); p.add_argument("--evidence", action="append")
    p.add_argument("--evidence-uploaded", dest="evidence_uploaded", action="store_true", help="screenshots are embedded in the PR; local copies may be deleted")
    p.add_argument("--session", help="<claude session id>|<cwd>: transcript deleted by cleanup once the ticket is finished")
    p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_set)
    p = sp.add_parser("show"); p.add_argument("id"); p.set_defaults(f=cmd_show)
    p = sp.add_parser("next"); p.add_argument("--repo", required=True); p.add_argument("--stages", required=True); p.add_argument("--limit", type=int); p.set_defaults(f=cmd_next)
    p = sp.add_parser("board"); p.add_argument("--repo"); p.set_defaults(f=cmd_board)
    p = sp.add_parser("open-count"); p.add_argument("--repo", required=True); p.set_defaults(f=cmd_open_count)
    p = sp.add_parser("known"); p.add_argument("id"); p.set_defaults(f=cmd_known)
    p = sp.add_parser("due"); p.set_defaults(f=cmd_due)
    p = sp.add_parser("recover"); p.add_argument("--minutes", type=int, default=90); p.set_defaults(f=cmd_recover)
    p = sp.add_parser("cleanup"); p.add_argument("--id"); p.add_argument("--dry-run", action="store_true"); p.set_defaults(f=cmd_cleanup)
    p = sp.add_parser("disk"); p.set_defaults(f=cmd_disk)
    p = sp.add_parser("batch", help="Apple Notes batch: start | finish | status | sync (tools/batch.py)"); p.add_argument("action", choices=["start", "finish", "status", "sync"]); p.set_defaults(f=cmd_batch)
    p = sp.add_parser("timings", help="minutes per stage per ticket + time to reach step 4"); p.add_argument("--id"); p.add_argument("--since", help="YYYY-MM-DD"); p.set_defaults(f=cmd_timings)
    p = sp.add_parser("branchname"); p.add_argument("--id", required=True); p.add_argument("--title", required=True); p.set_defaults(f=cmd_branchname)
    a = ap.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
