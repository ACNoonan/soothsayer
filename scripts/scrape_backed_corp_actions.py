"""
Backed Finance xStock corporate-actions scraper — GitHub registry path.

Why this exists
---------------
yfinance's corporate-actions feed reports actions on the *underlying* equity
(SPY, AAPL, ...), not on the *Backed-issued xStock* (SPYx, AAPLx, ...). The
xStock-era window (2025-07-14 onward) is at silent-bias risk from
dividends/splits/distributions/listings/delistings handled by Backed Finance
directly, especially when Backed's distribution policy diverges from the
underlying's. data-sources.md "Grant-impact addendum" lists this as a
Tier 1 ($0) free improvement.

Why GitHub instead of backed.fi/news-updates
--------------------------------------------
Backed's public website is a Webflow SPA — every URL returns the same
"Not Found" HTML shell with content loaded via JavaScript. A static-HTML
scrape returns the cookie banner and nothing else. Probed 2026-04-26.

The authoritative free source is Backed's own GitHub token registry:

  backed-fi/cowswap-xstocks-tokenlist
    - CHANGELOG.md     human-readable change log (≈ 2.5 KB)
    - tokenlist.json   canonical xStock metadata (≈ 45 KB)
    - commit history   each commit is an add/remove/update event with the
                       affected tickers in the message body

Every xStock listing, delisting, ticker change, or metadata update produces a
commit. That commit log *is* the corp-actions tape for the xStock universe.

Sources used (priority order)
-----------------------------
  1. backed-fi/cowswap-xstocks-tokenlist     — most recent, active registry
  2. backed-fi/backed-tokens-metadata        — secondary, less active

Both are read via the public GitHub REST API (no auth required for low-volume
reads — 60 unauth req/hr is plenty for this scrape).

Limitations
-----------
- Per-share dividends and splits *of the underlying* (e.g. AAPL 4-for-1 in
  2020) usually do not appear in Backed's registry — those are passed
  through to xStock holders via the underlying's distribution mechanism, and
  yfinance already labels them on the underlying. The complementary signal
  this scraper adds is **xStock-specific events**: token launches,
  delistings, ticker renames, decimals/mint changes, distribution-policy
  changes that diverge from the underlying.

- For the most rigorous on-chain ground truth (Token-2022
  `ScaledUiAmountConfig` updates, which are the canonical signal for
  Backed-administered scaling events), see the OEV grant Month 1 work —
  blocked here until `XStock.mint` is populated for each symbol in
  src/soothsayer/universe.py.

Outputs
-------
  data/processed/backed_corp_actions.parquet   — append-safe commit tape
  data/processed/backed_scrape.log             — run log
  reports/backed_corp_actions_summary.md       — diff-vs-yfinance writeup

Usage
-----
  uv run python -u scripts/scrape_backed_corp_actions.py --probe
  uv run python -u scripts/scrape_backed_corp_actions.py --scrape
  uv run python -u scripts/scrape_backed_corp_actions.py --diff

References
----------
  Backed GitHub org:           https://github.com/backed-fi
  GitHub REST API commits:     https://docs.github.com/en/rest/commits/commits
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from soothsayer.config import DATA_PROCESSED, REPORTS
from soothsayer.universe import ALL_XSTOCKS


# Repos to scan, in order. Each is read via the GitHub commits API.
REPOS = (
    "backed-fi/cowswap-xstocks-tokenlist",
    "backed-fi/backed-tokens-metadata",
)

# Heuristics to classify commit-message intent. Mapped over the lowercased message.
ACTION_HEURISTICS: tuple[tuple[str, str], ...] = (
    ("delete", "delist"),
    ("delist", "delist"),
    ("remove", "delist"),
    ("rename", "ticker_change"),
    ("ticker change", "ticker_change"),
    ("merge", "merger"),
    ("split", "split"),
    ("dividend", "dividend"),
    ("distribution", "distribution"),
    ("update logo", "metadata_update"),
    ("update", "metadata_update"),  # last — only matches if none of the above did
    ("add ", "list"),
    ("first commit", "registry_init"),
    ("token list", "registry_init"),
)

# xStock symbols + bToken aliases. Backed historically used the b-prefix
# (bSPY, bAAPL); xStocks rebranded to x-suffix (SPYx, AAPLx). Match both.
KNOWN_TICKERS = (
    {x.symbol.upper() for x in ALL_XSTOCKS}
    | {x.underlying.upper() for x in ALL_XSTOCKS}
    | {f"B{x.underlying.upper()}" for x in ALL_XSTOCKS}
)

GITHUB_API = "https://api.github.com"
USER_AGENT = "SoothsayerResearchBot/0.1 (informational; +https://github.com/<placeholder>)"
REQUEST_TIMEOUT_S = 30
PER_PAGE = 100  # GitHub API hard cap; we paginate if needed
MAX_PAGES = 5   # ≈ 500 commits — generous ceiling for any Backed repo

OUT_PARQUET = DATA_PROCESSED / "backed_corp_actions.parquet"
LOG_PATH = DATA_PROCESSED / "backed_scrape.log"
DIFF_REPORT = REPORTS / "backed_corp_actions_summary.md"

# Symbol-extraction regex: word boundaries around a recognised ticker symbol.
# Apply against the original-case commit message so we preserve casing.
SYMBOL_RE = re.compile(r"\b(" + "|".join(sorted(KNOWN_TICKERS, key=len, reverse=True)) + r"|[A-Z]{2,6}x)\b")


def _log(msg: str) -> None:
    line = f"[{datetime.now(UTC).isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def _gh_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{GITHUB_API}{path}"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    r = requests.get(url, headers=headers, params=params or {}, timeout=REQUEST_TIMEOUT_S)
    if r.status_code == 403 and "rate limit" in r.text.lower():
        _log(f"  GitHub rate limit hit on {url}; consider waiting an hour or setting GITHUB_TOKEN env")
        sys.exit(2)
    r.raise_for_status()
    return r.json()


def _classify_action(message: str) -> str | None:
    msg = message.lower()
    for needle, label in ACTION_HEURISTICS:
        if needle in msg:
            return label
    return None


def _extract_tickers(message: str) -> list[str]:
    """Pull all recognised ticker symbols from a commit message."""
    found = sorted(set(SYMBOL_RE.findall(message)))
    # Filter out generic words that happen to look like tickers
    return [t for t in found if t.upper() in KNOWN_TICKERS or t.endswith("x")]


def _fetch_commits(repo: str) -> list[dict[str, Any]]:
    """Paginate through commits for a single repo. Returns a flat list of commit dicts."""
    out: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        batch = _gh_get(
            f"/repos/{repo}/commits", params={"per_page": PER_PAGE, "page": page}
        )
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        if len(batch) < PER_PAGE:
            break  # last page
    return out


def _normalise(repo: str, commit: dict[str, Any], detected_at: datetime) -> dict[str, Any]:
    sha = commit.get("sha", "")
    commit_data = commit.get("commit", {})
    author = commit_data.get("author", {}) or {}
    msg = commit_data.get("message", "")
    msg_first_line = msg.split("\n", 1)[0]
    tickers = _extract_tickers(msg)
    return {
        "detected_at": detected_at,
        "repo": repo,
        "commit_sha": sha,
        "commit_date": (author.get("date") or "")[:10],  # YYYY-MM-DD
        "commit_url": commit.get("html_url", ""),
        "title": msg_first_line[:300],
        "underlying": tickers[0] if tickers else None,
        "all_tickers_json": json.dumps(tickers),
        "action_type": _classify_action(msg),
        "snippet": msg[:500],
    }


def cmd_probe() -> None:
    """Hit each repo's commits endpoint, print top-5 classified events. No write."""
    _log("probe start")
    for repo in REPOS:
        _log(f"  {repo}:")
        try:
            commits = _gh_get(f"/repos/{repo}/commits", params={"per_page": 10})
        except requests.RequestException as e:
            _log(f"    ERROR: {type(e).__name__}: {e}")
            continue
        if not isinstance(commits, list):
            _log(f"    unexpected response: {type(commits).__name__}")
            continue
        detected_at = datetime.now(UTC)
        rows = [_normalise(repo, c, detected_at) for c in commits]
        for row in rows[:10]:
            tickers = json.loads(row["all_tickers_json"])
            action = row["action_type"] or "—"
            _log(
                f"    {row['commit_date']} [{action:<16}] "
                f"tickers={','.join(tickers) or '—'}  msg={row['title']}"
            )


