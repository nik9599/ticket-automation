#!/usr/bin/env python3
"""Staleness check for the generated project files: projects/<repo>/*.md and profile.json.
Every `backticked` name in the maps that looks like a file or folder (has a / or a file extension), and every path in profile.json
(surfaces.*.code, context_docs, backend_paths, never_change), must still exist in the repo's origin/<base> tree (matched as a path suffix).
Commands, routes, packages and code symbols are ignored.
  python3 tools/check_project.py [repo ...]        (default: every enabled repo that has a profile)
Exit 0 = all found, 1 = missing names listed (fix the file or re-run `python3 run.py --map <repo>`)."""
import json, re, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import config
EXT = re.compile(r"\.[a-z0-9]{1,6}$", re.I)
SKIP = re.compile(r"^(npm|npx|yarn|pnpm|git|python3?|pip|make|bash|sh|\$|/|https?:|@|<)|[ {}()=<>*|]|\.\.\.|^\.\.|:\d|^[a-z-]+/:")


def names(text):
    for raw in re.findall(r"`([^`\n]+)`", text):
        n = raw.strip()
        if not SKIP.search(n) and ("/" in n or EXT.search(n)):
            yield n


def check_repo(name, rc):
    prof = rc.get("profile") or {}
    pdir = Path(rc["project_dir"])
    if not prof:
        print(f"{name}: no profile yet (run.py --map {name})"); return 0
    base = rc.get("base_branch", "main")
    tree = subprocess.run(["git", "ls-tree", "-r", "--name-only", f"origin/{base}"], cwd=rc["path"], capture_output=True, text=True).stdout.splitlines()
    if not tree:
        print(f"{name}: origin/{base} not found locally, skipped"); return 0
    dirs = {"/".join(p.split("/")[:i]) for p in tree for i in range(1, p.count("/") + 1)}
    pool = set(tree) | dirs
    found = lambda n: any(p == n.strip("/") or p.endswith("/" + n.strip("/")) for p in pool)
    bad = 0
    want = {"profile.json": config.profile_paths(prof) + list(prof.get("backend_paths") or []) + list(prof.get("never_change") or [])}
    for f in sorted(pdir.glob("*.md")):
        want[f.name] = list(names(f.read_text()))
    for fname, items in want.items():
        missing = [n for n in dict.fromkeys(items) if n and not found(n)]
        if missing:
            bad = 1; print(f"{name}/{fname}: MISSING on origin/{base}: " + ", ".join(missing))
        else:
            print(f"{name}/{fname}: OK")
    return bad


repos = config.load_repos()["repos"]
wanted = sys.argv[1:] or [n for n, rc in repos.items() if rc.get("enabled")]
bad = 0
for n in wanted:
    if n not in repos or not Path(repos[n].get("path", "")).is_dir():
        print(f"{n}: not in settings.json repos or path missing, skipped"); continue
    bad |= check_repo(n, repos[n])
sys.exit(bad)
