# Paper 1 — LaTeX build

Markdown → LaTeX → PDF pipeline for arXiv submission of *Coverage-Inversion: A Calibration-Transparent Oracle Primitive for Tokenized RWAs*.

## What's in this directory

| File | Purpose |
|---|---|
| `build.py` | Driver: parses references, concatenates section markdown, runs pandoc, optionally compiles PDF |
| `pandoc-template.tex` | Pandoc LaTeX template — wraps the section body in the arxiv-style preamble + natbib bibliography |
| `arxiv.sty` | Single-column NIPS-derived preprint style (from `kourgeorge/arxiv-style`) |

Generated artifacts (gitignored):

| File | Produced by |
|---|---|
| `references.bib` | `build.py` from `../references.md` |
| `paper.md` | `build.py` (concatenated body) |
| `paper.tex` | `build.py` via `pandoc` |
| `paper.pdf`, `paper.aux`, `paper.bbl`, etc. | `build.py --pdf` via `pdflatex` + `biber` |

## Install requirements

```bash
brew install pandoc
brew install --cask basictex                    # provides pdflatex + biber
sudo tlmgr update --self
sudo tlmgr install biber natbib graphicx booktabs nicefrac microtype lipsum amsfonts amsmath amssymb hyperref url longtable array multirow calc
```

`basictex` is ~100 MB; `mactex` is ~5 GB if you want the full distribution.

## Build

From the repo root:

```bash
# Parse-only: verify references.md ↔ body citation closure
uv run python reports/paper1_coverage_inversion/build/build.py --check

# Produce paper.tex + references.bib (no PDF)
uv run python reports/paper1_coverage_inversion/build/build.py

# Produce paper.tex + references.bib + paper.pdf
uv run python reports/paper1_coverage_inversion/build/build.py --pdf
```

The `--check` mode is fast (no pandoc invocation) and reports unresolved citations + orphans. Run before committing changes to section markdown to catch broken `[refkey]` references early.

## What `build.py` does

1. **Parse `references.md`** — reads `### [key] Author. Year. Title.` headers and bullet metadata into a list of bibliography entries; emits `references.bib` as `@misc{}` records (uniform type works for the mixed corpus of papers / blog posts / regulatory letters / specifications).

2. **Concatenate sections** in canonical order (`00_abstract.md` → `11_conclusion.md`); transforms inline citations `[refkey]` and `[k1; k2]` to LaTeX `\citep{}` calls. Any bracket group that does NOT match a defined key is left untouched (preserves markdown link text and inline notation).

3. **Run pandoc** with `--from markdown+tex_math_dollars+raw_tex --to latex --natbib --top-level-division=section`. The Pandoc template wraps the body in the arxiv-style preamble.

4. **Optionally compile the PDF** via `pdflatex → biber → pdflatex × 2` (the standard four-pass run for natbib + bibliography).

## arXiv submission packaging

Once `paper.pdf` builds locally, package for arXiv:

```bash
cd reports/paper1_coverage_inversion/build
tar czf soothsayer-paper1.tar.gz \
    paper.tex \
    references.bib \
    paper.bbl \
    arxiv.sty
```

Per arXiv submission requirements:
- Include the pre-built `.bbl` so arXiv doesn't need to run biber
- Don't include `.aux`, `.log`, `.toc`, intermediate PDFs, or the `.pdf` itself
- All figures (when added) must use `\includegraphics{...}` with paths relative to the submission root
- Avoid `\pdfoutput` commands and `\today` macros (the template uses `\date{April 2026}`)

## Common gotchas (from the Pandoc → LaTeX → arXiv path)

- **Multi-line equations.** `$$...$$` blocks render as `\[...\]` by default. For `align`/`gather` environments, use raw LaTeX inside the markdown (Pandoc's `+raw_tex` extension preserves it).
- **Tables wider than `\linewidth`.** Pandoc emits `longtable`; if a column overflows, add a `\resizebox{\linewidth}{!}{...}` wrapper or convert to a fixed-width `tabularx`.
- **Special characters in citations.** BibTeX is sensitive to `&`, `%`, `_`, `#` — `build.py` escapes these in the `references.bib` writer.
- **arXiv's TeXLive version.** arXiv updates infrequently. If `biber` complains about backend version mismatch, regenerate the `.bbl` with the system `biber` rather than committing whatever was last produced.
- **Date macro.** Don't reintroduce `\today` in the template — arXiv recommends fixed dates so the rendered date doesn't drift on recompile.

## Author info

The template currently sets:

```latex
\title{Coverage-Inversion: A Calibration-Transparent Oracle Primitive for Tokenized RWAs}
\author{Adam Noonan \\ Independent Researcher \\ \texttt{adam@samachi.com}}
\date{April 2026}
```

Edit `pandoc-template.tex` to change. Acknowledgements section can be added before `\bibliography{references}` in the same template.
