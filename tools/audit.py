#!/usr/bin/env python3
"""Guardrail audit, run by run.py after every fix / verify session (exit 0 = ok, 1 = violation).
Checks what a session leaves behind, independent of what the session says it did:
  1. branch diff vs origin/<base>: no local-only file, no changed/deleted/renamed EXISTING test (tools/check_staged.sh)
  2. working tree: only local-only files may be modified (untracked files are only a warning)
  3. optional: the profile's `cleanup_check` command (e.g. a local proxy/override status) must print its expected `ok` text
Usage: audit.py --repo <name> --repo-path <path> --ticket <id> --step <fix|verify>"""
import argparse, json, os, re, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import config


def run(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.environ.get("TICKET_REPO", "")); ap.add_argument("--repo-path", required=True)
ap.add_argument("--ticket", required=True); ap.add_argument("--step", default="")
a = ap.parse_args()
repo = a.repo_path
prof = config.load_profile(a.repo) if a.repo else {}
base = os.environ.get("TICKET_BASE_BRANCH") or prof.get("base_branch") or "main"
local_only = [re.compile(p, re.I) for p in (prof.get("local_only_files") or [])]
problems, warnings = [], []

if not Path(repo).is_dir():
    print(f"audit: repo path not found here ({repo}); skipped"); sys.exit(0)

branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo).stdout.strip()
if branch and branch not in (base, "master", "main", "HEAD"):
    env = dict(os.environ, TICKET_REPO=a.repo, TICKET_BASE_BRANCH=base)
    r = run(["bash", str(HERE / "check_staged.sh")], repo, env)
    if r.returncode != 0:
        problems.append("check_staged.sh failed on branch " + branch + ": " + (r.stdout + r.stderr).strip().replace("\n", " | ")[:500])
else:
    warnings.append(f"repo is on '{branch}', branch diff check skipped")

for line in run(["git", "status", "--porcelain"], repo).stdout.splitlines():
    code, path = line[:2], line[3:].strip().split(" -> ")[-1]
    if code == "??":
        warnings.append("untracked file left in repo: " + path)
    elif not any(p.search(path) for p in local_only):
        problems.append(f"uncommitted change outside the local-only files: {code.strip()} {path}")

chk = prof.get("cleanup_check") or {}
if chk.get("command"):
    r = subprocess.run(chk["command"], shell=True, cwd=repo, capture_output=True, text=True)
    if chk.get("ok", "") not in (r.stdout + r.stderr):
        problems.append(f"cleanup check failed ({chk['command']}): " + (r.stdout + r.stderr).strip()[:200])

for w in warnings: print("audit warning:", w)
if problems:
    print(f"AUDIT FAILED for ticket {a.ticket} after step {a.step}:")
    for p in problems: print("  -", p)
    sys.exit(1)
print(f"audit ok ({a.ticket}, {a.step})")
