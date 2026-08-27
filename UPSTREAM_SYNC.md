# Upstream sync ledger

This fork will always be behind [upstream](https://github.com/DroppedNeedle/DroppedNeedle) by a
growing number — cherry-picking a fix doesn't erase upstream's original commit from the count,
and upstream ships fast. See [FORK.md](FORK.md) for why "ahead" never reaches zero either. This
file exists so that number doesn't matter: it's the durable list of what's actually been looked
at, so a sync is always "review the new stuff since last time," never "start over."

## How to run a sync

1. `git fetch upstream`
2. `git log --oneline <last-triaged-hash>..upstream/main` — only the commits below "Last triaged
   through" need a look; everything above it is already recorded here.
3. For each new commit, check whether it touches anything in [FORK.md](FORK.md)'s removed list
   (Plugins, Connect Apps/Jellyfin server, Jellyfin, Plex, background upgrade scan, follow
   auto-download's approval system, Lidarr Import) — if it only touches those, it's **not
   applicable**, note it and move on. Otherwise it's a porting candidate.
4. Append it to the right section below with hash, one-line summary, and verdict.
5. Move the "Last triaged through" line to the newest hash you reviewed.
6. When you actually port something, check its box and note the PR.

**Cherry-picking**: use `git cherry-pick -x <hash>` (not plain `cherry-pick`) — the `-x` appends
`(cherry picked from commit <hash>)` to the new commit's message, which is the only reliable way
to tell "already ported" from "not yet," since the ahead/behind counts never will. Watch for
cross-commit test coupling: a commit's *test file* diff sometimes carries coverage for a
different, nearby upstream commit that hasn't landed here — if a newly-ported test references
something that doesn't exist in this fork yet, trace it to its real source commit before deciding
whether to implement that too or drop the test with a note (see PR #27 for the pattern).

**Last triaged through**: `814dbf45` (upstream, 2026-08-26) — 107 commits reviewed in one pass,
see the [full audit](https://claude.ai/code/artifact/68f0e4e0-9d0d-410d-8b94-b8a04c65aec7) for
the original reasoning behind every verdict below.

**Ported so far**: 4 commits, [PR #27](https://github.com/bross84/DroppedNeedle-Lite/pull/27).

---

## Needs a decision, not a routine port

- [ ] `05f478c7` — New `D-EDITION-AUTO` feature: lets Library Management auto-accept a release
  edition match with no human review, when confidence is very high. Off by default, ships with
  undo. Still a real product call (auto-accepting catalog changes), not a fix — decide before
  porting.
- [ ] `32d618f4` — Upstream deleted its entire legacy (non-"target") scanner and finished
  consolidating on the target-only runtime. This fork still has that legacy stack. Same direction
  as this fork's own Navidrome pivot, further along — worth treating as a model for finishing
  that work here, on its own timeline, not a cherry-pick.

## Scan engine & indexing reliability

- [x] `a4aa4ad4` — Replace blocked outbound User-Agent (`DroppedNeedle/1.0` → `DroppedNeedleApp/{version}`) — **ported, PR #27**
- [ ] `246da3fd` — Expand queued-only scan requests
- [ ] `15e8063f` — Put scan supervisor under worker watchdog
- [ ] `13bc7943` — Prevent detached walkers from holding read leases
- [ ] `d0f6968d` — Bound root probes with daemon workers
- [ ] `2efbaa5a` — Terminalize stopping runs across policy changes
- [ ] `bf04e8bf` — Forget revisions for failed discovery runs
- [ ] `0ae426e6` — Log worker failures before control settlement
- [ ] `0687da5b` — Restore indexing resume guard
- [ ] `5ef5265a` — Queue follow-ups instead of coalescing into active runs
- [ ] `c96fb104` — Use fresh wall-clock for discovery failure terminals
- [ ] `abf7c245` — Normalize overlapping queued scan scopes
- [ ] `42856ba2` — Stamp catalog timestamps from scan time, not file mtime
- [ ] `652e24b2` — Stop labeling control exits as permission failures
- [ ] `a9192675` — Make missing-file removal idempotent (test coverage for this already stripped out of PR #27 — see its notes)
- [ ] `4a3bc60e` — Apply frozen policy scopes on policy reconcile
- [ ] `02e0fe1b` — Preserve tag-read failure detail in scan diagnostics
- [ ] `81cc9970` — Skip unavailable root scopes and reconcile removal
- [ ] `ffc71101` — Walk resilience + honest partial reads (13 coded fixes)
- [ ] `a63c8bd8` — Scan trigger/scheduling hardening (5 coded fixes)
- [ ] `a48b1313` — Test only: hostile filesystem and resume behavior
- [ ] `d4fbcc5e` — Test only: scan-performance comparison benchmark

## Identification & matching

- [x] `6708e076` — Pace open breakers with durable retry deadlines — **ported, PR #27** (pulled in as a prerequisite for the batching fix below)
- [ ] `ead52008` — Accept nullable MusicBrainz contribution fields
- [ ] `45e4ffd5` — Enforce provider proof before artist retirement
- [ ] `58ed7321` — Classify unmappable provider payloads honestly
- [ ] `7b2cbd4b` — Durably defer transient reidentification attempts (adds `NativeLibraryStore.defer_reidentification_work()` — a couple of orphaned tests for this were dropped from PR #27, port them together)
- [ ] `c581095e` — Make the backoff cap match the retry policy
- [ ] `4bee778b` — Ignore edition suffixes when comparing album titles
- [ ] `20fb3eb8` — Recall fingerprint release groups before text candidates
- [ ] `baff461d` — Retry local fingerprint failures as local transients
- [ ] `35d8f518` — Keep transient release-group failures uncached
- [ ] `6ecb51df` — Disambiguate colliding staged grouping keys
- [ ] `b9419378` — Require provider identity for provider-bearing candidates (2 orphaned tests for this were dropped from PR #27, port them together)
- [ ] `379f7b67` — Keep edition suggestions inside the current release group
- [ ] `cd32d555` — Order mixed-precision edition dates explicitly
- [ ] `55c91884` — Treat signed reissue descriptors as harmless editions
- [x] `e5a5ac3f` — Classify proven ALAC as lossless, not AAC — **ported, PR #27**
- [ ] `f5e4f2be` — Accept digit-bearing artist name tokens
- [ ] `30722252` — Pass attached release to reidentification
- [ ] `312f35f2` — Identification retries + fingerprint resilience + shared edition pick (large, coded)

## Target-schema catalog layer

Adjacent to this fork's own Navidrome-pivot work (`target_native_library_service.py` etc.) —
expect real merge conflicts here, not clean applies.

- [ ] `caddc6ab` — Remove silent library stubs (touches the same home/library-hub wiring area as the Navidrome pivot)
- [ ] `01e88749` — Replace target cutoff N+1 reads with one aggregate
- [ ] `0116037d` — Test only: aggregate parity + query-count coverage (pairs with the above)
- [ ] `ac7de2fe` — Page target artist MBIDs with a keyset query
- [x] `5b2039b9` — Batch canonical target and track resolution — **ported, PR #27**
- [ ] `1eae6062` — Filter target playlist summary by id
- [ ] `ae7c73c1` — Scale browse pages with bounded projections (large)
- [ ] `16ba4742` — Report truthful mixed-format album summaries
- [ ] `8f2beacc` — Provide enrichment candidates and library MBID membership
- [ ] `3c4d1231` — Prune terminal identification history within bounds
- [ ] `c70baa66` — Normalize target cutoff artist metadata

## Downloads, imports & acquisition

- [ ] `f9f9256b` — Consume redundant held sources on validated no-op imports
- [ ] `86394936` — Import unmapped bonus files unmanaged
- [ ] `969706da` — Fulfil drop requests only on complete coverage
- [ ] `afa6111d` — Page retrying-history with batched task reads
- [ ] `ec5a21d3` — Wanted sweep shares one normalized membership snapshot
- [ ] `3fa9b346` — Trust clean delivery, stateful retries, reconcile orphan complete-dir folders (slskd)
- [ ] `f05f0574` — Bound outage enrolment work (Wanted watcher)

## Library Management (writer, publisher, recovery, editions)

- [ ] `d76aa1ab` — Recycle-bin fail-closed + writer guards (was silently hard-deleting on no resolvable bin)
- [ ] `b1e41cf6` — Recovery journal integrity
- [ ] `2da3293a` — Publish-cleanup durability + fairness
- [ ] `ab15ec27` — Apply-worker failure semantics + lease hygiene
- [ ] `4fa10c35` — Preview-seal planning fixes
- [ ] `2bf47c94` — Reuse local inspections per management pass
- [ ] `1b202849` — Offload file-state probes in ReplayGain analysis

## Startup migration & data safety

The container's boot-time `automatic_upgrade.py` system — real data-safety fixes live here.

- [ ] `af25e793` — Bound legacy path filesystem probes
- [ ] `e14ebb3e` — Key pending migration runs on pending input revision
- [ ] `8c8f0d90` — Project pending legacy paths through verified remap
- [ ] `e103cd28` — Test only: pending-gate pre-characterization
- [ ] `351f698b` — Pending-gate captured policy revision check
- [ ] `d0ea96f1` — Promote-gate `quick_check` and WAL/SHM quarantine-not-delete
- [ ] `1ff14d85` — Evidence completeness on migration failure
- [ ] `7b4108e1` — Reconciler progress observability
- [ ] `cead25a6` — Ops documentation at code sites
- [ ] `a15298ee` — Bound startup identity backfills and WAL checkpoint pressure (large — new subsystem, review on its own)

## MusicBrainz, ListenBrainz & external APIs

- [ ] `2020b79b` — Harden MusicBrainz outages, restore artist pages (stale-cache fallback + real pagination fix — attempted, hit a cascading conflict in `artist_identity_reconciliation_service.py`, paused rather than guess at unfamiliar logic)
- [ ] `814dbf45` — Harden ListenBrainz rate limiting (measured the real limit is 30 req/10s; matches the 429s seen live this session — not yet attempted beyond its prerequisite `6708e076`, above)
- [ ] `42e0c7cc` — Classify degraded empty precache results

## Performance passes

- [ ] `f0ff088e` — Foundation perf pass (retry logic, MB/AudioDB/Discogs/Last.fm/ListenBrainz repos, cache service, new Settings → Diagnostics screen)
- [ ] `7a5772fc` — Quick-win caching pass
- [ ] `5bc2756c` — Frontend quick wins
- [ ] `c8cf04af` — Frontend structural pass
- [ ] `8a31be02` — Backend hygiene ladder
- [ ] `41b6dc82` — Structural backend perf (scoped cache invalidation)
- [ ] `d2b6396d` — MusicBrainz localization, phase 1
- [ ] `8ceabfcb` — MusicBrainz localization, phase 2
- [ ] `41f49154` — Localization hotfix
- [ ] `867a722a` — Campaign follow-ups

## Frontend, settings & cleanup

- [ ] `e79a3fd4` — Scroll collapsed sidebar rail
- [ ] `60750aa8` — Persist Spotify playlist covers safely
- [ ] `ed8f0244` — Configurable Spotify redirect origin
- [ ] `0f972702` — Key HTTP clients by effective construction settings
- [ ] `c26ac0e7` — Throttle sidecar touches on warm cache hits
- [ ] `e070d03a` — Compare only editable HTTP fields on save (needs `0f972702` landed first)
- [ ] `8fac084c` — Persistence-store schema hygiene (the `follow_store.py` portion assumes a table this fork already removed with the follow-approval system — needs manual reconciliation, rest is clean)
- [ ] `df81a362` — Tighten comments and user-facing copy

## Not applicable / can't stand alone

Not tracked as to-do items — recorded so nobody re-triages them by accident.

- `1bbf7a6d` — Targets the removed inbound OpenSubsonic server shim, not this fork's kept outbound Navidrome client.
- `7fba3f1d` — Test only; assumes a production cutover this fork doesn't have.
- `483740ce` — Test only; assumes the "legacy" library router is gone, but this fork still has and uses it.
- `854f80f6` — Nothing to re-export until `a15298ee` (above) lands.
- `fb5c819d` — Test only, companion to `81cc9970` (already listed above) — fine to bring along whenever that one is ported.
- `f45e7eb0` — Test-fixture repair only, no production change — fine to bring along whenever convenient.
