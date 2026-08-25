# Retired — soothsayer launchd plists

Nothing in this directory is deployed. Soothsayer never had an
automated deploy step: each plist was installed by hand with
`cp <plist> ~/Library/LaunchAgents/` and `launchctl load -w`, as the
comment block inside each file describes. So there is no glob and no
sync command that can re-arm these — bringing one back is a manual,
deliberate act.

## Shutdown — 2026-08-17

Soothsayer and scryer were wound down together. Every soothsayer job
was booted out of launchd, and every plist was removed from
`~/Library/LaunchAgents/`. Nothing runs on a timer any more.

| Retired plist | Was it loaded at shutdown? |
|---|---|
| `com.adamnoonan.soothsayer.band-commit.plist` | Yes |
| `com.adamnoonan.soothsayer.band-preopen.plist` | Yes |
| `com.adamnoonan.soothsayer.forward-tape.plist` | Yes |
| `com.soothsayer.lending-publisher.plist` | No — never installed. Previously sat alone in `ops/launchd/`; consolidated here so the repo has one archive instead of two plist locations. |

The first three were byte-identical to the copies in
`~/Library/LaunchAgents/`, so nothing was lost when those were removed.

## Two soothsayer jobs whose plists live in the scryer repo

Both ran soothsayer scripts but were catalogued on the scryer side,
because scryer owned the machine's schedule. Look there, not here:

- `com.soothsayer.forward-coverage` — ran `scripts/run_forward_coverage.sh`.
  Its plist had **no repo source anywhere**; it existed only in
  `~/Library/LaunchAgents/`. The sole surviving copy was rescued into
  `../../scryer/ops/launchd/retired/`.
- `com.soothsayer.kamino-weekly-rollup` — ran
  `scripts/run_kamino_weekly_rollup.sh`. Source is in
  `../../scryer/ops/launchd/cataloged/`.

## Restarting one

Copy the plist to `~/Library/LaunchAgents/`, then
`launchctl bootstrap gui/501 ~/Library/LaunchAgents/<name>.plist`.
Check the paths inside first — they point at this repo and at
`~/Library/Application Support/scryer/dataset`, and the scryer
fetchers that fed that dataset are stopped, so a restarted job reads
data frozen at shutdown.
