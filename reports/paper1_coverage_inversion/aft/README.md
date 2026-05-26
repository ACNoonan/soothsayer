# AFT 2026 condensed main-text sections

Condensed versions of the heaviest sections, carved for the **20-page LIPIcs main
text** (plan: [`reports/active/aft_carve_plan.md`](../../active/aft_carve_plan.md)).
The full versions remain in the parent directory and are the **appendix / arXiv
"full version"** content. The eventual `build.py --aft` mode will compose the
main text from these condensed files (where present) + the keep-as-is sections,
feeding the Dagstuhl LIPIcs template.

Drafted (venue-independent, reusable for any conference carve):
- `02_related_work.md` — 28-ref survey → categorical-claim + 4-bucket summary (full survey → Appendix F)
- `06_results.md` — 20 subsections → 6 headline ones + the two key tables (diagnostics → Appendix B)
- `09_limitations.md` — 11 disclosures → 4 load-bearing (rest → Appendix E)

Not yet carved (light compression or keep-as-is; do once venue/format confirmed):
§1 intro (keep, tight), §3 problem statement (keep), §4 methodology (keep core),
§5 data (compress switchboard tables → appendix), §7 ablation (3 components + §7.6),
§8 serving (§8.1 + §8.5 + §8.7 slice; crate/wire → appendix), §10/§11.

Gated on AFT go-ahead: LIPIcs template, anonymization, `--aft` build wiring.
