# Submission checklist — Paper 1

> ## State, 2026-09-12
>
> **Parts 0–2 are done.** Zenodo published 2026-08-25: concept DOI
> **10.5281/zenodo.22094768**, v1 version DOI 10.5281/zenodo.22094769, six files, CC BY 4.0.
> arXiv received the submission and it is **still on hold**, q-fin.RM primary requested. A first
> submission in a new primary category sits longer than the usual 1–4 days, and nothing Adam does
> moves it.
>
> **The submit ID at 2.17 was never written down**, and no file in this repo records the submission
> date either. Both are recoverable from the arXiv submission page or the confirmation email; fill
> them in when you have them.
>
> **Part 3 is the live list** — every box there waits on the announcement. Item 3.4 (STATUS.md) is
> partly done already: the Paper 1 row and a new "Paper 1 release state" section carry the Zenodo
> DOIs and the hold, and want only the arXiv ID added.
>
> **Standing decision while the hold is open:** do not file a cross-list request on the exceedance
> paper's arXiv record (arXiv:2608.21262). It is the published parent result this paper builds on,
> and a request there invites a moderator to review both papers' scope at once for the sake of a
> stat.ME cross-list that gains nothing.

**Follow this top to bottom in one sitting.** The two reference documents
(`ARXIV-SUBMISSION-PLAYBOOK.md`, `v1/ZENODO_v1_INSTRUCTIONS.txt`) explain *why*;
this one is the *sequence*. Boxes are in dependency order — Zenodo must publish
before arXiv, because arXiv's Comments field carries the Zenodo DOI.

Budget: about 40 minutes for Zenodo, 30 for arXiv. Submit **Mon–Thu before
14:00 ET** or the arXiv half waits for the next cycle.

---

## PART 0 — Pre-flight (terminal, 5 min)

- [ ] **0.1** Re-stage and let the gates run. If any gate fails, stop — a failed
      gate means the bundle and the paper disagree.

          cd ~/Documents/soothsayer
          .venv/bin/python research/coverage-inversion/release/stage.py --version v1

      Expect four `OK` lines and `✓ staged 6 files`.

- [ ] **0.2** Open the staged folder in Finder; you will drag from it twice.

          open research/coverage-inversion/release/v1/upload

- [ ] **0.3** Confirm the tarball you will give arXiv is the one the gates
      checked.

          shasum -a 256 research/coverage-inversion/build/arxiv_submission.tar.gz
          shasum -a 256 research/coverage-inversion/release/v1/upload/03_paper_latex_source.tar.gz

      The two hashes must match. They are the same bytes by construction; this
      catches a rebuild that happened between staging and submitting.

---

## PART 1 — Zenodo (publish FIRST)

### 1A. Create the record

- [ ] **1.1** Go to https://zenodo.org and log in. GitHub SSO is fine.
- [ ] **1.2** Top right: **New upload** (Zenodo sometimes labels this
      "New submission" — same thing).
- [ ] **1.3** Leave the community field empty. Do not submit to a community on
      the first publish; a community review can hold the record and you need the
      DOI today.

### 1B. Files — order matters

Zenodo takes the **first file** as the record preview image. Upload in this
order and do not let the browser reorder them.

- [ ] **1.4** Drag all six files in at once, then check the list reads:

      1. `01_hero.png`                              65 KB
      2. `02_Noonan_2026_coverage_inversion.pdf`   1.0 MB — 67 pages
      3. `03_paper_latex_source.tar.gz`            452 KB
      4. `04_reference_implementation.zip`         258 KB — 88 files
      5. `05_calibration_artefacts.zip`            150 KB — 5 files
      6. `06_public_band_archive.zip`               94 KB — 4 files

      Do **not** upload `CHECKSUMS.txt` or `MANIFEST.json`. They are your
      staging evidence, not part of the record.

- [ ] **1.5** If the preview thumbnail shows anything other than the
      "anatomy of a read" schematic, the order is wrong. Fix it before saving.

### 1C. Metadata

- [ ] **1.6 DOI** → Zenodo asks whether you already have one. You do not.
      Click **"Get a DOI now"** to reserve one.

      The "I already have a DOI" path is for content assigned an identifier
      elsewhere. arXiv mints its own DOI later, but that identifies the arXiv
      record, not this one — they are two records that point at each other, not
      one record with two names.

      A *reserved* DOI is not registered until you press Publish, and what the
      reserve shows you is the **version** DOI. Take the concept DOI from the
      published record page at step 1.19; do not paste the reserved one into
      arXiv.

