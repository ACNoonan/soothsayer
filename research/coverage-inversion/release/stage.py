"""Stage the Zenodo upload bundle for Paper 1 (coverage inversion).

Zenodo takes a folder of artifacts; arXiv takes one source tarball and a form.
This script builds the Zenodo folder and refuses to stage anything unless the
gates below pass — the point is that a staged directory is evidence the checks
ran, not just a place files were copied to.

Gates
  G1  the arXiv tarball is NEWER than every section source, so the staged PDF
      and the tarball describe the same paper
  G2  clean-room compile of the tarball (pdflatex only, no bibtex, 3 passes):
      0 LaTeX errors, 0 undefined references or citations, stable page count
  G3  the abstract fits arXiv's hard 1,920-character limit, is pure ASCII, and
      every paragraph after the first begins with a space (arXiv strips
      newlines otherwise and the abstract arrives as one block)
  G4  no figure referenced by the paper is missing from the tarball

Usage
    python release/stage.py --version v1 [--skip-cleanroom]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent                      # research/coverage-inversion
REPO = PAPER.parent.parent               # repo root
BUILD = PAPER / "build"
TARBALL = BUILD / "arxiv_submission.tar.gz"
PDF = BUILD / "paper_v2.pdf"
ABSTRACT = PAPER / "arxiv_form_abstract.txt"
ABSTRACT_LIMIT = 1920

PAPER_TITLE_SLUG = "Noonan_2026_coverage_inversion"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg: str) -> None:
    print(f"\n✗ GATE FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


def gate_freshness() -> None:
    if not TARBALL.exists():
        fail(f"{TARBALL.name} does not exist — run build.py --v2 --arxiv")
    t = TARBALL.stat().st_mtime
    stale = [p.name for p in sorted((PAPER / "rewrite").glob("*.md"))
             if p.stat().st_mtime > t]
    stale += [p.name for p in [PAPER / "references.md"] if p.stat().st_mtime > t]
    if stale:
        fail("tarball is STALE against sources edited after it was built: "
             + ", ".join(stale) + "\n  run: python build/build.py --v2 --arxiv")
    print(f"  G1 freshness       OK  (tarball newer than all sources)")


def gate_cleanroom() -> dict:
    """Compile the tarball the way arXiv does and read the log."""
    with tempfile.TemporaryDirectory() as d:
        with tarfile.open(TARBALL) as tf:
            tf.extractall(d, filter="data")
        for _ in range(3):
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "paper.tex"],
                           cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log = (Path(d) / "paper.log").read_bytes().decode("utf8", "replace")
        errors = len(re.findall(r"^!", log, re.M))
        undef = len(re.findall(r"Warning: (Reference|Citation).*undefined", log, re.I))
        overfull = len(re.findall(r"Overfull", log))
        churn = len(re.findall(r"Label\(s\) may have changed", log))
        out = subprocess.run(["pdfinfo", str(Path(d) / "paper.pdf")],
                             capture_output=True, text=True).stdout
        pages = int(re.search(r"^Pages:\s+(\d+)", out, re.M).group(1))
    if errors or undef:
        fail(f"clean-room compile: {errors} LaTeX errors, {undef} undefined refs/cites")
    if churn:
        fail("clean-room compile did not converge in 3 passes (labels still moving)")
    print(f"  G2 clean room      OK  ({pages} pages, 0 errors, 0 undefined, "
          f"{overfull} overfull, converged)")
    return {"pages": pages, "latex_errors": errors, "undefined": undef,
            "overfull": overfull}


def gate_abstract() -> dict:
    t = ABSTRACT.read_text().rstrip("\n")
    n = len(t.strip())
    if n > ABSTRACT_LIMIT:
        fail(f"abstract is {n} chars, over arXiv's hard limit of {ABSTRACT_LIMIT}")
    if not t.isascii():
        bad = sorted({c for c in t if not c.isascii()})
        fail(f"abstract contains non-ASCII characters arXiv rejects: {bad}")
    paras = [p for p in t.split("\n\n") if p.strip()]
    unindented = [i for i, p in enumerate(paras) if i > 0 and not p.startswith(" ")]
    if unindented:
        fail(f"abstract paragraphs {unindented} do not begin with a space; arXiv "
             "strips the newline and the abstract arrives as one block")
    print(f"  G3 abstract        OK  ({n}/{ABSTRACT_LIMIT} chars, ASCII, "
          f"{len(paras)} paragraphs correctly indented)")
    return {"abstract_chars": n, "abstract_paragraphs": len(paras)}


def gate_figures() -> int:
    with tarfile.open(TARBALL) as tf:
        names = set(tf.getnames())
        tex = tf.extractfile("paper.tex").read().decode("utf8", "replace")
    wanted = set(re.findall(r"\{(figures/[^}]+?)(?:\.pdf)?\}", tex))
    missing = [w for w in wanted
               if f"{w}.pdf" not in names and w not in names]
    if missing:
        fail(f"paper.tex references figures absent from the tarball: {missing}")
    n = len([x for x in names if x.startswith("figures/")])
    print(f"  G4 figures         OK  ({n} figures present, none referenced-but-missing)")
    return n


def zip_tree(out: Path, items: list[tuple[Path, str]]) -> int:
    """Deterministic zip: sorted entries, pinned mtime, no host metadata."""
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in sorted(items, key=lambda x: x[1]):
            if not src.exists():
                continue
            zi = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
            zi.external_attr = 0o644 << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, src.read_bytes())
            count += 1
    return count


def collect(root: Path, patterns: list[str], prefix: str,
            exclude: tuple[str, ...] = ()) -> list[tuple[Path, str]]:
    out = []
    for pat in patterns:
        for p in sorted(root.glob(pat)):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if any(x in rel for x in exclude):
                continue
            out.append((p, f"{prefix}/{rel}"))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="v1")
    ap.add_argument("--skip-cleanroom", action="store_true",
                    help="skip G2 (only when pdflatex is unavailable; the "
                         "manifest records that it did not run)")
    args = ap.parse_args()

    dest = HERE / args.version / "upload"
    dest.mkdir(parents=True, exist_ok=True)

    print(f"Staging Zenodo bundle {args.version} → {dest.relative_to(REPO)}\n")
    print("Gates:")
    gate_freshness()
    cleanroom = ({"skipped": True} if args.skip_cleanroom else gate_cleanroom())
    if args.skip_cleanroom:
        print("  G2 clean room      SKIPPED (recorded in MANIFEST.json)")
    abstract = gate_abstract()
    n_figs = gate_figures()

    print("\nAssembling:")
    # 1. hero / preview image — Zenodo shows the FIRST file as the record preview
    hero_src = REPO / "landing" / "og-image.png"
    shutil.copy2(hero_src, dest / "01_hero.png")
    print(f"  01_hero.png")

    # 2. the paper
    shutil.copy2(PDF, dest / f"02_{PAPER_TITLE_SLUG}.pdf")
    print(f"  02_{PAPER_TITLE_SLUG}.pdf")

    # 3. LaTeX source — the same bytes arXiv compiles
    shutil.copy2(TARBALL, dest / "03_paper_latex_source.tar.gz")
    print(f"  03_paper_latex_source.tar.gz")

    # 4. reference implementation (Python + Rust + Anchor)
    code = []
    code += collect(REPO / "src", ["**/*.py"], "python")
    for crate in ("soothsayer-oracle", "soothsayer-verify", "soothsayer-consumer"):
        code += collect(REPO / "crates" / crate, ["**/*.rs", "**/*.toml"],
                        f"rust/{crate}", exclude=("target/",))
    code += collect(REPO / "programs", ["**/*.rs", "**/*.toml"], "anchor",
                    exclude=("target/",))
    for doc in ("README.md", "STATUS.md", "LICENSE"):
        p = REPO / doc
        if p.exists():
            code.append((p, doc))
    n_code = zip_tree(dest / "04_reference_implementation.zip", code)
    print(f"  04_reference_implementation.zip   ({n_code} files)")

    # 5. calibration artefacts — the 20 deployment scalars and their sidecars
    art = []
    for name in ("lwc_artefact_v1_frozen_20260504.json",
                 "lwc_artefact_v1_frozen_20260504.parquet",
                 "lwc_artefact_v1.json", "mondrian_artefact_v2.json",
                 "overnight_artefact_v1.json"):
        p = REPO / "data" / "processed" / name
        if p.exists():
            art.append((p, name))
    n_art = zip_tree(dest / "05_calibration_artefacts.zip", art)
    print(f"  05_calibration_artefacts.zip     ({n_art} files)")

    # 6. the public band archive — the append-only served-band record a reader
    #    can audit with `soothsayer-verify coverage`
    arch = collect(REPO / "data" / "band_archive", ["*.csv", "*.md"], "band_archive")
    n_arch = zip_tree(dest / "06_public_band_archive.zip", arch)
    print(f"  06_public_band_archive.zip       ({n_arch} files)")

    # ---- checksums + manifest
    files = sorted(p for p in dest.iterdir() if p.name != "CHECKSUMS.txt")
    lines = [f"{sha256(p)}  {p.name}" for p in files]
    (dest / "CHECKSUMS.txt").write_text("\n".join(lines) + "\n")

    git = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                           capture_output=True, text=True).stdout.strip()
    manifest = {
        "version": args.version,
        "staged_at": datetime.now(timezone.utc).isoformat(),
        "git": {"commit": git, "tree_dirty": bool(dirty)},
        "gates": {"freshness": "pass", "cleanroom": cleanroom,
                  "abstract": abstract, "figures_in_tarball": n_figs},
        "counts": {"reference_implementation_files": n_code,
                   "calibration_artefact_files": n_art,
                   "band_archive_files": n_arch},
        "upload_order": [p.name for p in files],
        "sha256": {p.name: sha256(p) for p in files},
    }
    (HERE / args.version / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n")

    total = sum(p.stat().st_size for p in dest.iterdir())
    print(f"\n✓ staged {len(files)} files, {total/1e6:.1f} MB")
    print(f"✓ MANIFEST.json + CHECKSUMS.txt written")


if __name__ == "__main__":
    main()
