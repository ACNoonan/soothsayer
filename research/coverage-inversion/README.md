# Paper 1 — coverage inversion

**Read this before editing anything in this directory.**

## Which tree is live

| Directory | Status | Edit it? |
|---|---|---|
| **`rewrite/`** | **LIVE — this is the arXiv submission.** The 2026-07 structural rewrite. | **Yes. All paper edits go here.** |
| `archive-v1/` | Superseded. The pre-rewrite section set. | No — historical reference only |
| `aft/` | ACM AFT variant. Overrides a subset of v1 sections; falls back to `archive-v1/` for the rest. | Only for an AFT-specific submission |
| `references.md` | **Shared by every build.** Single source of truth for the bibliography. | Yes — see below |
| `exemplars/` | Third-party PDFs, gitignored (copyright — kept locally, never redistributed) | Add PDFs, don't commit |

`rewrite/` and `archive-v1/` contain **files with identical names** — both have `02_related_work.md`, `07_*.md`, and so on. On 2026-07-24 a set of §2 edits intended for the submission was written into the v1 tree, which builds nothing that ships; the mistake surfaced only because the build reported the new citation keys as orphans. The v1 files were moved out of the paper root that day so the ambiguity is gone.

## Building

```bash
python3 build/build.py --v2 --pdf     # the live paper  -> build/paper_v2.pdf
python3 build/build.py --pdf          # superseded v1   -> build/paper.pdf
python3 build/build.py --aft --pdf    # ACM AFT variant -> build/aft_paper.pdf
```

`--v2 --pdf` also refreshes `landing/coverage-inversion.pdf`, the snapshot the public site serves. A `--v2 --pdf` run therefore changes a public-facing artefact on the next deploy.

Without `--pdf` the build stops after generating the `.tex` — useful for a fast citation-closure check, and the reason a run can look like it "succeeded" while `paper_v2.pdf` stays stale.

## Citations

`references.md` is the source of truth. **`build/references.bib` is generated from it on every build** — edit `references.md`, never the `.bib`.

Each entry needs a `### [key] Author, A., Author, B. YEAR. Title.` header plus the Venue / URL / Contribution / Why-we-cite / Bucket fields. The build then:

- parses the header into BibTeX author/year/title fields;
- brace-protects acronyms in titles (`protect_caps`) so plainnat's sentence-casing does not render `SoK of RWA` as `Sok of rwa`;
- reports **unresolved** keys (cited in prose, undefined — always fix) and **orphans** (defined, never cited — expected for entries kept on file).

Escape a literal `$` in a title as `\$`. An unescaped one opens math mode, and because the bibliography is one environment it does not fail loudly — it silently breaks `thebibliography` and every following `\bibitem` becomes a "Lonely \item". That produced 33 LaTeX errors while still emitting a plausible-looking 64-page PDF.

## Checking a build is actually clean

`pdflatex` runs under `-interaction=nonstopmode` and the build does not gate on its exit code, so **a PDF is produced whether or not LaTeX errored.** Check the log directly:

```bash
grep -ac "LaTeX Error" build/paper_v2.log     # expect 0
grep -ac "Citation.*undefined" build/paper_v2.log   # expect 0
```

Use `grep -a`. The log is classified as binary, so a plain `grep` silently prints nothing and reads as success.
