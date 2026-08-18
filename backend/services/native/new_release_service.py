"""Follow new-release detection.

One global pass over the DISTINCT followed artists. Per artist: fetch newest
release-groups, filter to wanted types (D7 + L6), baseline-seed on first sight
(DD2), diff against the known set + the library, and record new releases into
the Wanted feed. Future-dated releases are left out of the known set so a later
poll on/after release still surfaces them (DD4).

Detection only: this fork does not auto-download on a new release. The feed and
its unseen badges are the output; acquiring anything is a user action.

A per-artist failure is logged and skipped without advancing that artist's
cursor; the run never raises.
"""

import asyncio
import logging
from datetime import date

import httpx
import msgspec

from core.exceptions import ExternalServiceError
from infrastructure.persistence.follow_store import (
    DistinctFollowedArtist,
    FollowStore,
    NewReleaseInput,
)
from infrastructure.resilience.retry import CircuitOpenError

logger = logging.getLogger(__name__)

_WANTED_PRIMARY = {"album", "ep", "single"}  # D7
_EXCLUDED_SECONDARY = {"compilation", "live", "remix", "dj-mix"}  # L6
_MB_PAGE_LIMIT = 50  # L5: newest ~50 release-groups per artist per poll
_MB_FETCH_TIMEOUT = 30.0


class PollSummary(msgspec.Struct, frozen=True):
    artists_polled: int = 0
    baselined: int = 0
    new_releases: int = 0
    errors: int = 0


class _ArtistPollResult(msgspec.Struct, frozen=True):
    baselined: bool = False
    new_releases: int = 0


def _is_wanted_type(rg: dict) -> bool:
    primary = (rg.get("primary-type") or "").lower()
    if primary not in _WANTED_PRIMARY:
        return False
    secondary = {str(s).lower() for s in (rg.get("secondary-types") or [])}
    return not (secondary & _EXCLUDED_SECONDARY)


def _parse_release_date(value: str | None) -> date | None:
    # partial MB date (YYYY / YYYY-MM) resolves to the start of its period
    if not value:
        return None
    parts = value.split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day)
    except (ValueError, IndexError):
        return None


def _is_future(rg: dict, today: date) -> bool:
    release_date = _parse_release_date(rg.get("first-release-date"))
    return release_date is not None and release_date > today


class NewReleaseService:
    def __init__(
        self,
        follow_store: FollowStore,
        mb_repo,
        library_repo,
        inter_artist_delay: float = 1.1,
    ) -> None:
        self._store = follow_store
        self._mb = mb_repo
        self._library = library_repo
        self._inter_artist_delay = inter_artist_delay

    async def run_poll(self) -> PollSummary:
        artists = await self._store.list_distinct_followed_artists()
        if not artists:
            return PollSummary()
        owned = await self._owned_release_groups()
        today = date.today()
        baselined = new_releases = errors = 0
        for index, artist in enumerate(artists):
            try:
                result = await self._process_artist(artist, owned, today)
                baselined += 1 if result.baselined else 0
                new_releases += result.new_releases
            except (
                CircuitOpenError,
                ExternalServiceError,
                httpx.HTTPError,
                asyncio.TimeoutError,
            ) as exc:
                # skip without advancing the known-set; retried next run (DD6)
                await self._store.update_cursor(
                    artist.artist_mbid_lower, "error", str(exc)
                )
                logger.warning(
                    "Follow poll: MusicBrainz unavailable for %s: %s",
                    artist.artist_mbid_lower,
                    exc,
                )
                errors += 1
            except Exception as exc:  # noqa: BLE001 - one artist must never kill the run
                logger.error(
                    "Follow poll: unexpected error for %s: %s",
                    artist.artist_mbid_lower,
                    exc,
                    exc_info=True,
                )
                errors += 1
            if index < len(artists) - 1 and self._inter_artist_delay > 0:
                await asyncio.sleep(self._inter_artist_delay)
        summary = PollSummary(
            artists_polled=len(artists),
            baselined=baselined,
            new_releases=new_releases,
            errors=errors,
        )
        logger.info("Follow poll complete: %s", summary)
        return summary

    async def _owned_release_groups(self) -> set[str]:
        try:
            owned = await self._library.get_library_mbids(include_release_ids=False)
        except Exception as exc:  # noqa: BLE001 - degrade, do not crash the run
            logger.warning("Follow poll: could not load owned release groups: %s", exc)
            return set()
        return {str(m).lower() for m in owned}

    async def _process_artist(
        self, artist: DistinctFollowedArtist, owned: set[str], today: date
    ) -> _ArtistPollResult:
        release_groups, _total = await asyncio.wait_for(
            self._mb.get_artist_release_groups_or_raise(
                artist.artist_mbid, offset=0, limit=_MB_PAGE_LIMIT
            ),
            timeout=_MB_FETCH_TIMEOUT,
        )
        candidates = [
            rg for rg in release_groups if rg.get("id") and _is_wanted_type(rg)
        ]

        if not await self._store.has_cursor(artist.artist_mbid_lower):
            # DD2 baseline: record current discography and emit nothing
            await self._store.seed_baseline(
                artist.artist_mbid_lower, [rg["id"].lower() for rg in candidates]
            )
            return _ArtistPollResult(baselined=True)

        known = await self._store.known_release_set(artist.artist_mbid_lower)
        fresh = [
            rg
            for rg in candidates
            if rg["id"].lower() not in known and rg["id"].lower() not in owned
        ]
        if not fresh:
            await self._store.update_cursor(artist.artist_mbid_lower, "ok")
            return _ArtistPollResult()

        feed_rows = [self._to_input(rg, artist) for rg in fresh]
        # future-dated releases stay OUT of the known set so a later poll
        # on/after release can still detect + enqueue them (DD4)
        known_lowers = [rg["id"].lower() for rg in fresh if not _is_future(rg, today)]
        await self._store.record_new_releases(
            artist.artist_mbid_lower, feed_rows, known_lowers
        )

        await self._store.update_cursor(artist.artist_mbid_lower, "ok")
        return _ArtistPollResult(new_releases=len(fresh))

    @staticmethod
    def _to_input(rg: dict, artist: DistinctFollowedArtist) -> NewReleaseInput:
        secondary = rg.get("secondary-types") or []
        return NewReleaseInput(
            release_group_mbid=rg["id"],
            release_group_mbid_lower=rg["id"].lower(),
            artist_mbid_lower=artist.artist_mbid_lower,
            artist_name=artist.artist_name,
            title=rg.get("title") or "",
            primary_type=rg.get("primary-type"),
            secondary_types=",".join(secondary) if secondary else None,
            first_release_date=rg.get("first-release-date"),
        )

