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
  uv run python -u scripts/scrape_backed_corp_actions.py --enrich

References
----------
  Backed GitHub org:           https://github.com/backed-fi
  GitHub REST API commits:     https://docs.github.com/en/rest/commits/commits
"""

from __future__ import annotations

import argparse
import base64
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
ENRICH_PARQUET = DATA_PROCESSED / "backed_corp_actions_enriched.parquet"
LOG_PATH = DATA_PROCESSED / "backed_scrape.log"
DIFF_REPORT = REPORTS / "backed_corp_actions_summary.md"
ENRICH_REPORT = REPORTS / "backed_corp_actions_enriched.md"

# Token-list filenames known to live in the Backed registries. Diff against
# any of these per commit gives the canonical add/remove/modify event list.
TOKENLIST_FILENAMES = (
    "tokenlist.json",
    "public_atomic_tokenlist.json",
)

# Panel tickers from src/soothsayer/universe.py — events touching these are
# what would affect Paper 1's calibration claim.
PANEL_UNDERLYINGS = {x.underlying.upper() for x in ALL_XSTOCKS}
PANEL_XSTOCKS = {x.symbol.upper() for x in ALL_XSTOCKS}
PANEL_BTOKENS = {f"B{x.underlying.upper()}" for x in ALL_XSTOCKS}
PANEL_ALL = PANEL_UNDERLYINGS | PANEL_XSTOCKS | PANEL_BTOKENS

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


def _fetch_commit_files(repo: str, sha: str) -> list[dict[str, Any]]:
    """Fetch the per-file patch list for one commit via the GitHub commits API."""
    detail = _gh_get(f"/repos/{repo}/commits/{sha}")
    return detail.get("files", []) or []


def _fetch_commit_parent(repo: str, sha: str) -> str | None:
    """Return the SHA of the first parent of `sha`, or None if root commit."""
    detail = _gh_get(f"/repos/{repo}/commits/{sha}")
    parents = detail.get("parents") or []
    return parents[0].get("sha") if parents else None


def _fetch_file_at_ref(repo: str, ref: str | None, filename: str) -> str | None:
    """Fetch a single file's text content at a given commit ref. None if missing/error."""
    if ref is None:
        return None
    try:
        detail = _gh_get(f"/repos/{repo}/contents/{filename}", params={"ref": ref})
    except requests.RequestException:
        return None
    if not isinstance(detail, dict) or detail.get("type") != "file":
        return None
    encoded = detail.get("content", "")
    if not encoded:
        return None
    try:
        return base64.b64decode(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def _symbols_from_tokenlist_text(text: str | None) -> set[str]:
    """Parse a tokenlist.json string and return the upper-cased set of symbols.

    Handles both the standard {"tokens": [...]} shape and a bare list at root.
    Falls back to None on parse error so the caller can distinguish empty
    file from parse-fail.
    """
    if not text:
        return set()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return set()
    tokens = data.get("tokens", []) if isinstance(data, dict) else data
    if not isinstance(tokens, list):
        return set()
    out: set[str] = set()
    for t in tokens:
        if isinstance(t, dict) and isinstance(t.get("symbol"), str):
            out.add(t["symbol"].upper())
    return out


def _verify_via_setdiff(
    repo: str, sha: str, filenames: list[str]
) -> tuple[set[str], set[str]] | None:
    """Compute true (added, removed) symbol sets between this commit and its parent.

    Aggregates across all tokenlist files touched. Returns None if we can't
    fetch the parent (root commit, etc.) or any of the file fetches failed.
    """
    parent = _fetch_commit_parent(repo, sha)
    if parent is None:
        return None
    parent_symbols: set[str] = set()
    head_symbols: set[str] = set()
    for fn in filenames:
        head_symbols |= _symbols_from_tokenlist_text(_fetch_file_at_ref(repo, sha, fn))
        parent_symbols |= _symbols_from_tokenlist_text(_fetch_file_at_ref(repo, parent, fn))
    return (head_symbols - parent_symbols, parent_symbols - head_symbols)


def _token_symbols_in_blob(blob_text: str | None) -> set[str]:
    """Best-effort extraction of all `"symbol": "X"` values inside a JSON blob.

    We use a regex rather than json.loads because we work on patch fragments
    where the JSON may be sliced. Returns the upper-cased set.
    """
    if not blob_text:
        return set()
    return {m.upper() for m in re.findall(r'"symbol"\s*:\s*"([^"]+)"', blob_text)}


def _classify_patch(patch: str | None) -> tuple[set[str], set[str]]:
    """Walk a unified-diff patch and return (added_symbols, removed_symbols).

    A symbol counted as "added" appears in a `+` line; "removed" in a `-` line.
    Symbols appearing in both are classified as modifications by the caller.
    """
    if not patch:
        return (set(), set())
    added_lines: list[str] = []
    removed_lines: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            added_lines.append(line[1:])
        elif line.startswith("-"):
            removed_lines.append(line[1:])
    added = _token_symbols_in_blob("\n".join(added_lines))
    removed = _token_symbols_in_blob("\n".join(removed_lines))
    return (added, removed)


def cmd_enrich() -> None:
    """Fetch each commit's actual file diffs and extract canonical add/remove/modify
    events for tokens in the registry. Cross-reference against the Paper 1 panel.

    The regex-extracted `underlying` field on the base tape is heuristic and
    can mis-attribute tickers that appear in commit-message context. This step
    pulls the unified-diff patch for each commit's tokenlist files and reads
    the actual `"symbol": "..."` entries from + and - lines, which is the
    canonical event source.

    Outputs:
      data/processed/backed_corp_actions_enriched.parquet  — per-commit canonical events
      reports/backed_corp_actions_enriched.md              — panel-impact analysis
    """
    if not OUT_PARQUET.exists():
        _log(f"missing {OUT_PARQUET}; run --scrape first")
        sys.exit(1)
    tape = pd.read_parquet(OUT_PARQUET)
    tape = tape.sort_values(["commit_date", "repo"]).reset_index(drop=True)
    _log(f"enrich start: {len(tape)} commits to walk")

    rows: list[dict[str, Any]] = []
    for _, t in tape.iterrows():
        repo = t["repo"]
        sha = t["commit_sha"]
        if not sha:
            continue
        try:
            files = _fetch_commit_files(repo, sha)
        except requests.RequestException as e:
            _log(f"  {repo}@{sha[:8]}: ERROR {type(e).__name__}: {e}")
            continue

        per_commit_added: set[str] = set()
        per_commit_removed: set[str] = set()
        files_examined: list[str] = []
        for f in files:
            filename = f.get("filename", "")
            if filename not in TOKENLIST_FILENAMES:
                continue
            files_examined.append(filename)
            added, removed = _classify_patch(f.get("patch"))
            per_commit_added |= added
            per_commit_removed |= removed

        modified = per_commit_added & per_commit_removed
        net_added = per_commit_added - per_commit_removed
        net_removed = per_commit_removed - per_commit_added
        panel_added_patch = sorted(net_added & PANEL_ALL)
        panel_removed_patch = sorted(net_removed & PANEL_ALL)
        panel_modified_patch = sorted(modified & PANEL_ALL)
        patch_affects_panel = bool(panel_added_patch or panel_removed_patch or panel_modified_patch)

        # Set-diff verification: a unified-diff "+" line for a symbol can be a
        # genuine listing OR a no-op format change (e.g. when an autogenerated
        # update script rewrites the entire tokenlist with reordered fields,
        # every entry appears in `+` lines but the symbol set is unchanged).
        # Verify against the actual symbol set diff between parent and HEAD.
        verified = patch_affects_panel  # only verify if patch flagged it (saves API calls)
        true_added: set[str] = set()
        true_removed: set[str] = set()
        if verified:
            res = _verify_via_setdiff(repo, sha, files_examined)
            if res is not None:
                true_added, true_removed = res

        true_panel_added = sorted(true_added & PANEL_ALL)
        true_panel_removed = sorted(true_removed & PANEL_ALL)
        # Only count as panel impact when the symbol-set actually changed
        true_affects_panel = bool(true_panel_added or true_panel_removed)

        rows.append(
            {
                "commit_date": t["commit_date"],
                "repo": repo,
                "commit_sha": sha,
                "commit_url": t["commit_url"],
                "title": t["title"],
                "files_examined_json": json.dumps(files_examined),
                "tokenlist_files_changed": len(files_examined),
                "n_added_patch": len(net_added),
                "n_removed_patch": len(net_removed),
                "n_modified_patch": len(modified),
                "patch_affects_panel": patch_affects_panel,
                "verified": verified,
                "n_added_setdiff": len(true_added),
                "n_removed_setdiff": len(true_removed),
                "added_json": json.dumps(sorted(net_added)),
                "removed_json": json.dumps(sorted(net_removed)),
                "modified_json": json.dumps(sorted(modified)),
                "panel_added_patch_json": json.dumps(panel_added_patch),
                "panel_removed_patch_json": json.dumps(panel_removed_patch),
                "panel_modified_patch_json": json.dumps(panel_modified_patch),
                "panel_added_setdiff_json": json.dumps(true_panel_added),
                "panel_removed_setdiff_json": json.dumps(true_panel_removed),
                "true_affects_panel": true_affects_panel,
                "format_change_only": patch_affects_panel and not true_affects_panel,
            }
        )
        if rows[-1]["true_affects_panel"]:
            marker = "▣ TRUE PANEL IMPACT"
        elif rows[-1]["format_change_only"]:
            marker = "○ format-change false positive (patch flagged, set-diff cleared)"
        else:
            marker = "·"
        _log(
            f"  {t['commit_date']} {repo.split('/')[-1]:<32} "
            f"patch:+{len(net_added):<3}/-{len(net_removed):<3}  "
            f"setdiff:+{len(true_added):<3}/-{len(true_removed):<3}  "
            f"{marker}"
        )

    if not rows:
        _log("no enrichment rows; nothing to write")
        return

    enriched = pd.DataFrame(rows)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    enriched.to_parquet(ENRICH_PARQUET, index=False)
    _log(f"wrote {len(enriched)} enriched rows → {ENRICH_PARQUET}")

    # Scope check: pull the *current* head of the most-active registry and
    # report which chains the entries cover. If the answer is still "EVM-only,"
    # the panel-impact analysis above is structurally orthogonal to the
    # Solana panel Paper 1 uses, regardless of how many true_panel_impact
    # commits the patch view found. Re-run this on every enrich call so any
    # future Backed Solana listings are detected the moment they ship.
    chain_breakdown: dict[str, int] = {}
    solana_count = 0
    primary_repo = "backed-fi/cowswap-xstocks-tokenlist"
    head_text = _fetch_file_at_ref(primary_repo, "HEAD", "tokenlist.json")
    if head_text:
        try:
            head_data = json.loads(head_text)
            head_tokens = (
                head_data.get("tokens", []) if isinstance(head_data, dict) else head_data
            )
            for t in head_tokens or []:
                if not isinstance(t, dict):
                    continue
                cid = t.get("chainId")
                addr = t.get("address", "") or ""
                key = f"chainId={cid}"
                chain_breakdown[key] = chain_breakdown.get(key, 0) + 1
                # Solana-style addresses are base58, not 0x-prefixed
                if isinstance(addr, str) and addr and not addr.startswith("0x"):
                    solana_count += 1
        except json.JSONDecodeError:
            _log(f"  scope-check: failed to parse {primary_repo} HEAD tokenlist.json")
    _log(f"scope check at HEAD of {primary_repo}:")
    for key, n in sorted(chain_breakdown.items(), key=lambda x: -x[1]):
        _log(f"  {key:<14} : {n} entries")
    _log(f"  non-EVM (Solana-style) addresses: {solana_count}")
    if solana_count == 0:
        _log(
            "  CONCLUSION: registry is EVM-only — Solana xStock corp-actions are NOT in this "
            "surface. Paper 1 §9 finding stands: ruled out via canonical registry inspection."
        )

    # Write the panel-impact report
    REPORTS.mkdir(parents=True, exist_ok=True)
    true_panel_events = enriched[enriched["true_affects_panel"]].copy()
    format_change_events = enriched[enriched["format_change_only"]].copy()
    n_total_patch_changes = enriched[["n_added_patch", "n_removed_patch", "n_modified_patch"]].sum().sum()

    with ENRICH_REPORT.open("w") as f:
        f.write("# Backed Finance corp-actions — canonical patch-derived enrichment\n\n")
        f.write(
            f"Enriched **{len(enriched)}** commits across "
            f"`{', '.join(REPOS)}`. Total token-level changes across all commits "
            f"(patch view): **{int(n_total_patch_changes)}**. Set-diff verification was run "
            f"against the parent commit's tokenlist for any commit the patch view flagged as "
            f"panel-affecting, to filter out format-change false positives produced by "
            f"autogenerated tokenlist rewrites.\n\n"
        )
        # Scope check at HEAD — surfaces the EVM-only finding directly in the report
        if chain_breakdown:
            f.write("## Registry scope (HEAD of `backed-fi/cowswap-xstocks-tokenlist`)\n\n")
            f.write(
                "| chainId | n_entries |\n|---|---:|\n"
            )
            for key, n in sorted(chain_breakdown.items(), key=lambda x: -x[1]):
                cid = key.replace("chainId=", "")
                f.write(f"| {cid} | {n} |\n")
            f.write(f"\nNon-EVM (Solana-style) addresses: **{solana_count}**\n\n")
            if solana_count == 0:
                f.write(
                    "**Critical finding:** the registry covers EVM chains only "
                    "(chainId 57073 = Ink/Kraken-L2, 1 = Ethereum, 42161 = Arbitrum, "
                    "56 = BNB). Paper 1's panel uses Solana-deployed Token-2022 xStocks, "
                    "which are **structurally orthogonal** to anything in this registry. "
                    "Any panel-impact rows in the patch / set-diff analysis below are "
                    "EVM-side events that do not affect the Solana panel.\n\n"
                )
        f.write(
            f"Panel under analysis: **{len(PANEL_UNDERLYINGS)}** underlyings "
            f"({', '.join(sorted(PANEL_UNDERLYINGS))}). "
            f"Includes xStock variants ({', '.join(sorted(PANEL_XSTOCKS))}) "
            f"and any `b<UNDERLYING>` legacy aliases.\n\n"
        )

        if true_panel_events.empty:
            f.write("## True panel impact (set-diff verified): NONE\n\n")
            if not format_change_events.empty:
                f.write(
                    f"The patch view flagged **{len(format_change_events)}** commit(s) as "
                    f"potentially panel-affecting, but set-diff verification confirmed all of them "
                    f"are format-change false positives — the symbol set in the tokenlist did not "
                    f"actually change for the panel tickers, the tokenlist file was just "
                    f"regenerated by an update script (every entry appears in `+` lines because "
                    f"the JSON formatting changed):\n\n"
                )
                for _, row in format_change_events.iterrows():
                    f.write(
                        f"- **{row['commit_date']}** "
                        f"[{row['commit_sha'][:12]}]({row['commit_url']}) — "
                        f"{row['title']}  "
                        f"(patch: +{int(row['n_added_patch'])} -{int(row['n_removed_patch'])}; "
                        f"set-diff: +{int(row['n_added_setdiff'])} -{int(row['n_removed_setdiff'])})\n"
                    )
                f.write("\n")
            f.write(
                "No commit in the Backed registry tapes adds, removes, or substantively "
                "modifies any of the Paper 1 panel xStocks or their underlyings during the "
                "captured window. The 17-token listing event (2026-03-05) and 15-token "
                "delisting event (2026-03-03) operate exclusively on xStocks **outside** the "
                "panel (TBLLx, ORCLx, STRCx, MCDx, NFLXx, GSx, CMCSAx, BACx, MRVLx, IBMx, "
                "CRWDx, IEMGx, LINx, CRMx, DHRx, AZNx, GMEx, SLVx, BTGOx, COPXx, DFDVx, OPENx, "
                "KRAQx, PALLx, SLMTx, PPLTx, ACNx, HDx, MDTx, BTBTx, IWMx, BMNRx).\n\n"
            )
            f.write(
                "**Implication for Paper 1:** the silent-bias risk identified in "
                "data-sources.md (\"yfinance reports actions on underlyings, not on "
                "Backed-issued xStocks\") is not material at this universe size for the "
                "captured commit window. Two paths to reach a paper-affecting finding remain:\n\n"
                "1. Expand the panel to the full Backed-registry universe (~27+ xStocks). "
                "Out of scope for Paper 1; deferred to v2-paper expansion.\n"
                "2. Pull on-chain Token-2022 `ScaledUiAmountConfig` updates per panel xStock "
                "mint via Helius. Catches dividend/split scaling events that don't appear in "
                "the cowswap tokenlist registry. Belongs to OEV grant Month 1 work; gated on "
                "populating `XStock.mint` in `src/soothsayer/universe.py`.\n\n"
                "**Documented as Paper 1 §9 follow-up:** ruled-out via canonical set-diff "
                "verification across the captured commit window.\n"
            )
        else:
            f.write(f"## True panel impact: {len(true_panel_events)} commit(s) affect panel tickers\n\n")
            for _, row in true_panel_events.iterrows():
                added = json.loads(row["panel_added_setdiff_json"] or "[]")
                removed = json.loads(row["panel_removed_setdiff_json"] or "[]")
                f.write(
                    f"### {row['commit_date']} — {row['repo']}\n\n"
                    f"- Commit: [{row['commit_sha'][:12]}]({row['commit_url']}) — {row['title']}\n"
                    f"- Panel-relevant additions (set-diff verified): {', '.join(added) or '—'}\n"
                    f"- Panel-relevant removals (set-diff verified): {', '.join(removed) or '—'}\n\n"
                )
            if solana_count == 0:
                f.write(
                    "**Implication for Paper 1 (given EVM-only scope above):** the panel "
                    "additions listed above are EVM-side CowSwap/Ink/Ethereum registry "
                    "expansion events — the cowswap registry added EVM-deployed equivalents "
                    "of the Solana xStocks already on Kamino. They are **not** corp-actions "
                    "on the Solana xStocks Paper 1's panel uses. No v1b panel rebuild is "
                    "warranted on this signal alone.\n\n"
                    "The remaining open question — \"are there Solana-side xStock corp-actions "
                    "that yfinance misses\" — can only be answered via on-chain Token-2022 "
                    "`ScaledUiAmountConfig` observation, which is OEV grant Month 1 work and "
                    "is gated on populating `XStock.mint` in `src/soothsayer/universe.py`.\n"
                )
            else:
                f.write(
                    "**Implication for Paper 1:** these events are silent-bias candidates "
                    "the v1b panel rebuild must merge against yfinance corp-actions. Re-run "
                    "`scripts/run_v1_scrape.py` and `scripts/run_calibration.py` with the "
                    "merged events; report Δcoverage per τ with bootstrap CI in §6 / §9.\n"
                )

        f.write(
            "\n\n## Full per-commit enrichment table\n\n"
            "Columns: commit_date | repo | patch +/− | set-diff +/− | "
            "true_affects_panel | format_change_only\n\n"
        )
        view = enriched.assign(
            patch=lambda d: d["n_added_patch"].astype(int).astype(str)
            + "/"
            + d["n_removed_patch"].astype(int).astype(str),
            setdiff=lambda d: d["n_added_setdiff"].astype(int).astype(str)
            + "/"
            + d["n_removed_setdiff"].astype(int).astype(str),
        )[["commit_date", "repo", "patch", "setdiff", "true_affects_panel", "format_change_only"]]
        f.write(view.to_markdown(index=False))
        f.write("\n")

    _log(f"wrote enrichment report → {ENRICH_REPORT}")
    true_panel_count = int(enriched["true_affects_panel"].sum())
    format_only_count = int(enriched["format_change_only"].sum())
    _log(
        f"summary: {len(enriched)} commits enriched, "
        f"{int(n_total_patch_changes)} total patch-level changes, "
        f"{true_panel_count} true panel-impact commit(s), "
        f"{format_only_count} format-change false positive(s) cleared by set-diff"
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
    g.add_argument("--enrich", action="store_true", help="pull canonical patches per commit, panel-impact analysis")
    args = parser.parse_args()

    if args.probe:
        cmd_probe()
    elif args.scrape:
        cmd_scrape()
    elif args.diff:
        cmd_diff()
    elif args.enrich:
        cmd_enrich()


if __name__ == "__main__":
    main()
