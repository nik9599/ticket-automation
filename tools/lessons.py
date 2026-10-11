#!/usr/bin/env python3
"""The automation's notebook: short, curated lessons that make the next ticket easier.
Per repo (project-specific, generated, git-ignored): projects/<repo>/lessons.md. Cross-project lessons (--repo general): memory/lessons.md.
  lessons.py show [--repo <name>] [--surface <key>]
  lessons.py add  [--repo <name>] --surface <key|general> --ticket <id> --text "<one plain-English lesson>"
--repo defaults to $TICKET_REPO. Surface keys are the profile's surface keys (step 0) plus `general`.
Rules: one line per lesson, dated, deduplicated, short (max 40 lines per surface; oldest dropped first). Never secrets, tokens or customer data."""
import argparse, datetime, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
AUTO = os.environ.get("TICKET_AUTOMATION_DIR", os.path.dirname(HERE))
MAX = 40
SECRET = re.compile(r"(token=|jwt|password|secret|api[_-]?key|sk-[a-z0-9]|eyJ[a-zA-Z0-9_-]{10,})", re.I)
KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,30}$")


def path_for(repo):
    if not repo or repo == "general":
        return os.path.join(AUTO, "memory", "lessons.md")
    return os.path.join(AUTO, "projects", repo, "lessons.md")


def load(path):
    data, cur = {}, None
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.rstrip("\n")
            m = re.match(r"^## ([\w-]+)", line)
            if m: cur = m.group(1); data.setdefault(cur, []); continue
            if cur and line.startswith("- "): data[cur].append(line)
    return data


def save(path, data, repo):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    title = f"# Lessons: {repo}" if repo and repo != "general" else "# Lessons (cross-project)"
    out = [title, "Short, plain-English notes. Read the matching surface before a fix; add one line after each ticket.", ""]
    for s in sorted(data, key=lambda k: (k != "general", k)):
        out += [f"## {s}"] + data[s] + [""]
    open(path, "w", encoding="utf-8").write("\n".join(out))


def norm(t): return re.sub(r"\W+", " ", t.lower()).strip()


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="c", required=True)
    p = sp.add_parser("show"); p.add_argument("--repo", default=os.environ.get("TICKET_REPO")); p.add_argument("--surface")
    p = sp.add_parser("add"); p.add_argument("--repo", default=os.environ.get("TICKET_REPO")); p.add_argument("--surface", required=True)
    p.add_argument("--ticket", required=True); p.add_argument("--text", required=True)
    a = ap.parse_args()
    if a.c == "show":
        for repo in dict.fromkeys([a.repo or "general", "general"]):
            d = load(path_for(repo))
            for s in ([a.surface, "general"] if a.surface else list(d)):
                if d.get(s): print(f"## {repo} / {s}"); print("\n".join(d[s]))
        return
    surface = a.surface.lower()
    if not KEY.match(surface): sys.exit("refused: surface must be a short key like the profile's surface keys, or general")
    text = " ".join(a.text.split())
    if SECRET.search(text): sys.exit("refused: looks like it contains a secret/token; rewrite without it")
    if len(text) > 300: sys.exit("refused: too long, keep one lesson under 300 characters")
    path = path_for(a.repo); d = load(path); d.setdefault(surface, [])
    if any(norm(text) in norm(l) for l in d[surface]): print("already known"); return
    d[surface].append(f"- {datetime.date.today()} [{a.ticket}] {text}")
    d[surface] = d[surface][-MAX:]
    save(path, d, a.repo); print(f"saved to {path}")


main()
