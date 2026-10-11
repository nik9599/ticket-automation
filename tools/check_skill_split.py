#!/usr/bin/env python3
"""Rule-coverage check for splitting a step prompt into a core file + playbooks.
Every line of the BASELINE file (min 20 chars after normalising) must still appear somewhere in the CURRENT core fileor skills/playbooks/*.md.
  python3 tools/check_skill_split.py [--baseline skills/_split-baseline/replicate_classify.pre-split.md] [--core skills/replicate_classify.md]
Exit 0 = nothing lost, 1 = missing lines listed."""
import argparse, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent

def norm(t):
    t = re.sub(r"^\s*([-*]|\d+\.|[a-z]\.)\s+", "", t.strip(), flags=re.I)
    return re.sub(r"\s+", " ", t).strip().lower()

ap = argparse.ArgumentParser()
ap.add_argument("--baseline", default="skills/_split-baseline/replicate_classify.pre-split.md")
ap.add_argument("--core", default="skills/replicate_classify.md")
a = ap.parse_args()
if not (HERE / a.baseline).exists():
    sys.exit(f"no baseline at {a.baseline}: nothing to compare (save the old prompt there before splitting it)")
base = (HERE / a.baseline).read_text().splitlines()
pool = [(HERE / a.core).read_text()] + [p.read_text() for d in ("skills/playbooks",) for p in sorted((HERE / d).glob("*.md"))]
hay = " ".join(norm(l) for t in pool for l in t.splitlines())
hay_compact = re.sub(r"\s+", " ", hay)
missing = [l for l in base if len(norm(l)) >= 20 and norm(l) not in hay_compact]
checked = sum(1 for l in base if len(norm(l)) >= 20)
if missing:
    print(f"MISSING {len(missing)} of {checked} baseline lines:")
    for l in missing: print("  -", l.strip()[:160])
    sys.exit(1)
print(f"OK: all {checked} baseline lines still present (core + playbooks).")
