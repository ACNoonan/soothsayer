# reports/active/ — In-flight working docs

These are scratch/working docs for *active* methodology + paper workstreams. When a workstream lands, its content gets compacted into a dated entry in `reports/methodology_history.md` and the file here is deleted.

**Source of truth for what's *deployed*:** `STATUS.md` (root) and `reports/methodology_history.md` §0.

**Source of truth for what's *historical*:** `reports/methodology_history.md` §1 and the dated reports outside this folder (see `reports/INDEX.md`).

## Current contents (2026-05-04)

| File | Workstream | Status | Delete when |
|---|---|---|---|
| [`m6_refactor.md`](m6_refactor.md) | M6 LWC promotion plan (the post-`v3_bakeoff` working doc) | Phases 1–6 ✅ complete; Phase 7 (Rust parity port) gated; Phase 8 ✅ complete | M6 Rust port lands and §6/§7/§8 of Paper 1 are revised against M6 |
| [`phase_7_results.md`](phase_7_results.md) | Paper-strengthening empirical tests on M6 | ✅ Complete 2026-05-04 (portfolio clustering, sub-period robustness, GARCH-t baseline) | Findings folded into Paper 1 §6.3.1, §6.4.2, §9.2 |
| [`phase_8.md`](phase_8.md) | Compounders on Phase 7 (worst-weekend characterisation, per-symbol GARCH-t, k_w threshold stability) | ✅ Complete 2026-05-04 | Findings folded into Paper 1 §6.3.1, §6.4.1, §9.1 |
| [`validation_backlog.md`](validation_backlog.md) | Candidate workstreams beyond M5/M6 | Living. Each item terminates as Adopt / Disclose-not-deploy / Reject | Every workstream is in one of those terminal states and has a methodology log entry |

## Rules for this folder

1. **Don't put anything in `reports/active/` that isn't actively driving work.** Methodology log entries, paper sections, frozen evidence reports go in their normal homes (`reports/methodology_history.md`, `reports/paper1_coverage_inversion/`, etc.).
2. **Delete files on completion.** The last step of any workstream is to fold the result into a methodology log entry and `git rm` the working doc. The folder should shrink over time, not grow.
3. **Cross-link, don't duplicate.** If a working doc cites a finding that also lives in a paper section or methodology entry, link to that — don't re-paste.
