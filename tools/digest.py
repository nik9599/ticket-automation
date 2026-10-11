#!/usr/bin/env python3
"""Run digest for the owner: what is ready to test, what needs the owner, what ended without a fix, and where the time went.
  python3 tools/digest.py [--hours 24]   -> prints it and writes state/digest-latest.md"""
import argparse, csv, json, re, sys, datetime as dt
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import config  # settings.json -> {{KEY}} values
ap = argparse.ArgumentParser(); ap.add_argument("--hours", type=float, default=24)
a = ap.parse_args()
repos = config.load_repos()["repos"]
cut = dt.datetime.now().astimezone() - dt.timedelta(hours=a.hours)

def when(t):
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try: return dt.datetime.strptime(t, fmt)
        except Exception: pass
    return None

KEY = re.compile(r"(DECISION|OPEN DECISION|NOT REPRODUCED|needs live|BE NEEDED|For BE team|BLOCKER: (?!none)|NEEDED:)", re.I)
tickets = []
for f in (HERE / "state/tickets").glob("*.json"):
    t = json.loads(f.read_text()); u = when(t.get("updated", ""))
    if u and u.astimezone() >= cut: tickets.append(t)

def last(t, n=420):
    notes = t.get("notes") or []
    return (notes[-1]["text"] if notes else "")[:n].replace("\n", " ")

def flags(t):
    out = []
    for n in t.get("notes") or []:
        for m in re.finditer(r"[^.|]*(?:%s)[^.|]*" % KEY.pattern, n["text"], re.I):
            s = m.group(0).strip()[:220]
            if s and s not in out: out.append(s)
    return out[:4]

ready = [t for t in tickets if t["stage"] in ("verified", "fixed-local", "verifying", "pr-draft")]
need = [t for t in tickets if t["stage"] in ("needs-human", "needs-info", "not-reproducible")]
nofix = [t for t in tickets if t["stage"] in ("done-config", "done-be")]
L = [f"# Ticket automation digest ({dt.datetime.now().strftime('%Y-%m-%d %H:%M')}, last {a.hours:g}h)", ""]
L.append(f"## Ready to test ({len(ready)})")
for t in sorted(ready, key=lambda x: x["repo"]):
    path = repos.get(t["repo"], {}).get("path", "<repo>")
    L += [f"- [{t['title']}]({t['link']}) - {t['repo']}, {t.get('surface') or '?'}, stage {t['stage']}"]
    if t.get("branch"): L.append(f"  - test it: `git -C {path} checkout {t['branch']}`")
    if t.get("pr_url"): L.append(f"  - PR: {t['pr_url']}")
    for fl in flags(t): L.append(f"  - check: {fl}")
L += ["", f"## Needs you ({len(need)})"]
for t in need: L += [f"- [{t['title']}]({t['link']}) - {t['repo']}, {t['stage']}: {last(t)}"]
L += ["", f"## Ended without a code fix ({len(nofix)})"]
for t in nofix: L += [f"- [{t['title']}]({t['link']}) - {t['stage']}: {last(t, 200)}"]
tm = HERE / "state/timings.csv"
if tm.exists():
    tot = {}
    for r in csv.DictReader(tm.open()):
        d = when(r["time"])
        if d and d.astimezone() >= cut:
            s = tot.setdefault(r["step"], [0, 0]); s[0] += int(r["seconds"]); s[1] += 1
    if tot:
        L += ["", "## Where the time went"]
        for k, (sec, n) in tot.items(): L.append(f"- {k}: {sec/60:.1f} min over {n} session(s), avg {sec/60/n:.1f} min")
        L.append(f"- total: {sum(v[0] for v in tot.values())/60:.1f} min")
out = "\n".join(L) + "\n"
(HERE / "state/digest-latest.md").write_text(out)
print(out)