def cmd_scrape() -> None:
    """Pull full commit history for each repo, normalize, append to tape."""
    _log("scrape start")
    detected_at = datetime.now(UTC)
    all_rows: list[dict[str, Any]] = []
    for repo in REPOS:
        try:
            commits = _fetch_commits(repo)
        except requests.RequestException as e:
            _log(f"  {repo}: ERROR {type(e).__name__}: {e}")
            continue
        _log(f"  {repo}: {len(commits)} commits fetched")
        for c in commits:
            all_rows.append(_normalise(repo, c, detected_at))
    if not all_rows:
        _log("no commits fetched; nothing to write")
        return

    new_df = pd.DataFrame(all_rows)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    if OUT_PARQUET.exists():
        existing = pd.read_parquet(OUT_PARQUET)
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["repo", "commit_sha"], keep="first")
    else:
        combined = new_df
    combined = combined.sort_values(["commit_date", "repo"]).reset_index(drop=True)
    combined.to_parquet(OUT_PARQUET, index=False)
    classified = combined[combined["action_type"].notna()]
    _log(
        f"appended {len(new_df)} commits → {OUT_PARQUET} "
        f"(total: {len(combined)}, classified: {len(classified)}, "
        f"with-tickers: {combined['underlying'].notna().sum()})"
    )