- [ ] **1.7 Resource type** → `Publication` → `Preprint`.

      **Not `Software`.** If the form is showing you *Repository URL* and
      *Programming languages*, you have Software selected — those are
      software-type fields. The primary object here is the 67-page paper; the
      code is an attached artifact. Choosing Software demotes the paper to an
      attachment on a software record, which reads wrong beside the arXiv
      version and is worse for citation.

      If those fields remain as optional extras after switching, fill them —
      they are accurate and cost nothing:

      - Repository URL: `https://github.com/ACNoonan/soothsayer`  (public)
      - Programming languages: `Python`, `Rust`  (the Anchor programs are Rust)

- [ ] **1.8 Publication date** → today's date, the day you publish. Zenodo
      defaults to it. Do **not** backdate it to the paper's data cutoff — the
      field means "when did this become public", not "when did the data end".

- [ ] **1.9 Title** — paste exactly:

      Coverage Inversion: Calibration-Transparent Fair-Value Oracles for Closed-Market Hours

- [ ] **1.10 Authors** — `Noonan, Adam`. Add your ORCID if you have one; it is
      the only field here that pays off later, because it links this record to
      the stats.ML paper automatically.

- [ ] **1.11 Description** — open `v1/ZENODO_v1_DESCRIPTION.txt`, copy
      **everything below the dashed line**, paste.

      Then **read it back in the box.** It is a rich-text field and it mangles
      pasted plain text: the usual casualties are the indented block under
      "WHAT IS HERE" and the double line breaks between sections. Fix the
      paragraph breaks by hand if they collapsed.

- [ ] **1.12 Version** — `v1`

- [ ] **1.13 Language** — `English`

- [ ] **1.14 Keywords** — add one at a time, pressing Enter after each:

      conformal prediction · calibration · oracle · tokenized equities ·
      real-world assets · Solana · risk management · coverage ·
      split conformal · DeFi

- [ ] **1.15 License** — `Creative Commons Attribution 4.0 International`
      (CC BY 4.0). This must match what you pick on arXiv.

- [ ] **1.16 Related works** — leave empty. The arXiv ID does not exist yet;
      you add it in step 3.2 without cutting a new version.

- [ ] **1.17 Series information** — leave empty.

### 1D. Publish

- [ ] **1.18** Press **Save** first, not Publish. Read the draft page.
- [ ] **1.19** Check the description rendered. Check the preview image.
- [ ] **1.20** **Publish.**

      This is irreversible. A published Zenodo record cannot be deleted, only
      superseded by a new version.

### 1E. Capture the DOI — the step everything downstream needs

- [ ] **1.21** The record page now shows **two** DOIs. You want the one labelled
      **"Cite all versions"** / concept DOI, not the version DOI.

      - Concept DOI  `10.5281/zenodo.XXXXXXX`  ← resolves to newest forever
      - Version DOI  `10.5281/zenodo.YYYYYYY`  ← pins v1, will look stale

- [ ] **1.22** Write the **concept** DOI here before moving on.

      **DONE 2026-08-25:**

          ZENODO CONCEPT DOI: 10.5281/zenodo.22094768
          version DOI (v1):   10.5281/zenodo.22094769

      Read off the record's API (`conceptdoi`), not the record page — the
      page's Versions panel is easy to miss and the two numbers differ by one
      digit:

          curl -s https://zenodo.org/api/records/<ID> | python3 -m json.tool | grep -i conceptdoi

- [ ] **1.23** Verify the files downloaded intact:

          cd ~/Downloads   # after downloading a couple from the record
          shasum -a 256 -c ~/Documents/soothsayer/research/coverage-inversion/release/v1/upload/CHECKSUMS.txt

---

## PART 2 — arXiv

### 2A. Start, and hit the endorsement gate early

- [ ] **2.1** Go to https://arxiv.org and log in.
- [ ] **2.2** **Start New Submission.**
- [ ] **2.3** Accept the submission agreement.

- [ ] **2.4 License** → **CC BY 4.0**, matching Zenodo.

      Irrevocable once submitted. arXiv's default perpetual non-exclusive
      licence is *more* restrictive than what you have already granted on
      Zenodo for the same text, so the default is the inconsistent choice.

