# archive-v1 — SUPERSEDED

**These files are not the paper. Do not edit them to change the submission.**

The live paper is `../rewrite/`. See `../README.md`.

This is the pre-rewrite (v1) section set, moved here from the paper root on 2026-07-24. It is kept because:

- `build/build.py` (no flag) still builds it via `SECTION_ORDER` → `build/paper.pdf`;
- the `--aft` build overrides a subset of these files with `../aft/` and falls back here for the rest;
- several sections carry historical detail the v2 rewrite condensed, which is occasionally worth consulting when chasing why a claim is phrased a particular way.

**Why it was moved.** These filenames collide with the v2 section names — both trees contain `02_related_work.md`, `07_*.md`, and others. On 2026-07-24 a set of §2 related-work additions was written here instead of into `../rewrite/`, and shipped nothing. Editing the paper root was the natural-looking move and there was no signpost saying otherwise. Moving the v1 tree down a level removes the ambiguity rather than relying on anyone reading a warning.

Anything cited or claimed from these files should be verified against `../rewrite/` before it is repeated — the rewrite changed structure, section numbering, and in places the framing.
