# SURFACE: <repo> / <surface> (<one line: what it is>)
Read by step 3 when the handover surface is `<surface>`. Paths are from the repo root.
Base reference: `<repo doc>` -> "<section>". Last checked against origin/<base> <date>.

## What it is and where it runs
<stack, where it runs (admin / storefront / customer area / mobile / POS ...), how it boots, which store / API client it uses>

## Where things live
<entry file, router, feature folders (one line each), data layer, shared utils>

## Feature -> file -> twin on other surfaces
| Feature | File(s) here | Twin / copy elsewhere (must change together) |
|---|---|---|

## Deprecated / do not change
<folders never edited, and what to write in the note instead>

## Rules that cost time before
<one line each; promoted from `tools/lessons.py show --surface <surface>`>

## Tests
<spec location, render-test pattern, commands for this surface>
