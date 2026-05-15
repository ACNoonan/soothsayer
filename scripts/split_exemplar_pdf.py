"""One-off: split Tokenized-Stocks-Cong.pdf into per-subsection text files.

Reads the PDF with `pdftotext`, splits the output on form-feed (page boundary),
then groups pages into subsections per a hand-built TOC map. Writes one .txt
per subsection plus an INDEX.md.

Usage:
    python3 scripts/split_exemplar_pdf.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PDF = REPO / "reports/paper1_coverage_inversion/exemplars/Tokenized-Stocks-Cong.pdf"
OUT = REPO / "reports/paper1_coverage_inversion/exemplars/Tokenized-Stocks-Cong"

# Each entry: (file_id, display_label, slug, start_page).
# End page is implicit: (next entry's start_page - 1), or TOTAL_PAGES for the last.
# Subsections that share a starting page are merged into one file.
TOC: list[tuple[str, str, str, int]] = [
    ("01",         "1 Introduction",                                                 "introduction",                          3),
    ("02-1",       "2 / 2.1 What Are Tokenized Stocks?",                             "what_are_tokenized_stocks",             8),
    ("02-2",       "2.2 Backed Finance (xStocks) vs. Ondo Finance",                  "backed_xstocks_vs_ondo",               10),
    ("02-3",       "2.3 Blockchain Platforms",                                       "blockchain_platforms",                 12),
    ("03-1-2",     "3 / 3.1 Setting + 3.2 Data",                                     "setting_and_data",                     14),
    ("03-3",       "3.3 Conceptual Framework (intro)",                               "conceptual_framework",                 15),
    ("03-3-1-2",   "3.3.1 Continuous trading + 3.3.2 Fractional trading",            "continuous_and_fractional",            16),
    ("03-3-3-4",   "3.3.3 Arbitrage coupling + 3.3.4 Off-hour dynamics",             "arbitrage_and_offhour",                17),
    ("04-1",       "4 / 4.1 TSLAx Market Activity (First 3 Months)",                 "tslax_market_activity",                18),
    ("04-2",       "4.2 Transaction Size Distribution and Fractional Trading",      "transaction_size_distribution",        19),
    ("04-3",       "4.3 TSLAx DeFi Markets",                                         "tslax_defi_markets",                   20),
    ("04-4-5",     "4.4 Top Holder Analysis + 4.5 Price Comparisons",                "top_holder_and_price_comparisons",     23),
    ("04-6",       "4.6 Return Distributions by Day of Week",                        "return_distributions",                 26),
    ("04-7",       "4.7 Cross-Platform Price Differentials by Day of Week",          "cross_platform_price_diff",            27),
    ("04-8",       "4.8 Slippage Analysis: Daily Maximum Deviation",                 "slippage_analysis",                    30),
    ("04-9",       "4.9 Arbitrage Opportunities (Threshold Exceedance)",             "arbitrage_opportunities",              31),
    ("04-10",      "4.10 Global Access",                                             "global_access",                        32),
    ("05-1",       "5 / 5.1 Price Mapping to the Underlying Stock",                  "price_mapping_underlying",             33),
    ("05-2",       "5.2 Response to Value-Relevant News",                            "value_relevant_news",                  35),
    ("05-3",       "5.3 Off-Hour Price Movements",                                   "off_hour_price_movements",             37),
    ("05-4",       "5.4 Anticipation of Underlying Stock Returns",                   "anticipation_underlying_returns",      39),
    ("06-1",       "6 / 6.1 Market Efficiency and Price Discovery",                  "market_efficiency",                    41),
    ("06-2",       "6.2 Liquidity and Market Quality",                               "liquidity_market_quality",             42),
    ("06-3-4",     "6.3 Regulatory + 6.4 Issuers and Competition",                   "regulatory_and_issuers",               44),
    ("06-5",       "6.5 Future Research Directions",                                 "future_research",                      45),
    ("07",         "7 Conclusion",                                                   "conclusion",                           46),
    ("99",         "References / Appendix",                                          "references",                           47),
]

TOTAL_PAGES = 51

# The manuscript's printed page numbers (used in the TOC) differ from PDF page
# numbers because the unnumbered title page precedes the TOC. Empirically,
# manuscript page N = PDF page N + 1 for this file.
PAGE_OFFSET = 1


def extract_pages(pdf: Path) -> list[str]:
    """Return list of page texts (index 0 = page 1)."""
    result = subprocess.run(
        ["pdftotext", str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    )
    pages = result.stdout.split("\f")
    if pages and pages[-1].strip() == "":
        pages = pages[:-1]
    return pages


def main() -> None:
    pages = extract_pages(PDF)
    assert len(pages) == TOTAL_PAGES, f"expected {TOTAL_PAGES} pages, got {len(pages)}"
    OUT.mkdir(parents=True, exist_ok=True)

    index_rows: list[tuple[str, str, str, str]] = []  # (file, label, page_range, slug)

    # PDF page 1 is the unnumbered title + abstract page. Emit it as a standalone
    # file so the abstract is searchable even though it has no manuscript page
    # number in the TOC.
    abstract_body = pages[0].rstrip() + "\n"
    abstract_header = (
        f"# 0 Title page + Abstract\n"
        f"# Source pages: PDF p. 1 (unnumbered) of {PDF.name}\n\n"
    )
    (OUT / "00_abstract.txt").write_text(abstract_header + abstract_body)
    index_rows.append(("00_abstract.txt", "0 Title page + Abstract", "PDF p. 1", "abstract"))

    for i, (file_id, label, slug, start_pp) in enumerate(TOC):
        end_pp = TOC[i + 1][3] - 1 if i + 1 < len(TOC) else (TOTAL_PAGES - PAGE_OFFSET)
        pdf_start = start_pp + PAGE_OFFSET  # 1-indexed PDF page
        pdf_end = end_pp + PAGE_OFFSET
        page_texts = pages[pdf_start - 1 : pdf_end]
        body = "\n".join(page_texts).rstrip() + "\n"
        header = f"# {label}\n# Source pages: {start_pp}–{end_pp} of {PDF.name}\n\n"
        fname = f"{file_id}_{slug}.txt"
        (OUT / fname).write_text(header + body)
        page_range = f"p. {start_pp}" if start_pp == end_pp else f"pp. {start_pp}–{end_pp}"
        index_rows.append((fname, label, page_range, slug))

    index_lines = [
        "# Tokenized Stocks (Cong, Landsman, Rabetti, Zhang, Zhao — Dec 2025) — subsection index",
        "",
        f"Split from `{PDF.name}` (51 pp) by `scripts/split_exemplar_pdf.py`.",
        "Subsections that share a starting page are merged into a single file.",
        "",
        "| file | section | pages |",
        "| --- | --- | --- |",
    ]
    for fname, label, page_range, _ in index_rows:
        index_lines.append(f"| [{fname}]({fname}) | {label} | {page_range} |")
    (OUT / "INDEX.md").write_text("\n".join(index_lines) + "\n")

    print(f"Wrote {len(index_rows)} subsection files + INDEX.md to {OUT}")


if __name__ == "__main__":
    main()
