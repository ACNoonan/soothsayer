# arXiv submission — Paper 1, coverage inversion

Written 2026-08-25. The counterpart to `release/v1/ZENODO_v1_INSTRUCTIONS.txt`.

**Zenodo takes a folder of artifacts. arXiv takes one source tarball and a form.**
Different package, different failure modes, so they are separate documents.

---

## 0. State

- The tarball is **built and clean-room verified** — see §2. Gate G2 in
  `release/stage.py` re-runs that verification, so it cannot silently go stale.
- **Endorsement is no longer the blocker.** The q-fin.RM endorsement chase
  (`arxiv-endorsement/`) is dead work: the stats.ML submission means stats.AP is
  reachable. Confirm on your arXiv account page before relying on it — see §6.
- Nothing in the package is waiting on anything.

## 1. What arXiv gets, and what it must not get

Upload **`build/arxiv_submission.tar.gz`** (451,902 bytes). Source only —
arXiv compiles the PDF itself.

    paper.tex          (paper_v2.tex, renamed by the builder)
    arxiv.sty
    paper.bbl          (arXiv runs no bibtex; the .bbl IS the bibliography)
    figures/*.pdf      (13 figures)

**Do not upload the PDF.** arXiv rejects PDF-only submissions from
source-capable authors, and a PDF upload forfeits the HTML rendering many
readers now use.

**Do not upload the Zenodo bundle.** No code zip, no band archive, no hero
image. Those live on the Zenodo record, which the Comments field points at.
arXiv is not an artifact host.

Rebuild command, if sources change:

    .venv/bin/python build/build.py --v2 --arxiv

`--arxiv` implies `--pdf`, because the `.bbl` comes out of the bibtex pass.

## 2. The verification that was run (2026-08-25)

Extracted the tarball into a fresh directory and compiled it **the way arXiv
does** — `pdflatex` only, no `bibtex`, three passes:

| check | result |
|---|---|
| pages | **67** |
| LaTeX errors | 0 |
| undefined references / citations | 0 |
| bibliography entries | 65 |
| convergence | stable by pass 3 — no "Label(s) may have changed" |
| overfull boxes | 27 |

The 27 overfull boxes are pre-existing typographic slack, not a submission
blocker; arXiv does not reject on them. They are recorded so a future run can
tell whether the number moved.

### Re-running it

    cd "$(mktemp -d)"
    tar xzf ~/Documents/soothsayer/research/coverage-inversion/build/arxiv_submission.tar.gz
    for i in 1 2 3; do pdflatex -interaction=nonstopmode paper.tex >/dev/null; done
    grep -ac '^!' paper.log                                          # errors    → 0
    grep -aciE 'Warning: (Reference|Citation).*undefined' paper.log   # undefined → 0
    grep -ac 'Label(s) may have changed' paper.log                    # churn     → 0
    pdfinfo paper.pdf | grep -i pages

**Use `grep -a`.** The log is classified as binary, so a plain `grep` prints
nothing and reads exactly like success. This repo's README documents the same
trap; it cost a build once already.

**Three passes, not two.** After pass 2 the log still reports moving labels.
arXiv reruns to a fixed point, so verify at the fixed point.

## 3. Categories — the actual decision

**Primary: `stats.AP` (Statistics — Applications).**

The paper is applied statistics: split-conformal prediction, Kupiec and
Christoffersen backtests, leave-one-symbol-out cross-validation, a 28,620-row
panel. `stats.AP` is where that belongs and it is the category the existing
endorsement reaches.

**Cross-lists to request, in this order:**

1. **`q-fin.RM`** (Risk Management) — the natural readership. This was the
   original primary before the endorsement wall.
2. **`cs.CE`** (Computational Engineering, Finance, and Science) — reaches the
   on-chain/protocol audience the reference implementation is for.

Do **not** request more than two. A long cross-list request reads as
category-spamming to moderators and slows the whole submission.

### How to attempt the cross-category post

Cross-lists are requested **in the same submission form**, not afterwards:
at the category step you pick one primary and then add cross-lists.

- **Endorsement gates the primary.** That is the check arXiv runs at category
  selection, and it is why picking `stats.AP` matters more than the cross-lists.
- **A cross-list request is not guaranteed.** arXiv moderators decide, and they
  can accept it, drop it, or reclassify the paper entirely. A dropped cross-list
  does not block or delay announcement — the paper still goes live under its
  primary.
- **Attempting costs nothing.** If arXiv refuses a cross-list at the form, drop
  it and submit under `stats.AP` alone; you are not blocked, and you can request
  the cross-list later from the abstract page under "Ancillary" → cross-list.
- **If moderators reclassify you into `q-fin.RM`,** accept it. That is a better
  outcome than you asked for, not a problem.

Do not try to reason your way to what arXiv will accept; the rules that matter
here are not fully published. Submit, and let the form answer.

## 4. The submission sequence

1. Log in at arxiv.org → **Start New Submission**.
2. Accept the submission agreement. **License: CC BY 4.0** — see §5.
3. **Select the primary category: `stats.AP`.** This is the endorsement gate.
   arXiv answers with either "you are endorsed" or an endorsement request
   carrying a six-character code. If it asks for a code, stop and read §6.
4. Add cross-lists `q-fin.RM` and `cs.CE`.
5. Upload `arxiv_submission.tar.gz`. Let arXiv compile it. **Read the compile
   log it shows you** — its TeX Live is not yours.
6. **Check arXiv's own PDF preview before continuing.** 67 pages, 13 figures
   present, bibliography rendered.
7. Metadata — values in §5.
8. Preview, then submit.

**Timing.** Mon–Thu before 14:00 ET. Announcement is 20:00 ET the next cycle;
nothing announces Friday or Saturday. Moderation adds 1–4 days and longer is
common for a first submission in a new category, so treat the announced date as
unknown rather than next-day.

## 5. Field values and traps

**Title**
> Coverage Inversion: Calibration-Transparent Fair-Value Oracles for Closed-Market Hours

**Abstract — `arxiv_form_abstract.txt`, 1,827 characters.** The limit is 1,920
and it is a hard rejection at the form, not a warning. Re-count after any edit:

    python3 -c "import pathlib;print(len(pathlib.Path('arxiv_form_abstract.txt').read_text().strip()))"

Two things about that file, both deliberate — gate G3 enforces them:

- **Paragraph 2 begins with a single leading space.** arXiv strips newlines
  *unless* the next line starts with whitespace. Without it the abstract arrives
  as one wall of text. Do not "tidy" the indentation.
- **It is pure ASCII.** arXiv does not accept Unicode here, which is why the file
  writes `tau`, `+/-` and `--` rather than the symbols the paper uses.

**License — irrevocable once submitted.** Pick **CC BY 4.0**, matching the Zenodo
record. Both carry the same text, so consistency matters. arXiv's default
perpetual non-exclusive licence is *more* restrictive than what Zenodo already
grants, which makes it the inconsistent choice.

**Comments field** — Zenodo v1 published 2026-08-25, so this is final text,
not a template. Paste it exactly:

> 67 pages, 13 figures. Reference implementation (Python, Rust, Anchor), calibration artefacts, and the public band archive: https://doi.org/10.5281/zenodo.22094768

That is the **concept** DOI (10.5281/zenodo.22094768), taken from the
record's API `conceptdoi` field rather than inferred. The version DOI for v1 is
10.5281/zenodo.22094769 — one digit apart, and the wrong one to
publish, because it pins v1 while the concept DOI follows every future version.

**DOI field: leave blank.** It is for a published journal version. The Zenodo
DOI goes in Comments.

**MSC / ACM classes:** optional, and safe to leave empty. If you want them,
`62P05` (statistics applied to actuarial/financial sciences) is the honest fit.

## 6. If arXiv asks for an endorsement code

It means stats.AP did not inherit from your stats.ML submission. That is
possible: arXiv endorsement is per subject class, and auto-endorsement across
related classes is real but not documented in a way you can rely on.

The draft persists, so nothing is lost. The code is minted the moment you pick
the category, and an endorser enters it at https://arxiv.org/auth/endorse.

Forwarding is allowed. arXiv's wording is an *or*:

> "You should know the person that you endorse **or** you should see the paper
> that the person intends to submit."

A stranger who reads the Zenodo PDF is explicitly inside policy. The separate
rule against endorsing "third-parties or proxies" bars endorsing someone
submitting *someone else's* work — it does not bar forwarding your own.

`arxiv-endorsement/top_candidates.md` still holds the ranked q-fin.RM list if it
is ever needed again.

## 7. Ordering, and why it is this way

**Publish Zenodo first, then submit to arXiv.**

The arXiv Comments field carries the Zenodo concept DOI, and the concept DOI has
to exist before you can paste it. Doing it the other way round means editing the
arXiv metadata after announcement, which is possible but leaves v1 pointing at
nothing.

The reverse dependency — Zenodo's "Related works" wanting the arXiv ID — is the
softer one: a Zenodo record can be edited to add an identifier without cutting a
new version.

    1. Zenodo v1  → publish → note the CONCEPT DOI (not the version DOI)
    2. arXiv      → Comments field carries that concept DOI → submit
    3. after announcement → add the arXiv ID to Zenodo "Related works"
    4. record both in reports/methodology_history.md
