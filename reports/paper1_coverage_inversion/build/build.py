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


def write_bibtex(entries: list[dict], out_path: Path) -> None:
    """Render entries as @misc{key, ...} BibTeX records."""
    out = []
    for e in entries:
        fields = [f"  author = {{{bibtex_escape(e['author'])}}}"]
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


def concat_sections(defined_keys: set[str]) -> str:
    """Concatenate the body sections in canonical order, transforming citations."""
    parts: list[str] = []
    for fname in SECTION_ORDER:
        path = PAPER_DIR / fname
        if not path.exists():
            print(f"WARN: missing section {fname}", file=sys.stderr)
            continue
        body = path.read_text()
        body = transform_inline_citations(body, defined_keys)
        parts.append(body)
    return "\n\n".join(parts)


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
    """Compile the .tex via pdflatex + biber + pdflatex × 2."""
    cwd = tex_path.parent
    stem = tex_path.stem
    for cmd in [
        ["pdflatex", "-interaction=nonstopmode", tex_path.name],
        ["biber", stem],
        ["pdflatex", "-interaction=nonstopmode", tex_path.name],
        ["pdflatex", "-interaction=nonstopmode", tex_path.name],
    ]:
        print("$", " ".join(cmd))
        subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", action="store_true", help="also compile to PDF")
    ap.add_argument("--check", action="store_true",
                    help="parse-only; verify citation closure and exit")
    args = ap.parse_args()

    refs_md = PAPER_DIR / "references.md"
    bib_path = BUILD_DIR / "references.bib"
    md_concat = BUILD_DIR / "paper.md"
    tex_path = BUILD_DIR / "paper.tex"

    print(f"Parsing {refs_md.name} ...")
    entries = parse_references_md(refs_md)
    defined_keys = {e["key"] for e in entries}
    print(f"  {len(entries)} entries parsed")

    print(f"Writing {bib_path.name} ...")
    write_bibtex(entries, bib_path)

    print(f"Concatenating {len(SECTION_ORDER)} sections ...")
    body = concat_sections(defined_keys)
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

    print(f"\nRunning pandoc → {tex_path.name} ...")
    run_pandoc(md_concat, tex_path)

    if args.pdf:
        if shutil.which("pdflatex") is None or shutil.which("biber") is None:
            print("\n✗ pdflatex/biber not found. Install: brew install --cask basictex")
            print("  After install, also run: sudo tlmgr install biber natbib graphicx")
            sys.exit(1)
        print(f"\nCompiling {tex_path.name} → paper.pdf ...")
        run_latex(tex_path)
        pdf = tex_path.with_suffix(".pdf")
        if pdf.exists():
            print(f"\n✓ Built {pdf} ({pdf.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
