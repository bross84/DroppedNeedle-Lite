# About this fork

DroppedNeedle-Lite is a personal fork of
[DroppedNeedle](https://github.com/DroppedNeedle/DroppedNeedle) by
[Harvey Bragg (@HabiRabbu)](https://github.com/HabiRabbu) and its contributors.

**All credit for this application belongs to them.** Everything the app does was
designed and built upstream. This fork contributes no features — it only removes
things, to suit one person's use of it.

Forked from upstream commit `abe79f3`.

## What was removed

| Removed | Why |
|---|---|
| **Plugins** | Unsandboxed third-party Python running in-process with the server's privileges. A large trust surface to maintain for a fork that will never install one. |
| **Connect Apps** | The OpenSubsonic and Jellyfin *server* shims, which let external apps stream from DroppedNeedle. Redundant here — Navidrome already fills that role. |
| **Background upgrade scan** | An opt-in timer that re-acquired better copies on its own. Re-acquisition should be a deliberate action. |
| **Follow auto-download** | Following an artist now subscribes you to its release feed, nothing more. This also removed the per-artist admin approval system it required. |
| **Lidarr Import** | Existed to bulk-import artists as followed-with-auto-download, and was built entirely on the approval-batch machinery above. |
| **Jellyfin** | The inbound Jellyfin playback source, library browsing, and Jellyfin login/user import. Not used as a playback source here. |

Deliberately kept, despite sharing vocabulary with the above: the inbound
Navidrome and Plex playback sources; Plex login and user import; the Wanted
watcher's own "download automatically when a verified copy appears"; and the
weekly-mix auto-request grant.

## Support

- **Questions about the application** → upstream's
  [docs](https://www.droppedneedle.com/), [Discord](https://discord.gg/B5suDg7gu2)
  and [issue tracker](https://github.com/DroppedNeedle/DroppedNeedle/issues).
  Please don't raise issues there that are caused by this fork's removals.
- **Problems specific to this fork** →
  [its own issues](https://github.com/bross84/DroppedNeedle-Lite/issues).
- **Supporting development** → support the original author, via
  [Ko-fi](https://ko-fi.com/M4M41URGJO) or
  [GitHub Sponsors](https://github.com/sponsors/HabiRabbu). This fork asks for
  nothing.

## Licence

AGPL-3.0, unchanged from upstream. Copyright (c) 2025 Harvey Bragg and
contributors. See [LICENSE](LICENSE).