- [ ] **2.5 Primary category** → `stats.AP` (Statistics — Applications).

      **This is the endorsement gate.** arXiv answers one of two ways:

      - *"You are endorsed"* → continue to 2.6.
      - *An endorsement request with a six-character code* → stats.AP did not
        inherit from your stats.ML submission. **Stop; the draft persists.**
        Read `ARXIV-SUBMISSION-PLAYBOOK.md` §6. Nothing is lost and the Zenodo
        record is already live and citable.

- [ ] **2.6 Cross-lists** → add **`q-fin.RM`** and **`cs.CE`**. Two, not more.

      A long cross-list request reads as category-spamming and slows
      moderation. If the form refuses a cross-list, drop it and continue —
      cross-lists are moderator-decided, cannot block announcement, and can be
      requested later from the abstract page.

### 2B. Files

- [ ] **2.7** Upload **`research/coverage-inversion/build/arxiv_submission.tar.gz`**.

      Source only. Do **not** upload the PDF — arXiv rejects PDF-only
      submissions from source-capable authors and you would forfeit the HTML
      rendering. Do **not** upload anything from the Zenodo bundle.

- [ ] **2.8** Let arXiv compile. **Read its compile log**, not just the green
      tick. Its TeX Live is not yours.

- [ ] **2.9** Open arXiv's own PDF preview and check three things:
      - page count is **67**
      - all 13 figures rendered (spot-check H2, H4, S2)
      - the bibliography is present — 65 entries

### 2C. Metadata

- [ ] **2.10 Title** — same string as 1.7.

- [ ] **2.11 Abstract** — paste the contents of
      `research/coverage-inversion/arxiv_form_abstract.txt` **verbatim**.

      **Do not retype it and do not tidy it.** Paragraph 2 begins with a single
      leading space on purpose: arXiv strips newlines unless the next line
      starts with whitespace, and without it your abstract arrives as one wall
      of text. It is 1,827 of a hard 1,920 characters, and it is pure ASCII
      because arXiv rejects Unicode in this field.

- [ ] **2.12 Comments** — paste verbatim (the DOI is already filled in):

          67 pages, 13 figures. Reference implementation (Python, Rust, Anchor), calibration artefacts, and the public band archive: https://doi.org/10.5281/zenodo.22094768

- [ ] **2.13 DOI field** — leave **blank**. It is for a published journal
      version. The Zenodo DOI belongs in Comments, which you just did.

- [ ] **2.14 MSC/ACM class** — optional. `62P05` if you want one.

### 2D. Submit

- [ ] **2.15** Preview the whole submission.
- [ ] **2.16** **Submit.**
- [ ] **2.17** Record the submission identifier:

          ARXIV SUBMIT ID: ______________

      Announcement is 20:00 ET the next cycle; nothing announces Friday or
      Saturday. Moderation adds 1–4 days and longer is normal for a first
      submission in a new primary category. Treat the announced date as
      unknown, not next-day.

---

## PART 3 — After arXiv announces

- [ ] **3.1** Note the arXiv ID: `arXiv:XXXX.XXXXX`.

- [ ] **3.2** Edit the Zenodo record (no new version needed):
      **Related works** → relation `is identical to` → `arXiv:XXXX.XXXXX`.

- [ ] **3.3** Append a dated entry to `reports/methodology_history.md` carrying
      both DOIs and the arXiv ID.

- [ ] **3.4** Update `STATUS.md`: the Paper 1 row still says the gate is the
      q-fin.RM endorsement. Replace that with the DOIs.

- [ ] **3.5** Delete or archive `arxiv-endorsement/`. It is dead work now.

- [ ] **3.6** Check whether moderators reclassified you. If the paper landed in
      `q-fin.RM` primary, that is a better outcome than you asked for — accept
      it and update the history entry to say so.

---

## If something goes wrong

**A gate fails at 0.1** — the bundle disagrees with the paper. Rebuild:
`.venv/bin/python build/build.py --v2 --arxiv`, then re-stage.

**arXiv's compile fails** — read its log, not yours. The clean-room check in
the playbook §2 reproduces arXiv's exact compile locally; re-run it and diff
the logs.

**Page count is not 67** — arXiv's TeX Live differs from yours. Not fatal.
Update the Comments field to the number arXiv produced rather than shipping a
count that contradicts the PDF.

**You published Zenodo with a mistake** — you cannot delete it. Fix metadata
in place (metadata is editable), or cut v2 for a file change. The concept DOI
keeps pointing at the newest version, so a v2 is cheap and honest.
