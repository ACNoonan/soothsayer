"""
Markdown → LaTeX → arXiv-ready PDF build script.

Pipeline:
  1. Parse references.md into a BibTeX file (references.bib).
  2. Concatenate the section markdown files in canonical order.
  3. Run pandoc to produce paper.tex (citations rendered via natbib).
  4. Optionally invoke pdflatex + biber + pdflatex × 2 to produce paper.pdf.

The arxiv-style preamble (single-column, NIPS-derived) lives in arxiv.sty next
to this script; the Pandoc template (pandoc-template.tex) injects title block,
author info, and the \\usepackage{arxiv}.

Usage:
  uv run python build.py            # produces paper.tex + references.bib
  uv run python build.py --pdf      # additionally produces paper.pdf
  uv run python build.py --arxiv    # additionally writes arxiv_submission.tar.gz (source-only)
  uv run python build.py --aft      # builds the AFT 20-page main text → aft_paper.pdf
  uv run python build.py --check    # parse-only; verifies citation closure
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parent
PAPER_DIR = BUILD_DIR.parent
REPO_ROOT = PAPER_DIR.parent.parent  # research/coverage-inversion → repo root

# The Vercel landing site serves a snapshot of the v2 PDF at this path so the
# "Read the paper" links open the current build. Refreshed on every --v2 build.
LANDING_PDF = REPO_ROOT / "landing" / "coverage-inversion.pdf"

# Human-readable copy of the final PDF kept alongside paper.pdf so the file
# name matches the paper title when shared outside the repo. Refreshed on
# every --pdf build; update this string if the title in pandoc-template.tex
# changes.
NAMED_PDF = "Coverage-Inversion - Calibration-Transparent Fair-Value Oracles for Closed-Market Hours.pdf"
# Source-only arXiv submission tarball (paper.tex + arxiv.sty + paper.bbl + figures).
ARXIV_TARBALL = "arxiv_submission.tar.gz"

# Canonical section order. Files prefixed by 0X are the body; references.md
# is rendered separately via the BibTeX path.
SECTION_ORDER = [
    "00_abstract.md",
    "01_introduction.md",
    "02_related_work.md",
    "problem_statement.md",
    "04_methodology.md",
    "05_data_and_regimes.md",
    "06_results.md",
    "07_ablation.md",
    "08_serving_layer.md",
    "09_limitations.md",
    "10_future_work.md",
    "11_conclusion.md",
    "12_appendix_reproducibility.md",
]

# v2 structural rewrite (2026-07, SPINE.md/DISPOSITION.md): sections live in
# rewrite/, appendices are per-letter files. `--v2` builds these under the
# paper_v2 stem; the v1 SECTION_ORDER build remains untouched.
V2_DIR_NAME = "rewrite"
SECTION_ORDER_V2 = [
    "00_abstract.md",
    "01_blind_window.md",
    "02_related_work.md",
    "03_primitive.md",
    "04_architecture.md",
    "05_data.md",
    "06_contract_holds.md",
    "07_load_bearing.md",
    "08_where_it_fails.md",
    "09_conclusion.md",
]
APPENDIX_ORDER_V2 = [
    "10_appendix_A.md",
    "11_appendix_B.md",
    "12_appendix_C.md",
    "13_appendix_D.md",
    "14_appendix_E.md",
    "15_appendix_F.md",
]

# Map references.md "### [key] Author. Year. Title." entries → BibTeX @misc.
# We use @misc uniformly because the corpus mixes blog posts, academic papers,
# regulatory letters, and technical specifications — @misc renders cleanly for
# all of them under natbib's default style.
REF_HEADER_RX = re.compile(r"^### \[([a-zA-Z0-9_-]+)\]\s*(.+?)\s*$")
URL_RX = re.compile(r"\*\*URL / DOI:\*\*\s*(.+)")
VENUE_RX = re.compile(r"\*\*Venue:\*\*\s*(.+)")


def parse_references_md(refs_md: Path) -> list[dict]:
    """Parse references.md → list of dicts with key/title/author/year/url/venue."""
    entries: list[dict] = []
    current: dict | None = None
    for line in refs_md.read_text().splitlines():
        m = REF_HEADER_RX.match(line)
        if m:
            if current is not None:
                entries.append(current)
            key, header_rest = m.group(1), m.group(2)
            # Parse "Author. Year. Title." pattern; tolerant of variations
            year_match = re.search(r"\b(19|20)\d{2}\b", header_rest)
            year = year_match.group(0) if year_match else ""
            # Author = everything before the year; title = everything after the year.
            if year:
                pre, post = header_rest.split(year, 1)
                author = pre.rstrip(" .,")
                title = post.lstrip(" .,").rstrip(" .")
            else:
                author = header_rest.rstrip(" .")
                title = ""
            current = {
                "key": key,
                "author": author,
                "year": year,
                "title": title,
                "url": "",
                "venue": "",
            }
        elif current is not None:
            u = URL_RX.search(line)
            if u:
                current["url"] = u.group(1).strip()
            v = VENUE_RX.search(line)
            if v:
                current["venue"] = v.group(1).strip()
    if current is not None:
        entries.append(current)
    return entries


def bibtex_escape(s: str) -> str:
    """Escape characters that confuse BibTeX."""
    return s.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")


def normalise_authors(raw: str) -> str:
    """Convert references.md's comma-separated author list to BibTeX's ` and `.

    references.md format:  "Breidenbach, L., Cachin, C., Chan, B., ..."
    BibTeX expectation:    "Breidenbach, L. and Cachin, C. and Chan, B. and ..."

    Split on commas, pair them into (Last, FirstInitials) tuples, rejoin
    with ` and `. A single name with no comma (e.g. "Pyth Network") passes
    through unchanged.
    """
    pieces = [p.strip() for p in raw.split(",") if p.strip()]
    if len(pieces) <= 1:
        return raw  # corporate/single-name author or already-normalised
    # If there's an odd number of pieces and we can't cleanly pair, fall back
    # to single-name handling — the entry probably is a corporate author with
    # commas in the name and we'd be safer not mangling it.
    if len(pieces) % 2 != 0:
        return raw
    pairs = []
    for i in range(0, len(pieces), 2):
        last, firsts = pieces[i], pieces[i + 1]
        # Skip the pair if `firsts` doesn't look like initials/given names
        # (e.g. starts with a lowercase letter — likely the name pieces don't
        # actually fit the Last, First pattern).
        if not firsts or not firsts[0].isupper():
            return raw
        pairs.append(f"{last}, {firsts}")
    return " and ".join(pairs)


def write_bibtex(entries: list[dict], out_path: Path) -> None:
    """Render entries as @misc{key, ...} BibTeX records."""
    out = []
    for e in entries:
        fields = [f"  author = {{{bibtex_escape(normalise_authors(e['author']))}}}"]
        if e["year"]:
            fields.append(f"  year = {{{e['year']}}}")
        if e["title"]:
            fields.append(f"  title = {{{bibtex_escape(e['title'])}}}")
        if e["venue"]:
            fields.append(f"  howpublished = {{{bibtex_escape(e['venue'])}}}")
        if e["url"]:
            fields.append(f"  url = {{{e['url']}}}")
        body = ",\n".join(fields)
        out.append(f"@misc{{{e['key']},\n{body}\n}}\n")
    out_path.write_text("\n".join(out))


def transform_inline_citations(text: str, defined_keys: set[str]) -> str:
    """Convert markdown [refkey] and [k1; k2] citations to natbib \\citep{}.

    A bracket group qualifies as a citation iff every semicolon-separated piece
    is a key defined in references.bib. This avoids false-positives on markdown
    link text (which is followed by `(` — not handled here, but the simple
    "next char is `(`" check would also work).
    """
    rx = re.compile(r"\[([a-zA-Z0-9_;\s-]+)\](?!\()")

    def replace(m: re.Match) -> str:
        raw = m.group(1)
        pieces = [p.strip() for p in raw.split(";")]
        if not pieces or any(p not in defined_keys for p in pieces):
            return m.group(0)  # not a citation; leave as-is
        return r"\citep{" + ",".join(pieces) + "}"

    return rx.sub(replace, text)


def clean_headings(body: str) -> str:
    """Strip authorial conventions from headings that Pandoc would render literally.

    The .md files use these conventions for human-readable navigation when
    browsing sources; LaTeX numbering subsumes them in the rendered paper:

      `# §1 — Introduction (draft)` → `# Introduction`
      `## 1.1 How oracles answer ...` → `## How oracles answer ...`
      `### 6.4.1 Extended diagnostics` → `### Extended diagnostics`
      `# Abstract` → `# Abstract {-}`  (unnumbered)
    """
    lines = body.splitlines()
    out: list[str] = []
    for line in lines:
        m = re.match(r"^(#+)\s+(.*?)\s*$", line)
        if not m:
            out.append(line)
            continue
        hashes, text = m.group(1), m.group(2)
        # Strip "§N — " prefix
        text = re.sub(r"^§\d+[A-Z]?\s*[—–-]\s*", "", text)
        # Strip "Appendix X — " prefix (LaTeX \appendix letters the sections)
        text = re.sub(r"^Appendix [A-F]\s*[—–-]\s*", "", text)
        # Strip "N.M" or "N.M.K" numeric prefix on subheadings
        text = re.sub(r"^\d+(\.\d+)+\s+", "", text)
        # Strip bare "N " prefix on top-level headings (e.g. "# 8 Where it fails")
        text = re.sub(r"^\d+\s+", "", text)
        # Strip "X.N" / "X.N.M" letter-prefixed appendix subheadings
        text = re.sub(r"^[A-F](\.\d+)+\s+", "", text)
        # Strip "(draft...)" suffix
        text = re.sub(r"\s*\(draft[^)]*\)\s*$", "", text)
        # Mark abstract as unnumbered
        if hashes == "#" and text.strip().lower() == "abstract":
            out.append(f"# Abstract {{-}}")
        else:
            out.append(f"{hashes} {text}")
    return "\n".join(out)


def fix_typographic_numbers(body: str) -> str:
    """Convert LaTeX typographic-comma `5{,}986` to plain `5,986`.

    Pandoc escapes `{`/`}` braces in prose contexts even with +raw_tex; wrapping
    the number as inline math caused nested-math collisions where the markdown
    already had `\\(N = 5{,}986\\)`. Plain commas are unambiguous, render
    correctly in both prose and math mode (the math-mode comma kerning is
    visually fine), and avoid the edge cases.
    """
    return re.sub(r"(\d+)\{,\}(\d+)", r"\1,\2", body)


def concat_sections(defined_keys: set[str], aft: bool = False,
                    v2: bool = False) -> str:
    """Concatenate the body sections in canonical order, transforming citations.

    `aft=True` builds the AFT main text: each section prefers its condensed
    override in `aft/<file>` when present (else the full version), and the
    reproducibility section is dropped (it belongs in the appendix, which is not
    part of the 20-page main text). See reports/active/aft_carve_plan.md.

    `v2=True` builds the structural rewrite from rewrite/: main sections, then
    a raw `\\appendix` marker, then the per-letter appendix files, so LaTeX
    letters the appendices itself.
    """

    def render(path: Path) -> str:
        body = path.read_text()
        body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)  # working notes
        body = clean_headings(body)
        body = transform_inline_citations(body, defined_keys)
        body = fix_typographic_numbers(body)
        return body

    parts: list[str] = []
    if v2:
        base = PAPER_DIR / V2_DIR_NAME
        for fname in SECTION_ORDER_V2:
            path = base / fname
            if not path.exists():
                print(f"WARN: missing section {fname}", file=sys.stderr)
                continue
            parts.append(render(path))
        parts.append("\\appendix")
        for fname in APPENDIX_ORDER_V2:
            path = base / fname
            if not path.exists():
                print(f"WARN: missing appendix {fname}", file=sys.stderr)
                continue
            parts.append(render(path))
        return "\n\n".join(parts)

    for fname in SECTION_ORDER:
        if aft and fname == "12_appendix_reproducibility.md":
            continue
        path = PAPER_DIR / fname
        if aft and (PAPER_DIR / "aft" / fname).exists():
            path = PAPER_DIR / "aft" / fname
        if not path.exists():
            print(f"WARN: missing section {fname}", file=sys.stderr)
            continue
        parts.append(render(path))
    return "\n\n".join(parts)


def ensure_figures_symlink() -> None:
    """Create `build/figures -> ../figures` so the relative `figures/...`
    image refs in the section markdown resolve under pdflatex's CWD (the
    build dir). Idempotent."""
    link = BUILD_DIR / "figures"
    target = Path("../figures")
    if link.is_symlink():
        if link.readlink() == target:
            return
        link.unlink()
    elif link.exists():
        raise RuntimeError(
            f"{link} exists and is not a symlink; refuse to overwrite."
        )
    link.symlink_to(target)


def run_pandoc(md_path: Path, tex_path: Path) -> None:
    """Invoke pandoc to produce paper.tex."""
    template = BUILD_DIR / "pandoc-template.tex"
    cmd = [
        "pandoc",
        str(md_path),
        "-o", str(tex_path),
        "--from", "markdown+tex_math_dollars+raw_tex",
        "--to", "latex",
        "--standalone",
        "--template", str(template),
        "--natbib",
        "--top-level-division=section",
    ]
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def run_latex(tex_path: Path) -> None:
    """Compile the .tex via pdflatex + bibtex + pdflatex × 2.

    Pandoc's `--natbib` mode emits BibTeX-style `\\citation{}` markers in the
    .aux, so the right backend is bibtex, not biber. Use --biblatex on the
    pandoc side if switching to biber later.

    pdflatex returns non-zero exit when there are *any* unresolved references
    (which is normal on the first pass — the .bbl doesn't exist yet — and on
    the post-bibtex pass — labels haven't yet been read). We rely on the final
    pdf existing as the success signal, not the per-pass exit code. bibtex,
    by contrast, only fails on real errors (missing .bib entries, parse
    failures); we keep `check=True` for it.
    """
    cwd = tex_path.parent
    stem = tex_path.stem
    passes = [
        (["pdflatex", "-interaction=nonstopmode", tex_path.name], False),
        (["bibtex", stem], True),
        (["pdflatex", "-interaction=nonstopmode", tex_path.name], False),
        (["pdflatex", "-interaction=nonstopmode", tex_path.name], False),
    ]
    for cmd, must_succeed in passes:
        print("$", " ".join(cmd))
        result = subprocess.run(cmd, cwd=cwd)
        if must_succeed and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd)

    # pdflatex DROPS raw-Unicode glyphs that lack a \DeclareUnicodeCharacter,
    # leaving only a log error — the 2026-05 builds shipped blank gate-table
    # cells this way. Fail loudly so a new undeclared glyph can't slip out.
    log = (cwd / f"{stem}.log").read_text(errors="replace")
    flat = log.replace("\n", "")
    dropped = sorted(set(re.findall(
        r"Unicode character\s+\S+\s+\((U\+[0-9A-Fa-f]+)\)", flat)))
    if dropped:
        raise RuntimeError(
            f"pdflatex dropped undeclared Unicode characters: {dropped} — "
            "add \\DeclareUnicodeCharacter entries to pandoc-template.tex"
        )


def make_arxiv_package(tex_path: Path) -> None:
    """Assemble the source-only arXiv submission tarball next to paper.tex.

    Contents: paper.tex, arxiv.sty, paper.bbl, and *exactly* the figures
    referenced by paper.tex (auto-detected, so adding/removing a figure needs
    no edit here). No .pdf/.aux/.log — arXiv wants source only and rebuilds the
    PDF from the bundled .bbl (no .bib / bibtex pass needed). Uses Python's
    tarfile so the archive is flat, deterministic, dereferences the
    `build/figures` symlink, and carries no macOS AppleDouble cruft.

    Requires the .bbl, which the bibtex pass of run_latex() produces — so this
    runs only after a --pdf compile (the --arxiv flag implies it).
    """
    import tarfile

    bbl = tex_path.with_suffix(".bbl")
    sty = BUILD_DIR / "arxiv.sty"
    missing = [p.name for p in (tex_path, bbl, sty) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"arXiv package needs {missing} — run with --pdf to generate the .bbl first."
        )

    tex = tex_path.read_text()
    rels = sorted(set(re.findall(r"\{(figures/[^{}]+\.(?:pdf|png|jpe?g))\}", tex)))
    figs: list[tuple[Path, str]] = []
    for rel in rels:
        src = (BUILD_DIR / rel).resolve()  # follows the figures -> ../figures symlink
        if not src.exists():
            raise FileNotFoundError(f"referenced figure missing: {rel} -> {src}")
        figs.append((src, rel))

    out = BUILD_DIR / ARXIV_TARBALL
    with tarfile.open(out, "w:gz") as tf:
        tf.add(tex_path, arcname="paper.tex")
        tf.add(sty, arcname="arxiv.sty")
        tf.add(bbl, arcname="paper.bbl")
        for src, rel in figs:
            tf.add(src, arcname=rel)  # arcname keeps the flat figures/<name> layout
    print(f"✓ arXiv package → {out.name} ({out.stat().st_size:,} bytes; "
          f"paper.tex + arxiv.sty + paper.bbl + {len(figs)} figures)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", action="store_true", help="also compile to PDF")
    ap.add_argument("--arxiv", action="store_true",
                    help="also assemble the source-only arXiv tarball (implies --pdf, for the .bbl)")
    ap.add_argument("--aft", action="store_true",
                    help="build the AFT 20-page main text (aft/ section overrides, no appendix) → aft_paper.pdf")
    ap.add_argument("--v2", action="store_true",
                    help="build the 2026-07 structural rewrite from rewrite/ → paper_v2.pdf")
    ap.add_argument("--check", action="store_true",
                    help="parse-only; verify citation closure and exit")
    args = ap.parse_args()

    if args.v2 and args.aft:
        ap.error("--v2 and --aft are mutually exclusive")
    stem = "paper_v2" if args.v2 else ("aft_paper" if args.aft else "paper")
    refs_md = PAPER_DIR / "references.md"
    bib_path = BUILD_DIR / "references.bib"
    md_concat = BUILD_DIR / f"{stem}.md"
    tex_path = BUILD_DIR / f"{stem}.tex"

    print(f"Parsing {refs_md.name} ...")
    entries = parse_references_md(refs_md)
    defined_keys = {e["key"] for e in entries}
    print(f"  {len(entries)} entries parsed")

    print(f"Writing {bib_path.name} ...")
    write_bibtex(entries, bib_path)

    label = "v2 rewrite" if args.v2 else ("AFT main text" if args.aft else "full")
    print(f"Concatenating sections ({label}) ...")
    body = concat_sections(defined_keys, aft=args.aft, v2=args.v2)
    # Combining-accent sequences (sigma/p + U+0302) cannot be declared via
    # \DeclareUnicodeCharacter — normalise them to math macros before
    # pandoc. Any *other* stray undeclared glyph is caught loudly by the
    # post-compile log check in run_latex().
    body = (body
            .replace("\u03c3\u0302", "\\ensuremath{\\hat\\sigma}")
            .replace("p\u0302", "\\ensuremath{\\hat p}"))
    md_concat.write_text(body)
    print(f"  → {md_concat.name} ({len(body):,} bytes)")

    # Citation closure check (post-transform: any remaining [refkey] is unresolved)
    rx = re.compile(r"\\citep\{([^}]+)\}")
    cited_keys = set()
    for m in rx.finditer(body):
        cited_keys.update(p.strip() for p in m.group(1).split(","))
    unresolved = cited_keys - defined_keys
    orphans = defined_keys - cited_keys
    print(f"\nCitation closure:")
    print(f"  cited keys:      {len(cited_keys)}")
    print(f"  defined keys:    {len(defined_keys)}")
    print(f"  unresolved:      {len(unresolved)}  {sorted(unresolved) or 'OK'}")
    print(f"  orphans:         {len(orphans)}     {sorted(orphans) or 'OK'}")

    if args.check:
        sys.exit(0 if not unresolved else 1)

    if shutil.which("pandoc") is None:
        print("\n✗ pandoc not found. Install with: brew install pandoc")
        sys.exit(1)

    ensure_figures_symlink()

    print(f"\nRunning pandoc → {tex_path.name} ...")
    run_pandoc(md_concat, tex_path)

    if args.pdf or args.arxiv or args.aft:
        if shutil.which("pdflatex") is None or shutil.which("bibtex") is None:
            print("\n✗ pdflatex/bibtex not found. Install: brew install --cask basictex")
            print("  After install, also run: sudo /Library/TeX/texbin/tlmgr install"
                  " collection-latexrecommended units multirow")
            sys.exit(1)
        print(f"\nCompiling {tex_path.name} → {stem}.pdf ...")
        run_latex(tex_path)
        pdf = tex_path.with_suffix(".pdf")
        if pdf.exists():
            print(f"\n✓ Built {pdf} ({pdf.stat().st_size:,} bytes)")
            if not args.aft and not args.v2:  # named copy is for the v1 arXiv build only
                named = BUILD_DIR / NAMED_PDF
                shutil.copyfile(pdf, named)
                print(f"✓ Copied → {named.name}")
            if args.v2 and LANDING_PDF.parent.is_dir():  # refresh the landing snapshot
                shutil.copyfile(pdf, LANDING_PDF)
                print(f"✓ Copied → landing/{LANDING_PDF.name}")
        if args.arxiv:
            make_arxiv_package(tex_path)


if __name__ == "__main__":
    main()