def cmd_diff() -> None:
    """Summarise the Backed corp-actions tape for cross-reference against yfinance.

    Output: reports/backed_corp_actions_summary.md
      - All action-classified commits chronologically
      - Per-ticker × action-type matrix
      - Explicit "next step" instruction for the panel-rebuild integration
    """
    if not OUT_PARQUET.exists():
        _log(f"missing {OUT_PARQUET}; run --scrape first")
        sys.exit(1)

    backed = pd.read_parquet(OUT_PARQUET)
    actions = backed[backed["action_type"].notna()].copy()

    REPORTS.mkdir(parents=True, exist_ok=True)
    with DIFF_REPORT.open("w") as f:
        f.write("# Backed Finance corp-actions — registry-derived summary\n\n")
        f.write(f"Source repos: " + ", ".join(f"`{r}`" for r in REPOS) + "\n\n")
        f.write(
            f"Tape contents: **{len(backed)}** commits total across all source repos, "
            f"**{len(actions)}** classified as corp-action-equivalent events "
            f"(list / delist / ticker_change / split / dividend / merger / metadata_update / registry_init).\n\n"
        )
        if not actions.empty:
            f.write("## Commits classified by action type\n\n")
            counts = actions["action_type"].value_counts().to_frame("n_commits")
            f.write(counts.to_markdown() + "\n\n")

            f.write("## Commits with extracted xStock tickers\n\n")
            with_tickers = actions[actions["underlying"].notna()].copy()
            if not with_tickers.empty:
                pivot = (
                    with_tickers.groupby(["underlying", "action_type"])
                    .size()
                    .reset_index(name="n_commits")
                    .sort_values(["underlying", "action_type"])
                )
                f.write(pivot.to_markdown(index=False) + "\n\n")
            else:
                f.write("_(no commits with extracted ticker matches)_\n\n")

            f.write("## Chronological timeline\n\n")
            for _, row in actions.sort_values("commit_date").iterrows():
                tickers = json.loads(row.get("all_tickers_json") or "[]")
                f.write(
                    f"- **{row['commit_date']}** "
                    f"[`{row['action_type']}`] "
                    f"(tickers: {', '.join(tickers) or '—'}) "
                    f"— [{row['title']}]({row['commit_url']})\n"
                )

        f.write(
            "\n\n## Next step\n\n"
            "Cross-reference the timeline above against yfinance's `dividends` and "
            "`splits` for the matched underlying tickers over the same date range. "
            "Each `list` / `delist` / `ticker_change` / `metadata_update` event in "
            "this list is a candidate xStock-specific bias entry that yfinance does "
            "**not** capture. Re-run the v1b panel build with the merged events and "
            "report Δcoverage in §6 / §9 of Paper 1.\n\n"
            "On-chain Token-2022 `ScaledUiAmountConfig` cross-validation belongs to "
            "OEV grant Month 1 work and is gated on populating `XStock.mint` in "
            "`src/soothsayer/universe.py`.\n"
        )
    _log(f"wrote diff report → {DIFF_REPORT} ({len(actions)} action-classified commits)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--probe", action="store_true", help="hit each GitHub repo, print top commits")
    g.add_argument("--scrape", action="store_true", help="full pull, append to tape")
    g.add_argument("--diff", action="store_true", help="summarise tape for vs-yfinance comparison")
    args = parser.parse_args()

    if args.probe:
        cmd_probe()
    elif args.scrape:
        cmd_scrape()
    elif args.diff:
        cmd_diff()


if __name__ == "__main__":
    main()
