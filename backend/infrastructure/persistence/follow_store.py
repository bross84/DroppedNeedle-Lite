"""Per-user Follow persistence and the new-release feed built on it.

``PRAGMA foreign_keys=ON`` in ``_connect`` is what makes the
``ON DELETE CASCADE`` to ``auth_users(id)`` fire when a user is deleted.

Per DD1, follow state lives here and never as a column on ``library_artists`` /
``library_albums`` - those are wiped and rebuilt on every full library scan.
"""

import asyncio
import logging
import sqlite3
import threading
import time
from datetime import date, timedelta
from pathlib import Path

import msgspec

logger = logging.getLogger(__name__)

_LEGACY_OWNED_RELEASE_GROUPS_SQL = """
    SELECT lower(release_group_mbid) AS release_group_mbid_lower FROM library_files
    WHERE release_group_mbid IS NOT NULL AND deleted_at IS NULL
"""
_TARGET_OWNED_RELEASE_GROUPS_SQL = """
    SELECT lower(identity.release_group_mbid)
    FROM local_album_external_identities identity
    JOIN local_tracks track ON track.local_album_id = identity.local_album_id
    WHERE identity.provider = 'musicbrainz' AND track.availability = 'indexed'
"""


def _owned_release_groups_sql(conn: sqlite3.Connection) -> str:
    tables = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name IN ('library_files', 'local_album_external_identities', 'local_tracks')"
        ).fetchall()
    }
    sources: list[str] = []
    if "library_files" in tables:
        sources.append(_LEGACY_OWNED_RELEASE_GROUPS_SQL)
    if {"local_album_external_identities", "local_tracks"}.issubset(tables):
        sources.append(_TARGET_OWNED_RELEASE_GROUPS_SQL)
    return " UNION ".join(sources) or "SELECT NULL AS release_group_mbid_lower WHERE 0"


class FollowState(msgspec.Struct, frozen=True):
    followed: bool


class FollowedArtist(msgspec.Struct, frozen=True):
    artist_mbid: str
    artist_name: str
    followed_at: float


class DistinctFollowedArtist(msgspec.Struct, frozen=True):
    artist_mbid: str
    artist_mbid_lower: str
    artist_name: str


class NewRelease(msgspec.Struct, frozen=True):
    release_group_mbid: str
    artist_mbid: str
    artist_name: str
    title: str
    primary_type: str | None
    secondary_types: str | None
    first_release_date: str | None
    discovered_at: float
    # set by the recent-releases log view; the needs-requesting view leaves it
    # False by construction (owned rows are filtered out there)
    in_library: bool = False


class NewReleaseInput(msgspec.Struct, frozen=True):
    release_group_mbid: str
    release_group_mbid_lower: str
    artist_mbid_lower: str
    artist_name: str
    title: str
    primary_type: str | None = None
    secondary_types: str | None = None
    first_release_date: str | None = None


class FollowStore:
    def __init__(self, db_path: Path, write_lock: threading.Lock | None = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = write_lock or threading.Lock()
        with self._write_lock:
            self._ensure_tables()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_tables(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS user_followed_artists (
                    user_id           TEXT    NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
                    artist_mbid       TEXT    NOT NULL,
                    artist_mbid_lower TEXT    NOT NULL,
                    artist_name       TEXT    NOT NULL,
                    followed_at       REAL    NOT NULL,
                    updated_at        REAL    NOT NULL,
                    PRIMARY KEY (user_id, artist_mbid_lower)
                );
                CREATE INDEX IF NOT EXISTS idx_ufa_user ON user_followed_artists(user_id);
                CREATE INDEX IF NOT EXISTS idx_ufa_mbid ON user_followed_artists(artist_mbid_lower);

                CREATE TABLE IF NOT EXISTS new_release_feed (
                    release_group_mbid_lower TEXT    PRIMARY KEY,
                    release_group_mbid       TEXT    NOT NULL,
                    artist_mbid_lower        TEXT    NOT NULL,
                    artist_name              TEXT    NOT NULL,
                    title                    TEXT    NOT NULL,
                    primary_type             TEXT,
                    secondary_types          TEXT,
                    first_release_date       TEXT,
                    discovered_at            REAL    NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_nrf_artist ON new_release_feed(artist_mbid_lower);
                CREATE INDEX IF NOT EXISTS idx_nrf_date ON new_release_feed(first_release_date DESC);

                CREATE TABLE IF NOT EXISTS artist_release_check (
                    artist_mbid_lower TEXT PRIMARY KEY,
                    last_checked_at   REAL,
                    last_status       TEXT,
                    last_error        TEXT
                );

                CREATE TABLE IF NOT EXISTS artist_known_releases (
                    artist_mbid_lower TEXT NOT NULL,
                    rg_mbid_lower     TEXT NOT NULL,
                    PRIMARY KEY (artist_mbid_lower, rg_mbid_lower)
                );

                CREATE TABLE IF NOT EXISTS user_new_release_seen (
                    user_id TEXT PRIMARY KEY REFERENCES auth_users(id) ON DELETE CASCADE,
                    seen_at REAL NOT NULL
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _execute(self, operation, write: bool):
        if write:
            with self._write_lock:
                conn = self._connect()
                try:
                    result = operation(conn)
                    conn.commit()
                    return result
                finally:
                    conn.close()

        conn = self._connect()
        try:
            return operation(conn)
        finally:
            conn.close()

    async def _read(self, operation):
        return await asyncio.to_thread(self._execute, operation, False)

    async def _write(self, operation):
        return await asyncio.to_thread(self._execute, operation, True)

    async def follow_artist(self, user_id: str, artist_mbid: str, artist_name: str) -> None:
        # re-following preserves followed_at, only refreshing the name snapshot
        # and updated_at.
        mbid_lower = artist_mbid.lower()
        now = time.time()

        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO user_followed_artists (
                    user_id, artist_mbid, artist_mbid_lower, artist_name,
                    followed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, artist_mbid_lower) DO UPDATE SET
                    artist_name = excluded.artist_name,
                    updated_at = excluded.updated_at
                """,
                (user_id, artist_mbid, mbid_lower, artist_name, now, now),
            )

        await self._write(operation)

    async def unfollow_artist(self, user_id: str, artist_mbid: str) -> bool:
        mbid_lower = artist_mbid.lower()

        def operation(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "DELETE FROM user_followed_artists WHERE user_id = ? AND artist_mbid_lower = ?",
                (user_id, mbid_lower),
            )
            return cursor.rowcount > 0

        return await self._write(operation)

    async def get_follow_state(self, user_id: str, artist_mbid: str) -> FollowState:
        mbid_lower = artist_mbid.lower()

        def operation(conn: sqlite3.Connection) -> sqlite3.Row | None:
            return conn.execute(
                "SELECT 1 FROM user_followed_artists "
                "WHERE user_id = ? AND artist_mbid_lower = ?",
                (user_id, mbid_lower),
            ).fetchone()

        follow = await self._read(operation)
        return FollowState(followed=follow is not None)

    async def list_followed_artists(self, user_id: str) -> list[FollowedArtist]:
        def operation(conn: sqlite3.Connection) -> list[sqlite3.Row]:
            return conn.execute(
                """
                SELECT artist_mbid, artist_name, followed_at
                FROM user_followed_artists
                WHERE user_id = ?
                ORDER BY followed_at DESC
                """,
                (user_id,),
            ).fetchall()

        rows = await self._read(operation)
        return [
            FollowedArtist(
                artist_mbid=row["artist_mbid"],
                artist_name=row["artist_name"],
                followed_at=row["followed_at"],
            )
            for row in rows
        ]

    async def list_distinct_followed_artists(self) -> list[DistinctFollowedArtist]:
        def operation(conn: sqlite3.Connection) -> list[sqlite3.Row]:
            return conn.execute(
                """
                SELECT artist_mbid_lower AS artist_mbid_lower,
                       MIN(artist_mbid) AS artist_mbid,
                       MIN(artist_name) AS artist_name
                FROM user_followed_artists
                GROUP BY artist_mbid_lower
                ORDER BY artist_mbid_lower
                """
            ).fetchall()

        rows = await self._read(operation)
        return [
            DistinctFollowedArtist(
                artist_mbid=row["artist_mbid"],
                artist_mbid_lower=row["artist_mbid_lower"],
                artist_name=row["artist_name"],
            )
            for row in rows
        ]

    async def has_cursor(self, artist_mbid_lower: str) -> bool:
        def operation(conn: sqlite3.Connection) -> bool:
            return (
                conn.execute(
                    "SELECT 1 FROM artist_release_check WHERE artist_mbid_lower = ?",
                    (artist_mbid_lower,),
                ).fetchone()
                is not None
            )

        return await self._read(operation)

    async def seed_baseline(self, artist_mbid_lower: str, rg_mbids_lower: list[str]) -> None:
        # DD2 first-poll baseline. the ONLY method that creates the cursor row
        # (update_cursor only updates) so a transient error before the first
        # successful baseline never leaves an empty known-set behind a live cursor.
        now = time.time()

        def operation(conn: sqlite3.Connection) -> None:
            if rg_mbids_lower:
                conn.executemany(
                    "INSERT OR IGNORE INTO artist_known_releases (artist_mbid_lower, rg_mbid_lower) "
                    "VALUES (?, ?)",
                    [(artist_mbid_lower, rg) for rg in rg_mbids_lower],
                )
            conn.execute(
                """
                INSERT INTO artist_release_check (artist_mbid_lower, last_checked_at, last_status, last_error)
                VALUES (?, ?, 'ok', NULL)
                ON CONFLICT(artist_mbid_lower) DO UPDATE SET
                    last_checked_at = excluded.last_checked_at,
                    last_status = excluded.last_status,
                    last_error = excluded.last_error
                """,
                (artist_mbid_lower, now),
            )

        await self._write(operation)

    async def known_release_set(self, artist_mbid_lower: str) -> set[str]:
        def operation(conn: sqlite3.Connection) -> set[str]:
            rows = conn.execute(
                "SELECT rg_mbid_lower FROM artist_known_releases WHERE artist_mbid_lower = ?",
                (artist_mbid_lower,),
            ).fetchall()
            return {row["rg_mbid_lower"] for row in rows}

        return await self._read(operation)

    async def record_new_releases(
        self,
        artist_mbid_lower: str,
        feed_rows: list[NewReleaseInput],
        known_rg_lowers: list[str],
    ) -> None:
        # known_rg_lowers is a subset of feed_rows: a future-dated release is
        # added to the feed but left OUT of the known set so a later poll on/after
        # its release date can still detect and auto-enqueue it (DD4).
        # INSERT OR IGNORE on the feed PK makes overlapping poll runs idempotent.
        if not feed_rows and not known_rg_lowers:
            return
        now = time.time()

        def operation(conn: sqlite3.Connection) -> None:
            if known_rg_lowers:
                conn.executemany(
                    "INSERT OR IGNORE INTO artist_known_releases (artist_mbid_lower, rg_mbid_lower) "
                    "VALUES (?, ?)",
                    [(artist_mbid_lower, rg) for rg in known_rg_lowers],
                )
            if feed_rows:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO new_release_feed (
                        release_group_mbid_lower, release_group_mbid, artist_mbid_lower,
                        artist_name, title, primary_type, secondary_types, first_release_date, discovered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            r.release_group_mbid_lower,
                            r.release_group_mbid,
                            r.artist_mbid_lower,
                            r.artist_name,
                            r.title,
                            r.primary_type,
                            r.secondary_types,
                            r.first_release_date,
                            now,
                        )
                        for r in feed_rows
                    ],
                )

        await self._write(operation)

    async def update_cursor(
        self, artist_mbid_lower: str, status: str, error: str | None = None
    ) -> None:
        # updates an EXISTING cursor row only; does nothing if no baseline exists
        now = time.time()

        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                "UPDATE artist_release_check SET last_checked_at = ?, last_status = ?, last_error = ? "
                "WHERE artist_mbid_lower = ?",
                (now, status, error, artist_mbid_lower),
            )

        await self._write(operation)

    async def list_followers(self, artist_mbid_lower: str) -> list[str]:
        """Every user following the artist (the events watcher's SSE fan-out
        audience for concert notifications)."""

        def operation(conn: sqlite3.Connection) -> list[str]:
            rows = conn.execute(
                "SELECT user_id FROM user_followed_artists WHERE artist_mbid_lower = ?"
                " ORDER BY user_id",
                (artist_mbid_lower,),
            ).fetchall()
            return [row["user_id"] for row in rows]

        return await self._read(operation)

    async def list_new_releases_for_user(
        self, user_id: str, limit: int, offset: int
    ) -> tuple[list[NewRelease], int]:
        safe_limit = max(1, limit)
        safe_offset = max(0, offset)

        def operation(conn: sqlite3.Connection) -> tuple[list[sqlite3.Row], int]:
            owned_sql = _owned_release_groups_sql(conn)
            where = f"""
                FROM new_release_feed nrf
                JOIN user_followed_artists ufa
                    ON ufa.artist_mbid_lower = nrf.artist_mbid_lower AND ufa.user_id = ?
                WHERE nrf.release_group_mbid_lower NOT IN (
                    {owned_sql}
                )
            """
            total = conn.execute("SELECT COUNT(*) AS c " + where, (user_id,)).fetchone()["c"]
            rows = conn.execute(
                "SELECT nrf.release_group_mbid AS release_group_mbid, "
                "ufa.artist_mbid AS artist_mbid, nrf.artist_name AS artist_name, "
                "nrf.title AS title, nrf.primary_type AS primary_type, "
                "nrf.secondary_types AS secondary_types, "
                "nrf.first_release_date AS first_release_date, "
                "nrf.discovered_at AS discovered_at "
                + where
                + " ORDER BY nrf.first_release_date DESC, nrf.discovered_at DESC LIMIT ? OFFSET ?",
                (user_id, safe_limit, safe_offset),
            ).fetchall()
            return rows, total

        rows, total = await self._read(operation)
        items = [
            NewRelease(
                release_group_mbid=row["release_group_mbid"],
                artist_mbid=row["artist_mbid"],
                artist_name=row["artist_name"],
                title=row["title"],
                primary_type=row["primary_type"],
                secondary_types=row["secondary_types"],
                first_release_date=row["first_release_date"],
                discovered_at=row["discovered_at"],
            )
            for row in rows
        ]
        return items, total

    async def list_recent_releases_for_user(
        self, user_id: str, days: int, limit: int, include_owned: bool = True
    ) -> tuple[list[NewRelease], int]:
        """The LOG view: everything the user's artists released in the last
        ``days`` days, INCLUDING albums already in the library (flagged via
        ``in_library``) unless ``include_owned`` is False (the page's
        'hide owned' filter). Dateless rows fall back to their discovery time.
        Unlike list_new_releases_for_user this is a record of what happened,
        not a to-do list."""
        safe_limit = max(1, limit)
        cutoff_date = (date.today() - timedelta(days=max(1, days))).isoformat()
        cutoff_ts = time.time() - max(1, days) * 86400

        def operation(conn: sqlite3.Connection) -> tuple[list[sqlite3.Row], int]:
            owned_sql = _owned_release_groups_sql(conn)
            where = """
                FROM new_release_feed nrf
                JOIN user_followed_artists ufa
                    ON ufa.artist_mbid_lower = nrf.artist_mbid_lower AND ufa.user_id = ?
                WHERE (
                    nrf.first_release_date >= ?
                    OR (nrf.first_release_date IS NULL AND nrf.discovered_at >= ?)
                )
            """
            if not include_owned:
                where += f"""
                AND nrf.release_group_mbid_lower NOT IN (
                    {owned_sql}
                )
                """
            params = (user_id, cutoff_date, cutoff_ts)
            total = conn.execute("SELECT COUNT(*) AS c " + where, params).fetchone()["c"]
            rows = conn.execute(
                "SELECT nrf.release_group_mbid AS release_group_mbid, "
                "ufa.artist_mbid AS artist_mbid, nrf.artist_name AS artist_name, "
                "nrf.title AS title, nrf.primary_type AS primary_type, "
                "nrf.secondary_types AS secondary_types, "
                "nrf.first_release_date AS first_release_date, "
                "nrf.discovered_at AS discovered_at, "
                f"nrf.release_group_mbid_lower IN ({owned_sql}) AS in_library "
                + where
                + " ORDER BY nrf.first_release_date DESC, nrf.discovered_at DESC LIMIT ?",
                (*params, safe_limit),
            ).fetchall()
            return rows, total

        rows, total = await self._read(operation)
        items = [
            NewRelease(
                release_group_mbid=row["release_group_mbid"],
                artist_mbid=row["artist_mbid"],
                artist_name=row["artist_name"],
                title=row["title"],
                primary_type=row["primary_type"],
                secondary_types=row["secondary_types"],
                first_release_date=row["first_release_date"],
                discovered_at=row["discovered_at"],
                in_library=bool(row["in_library"]),
            )
            for row in rows
        ]
        return items, total

    async def count_unseen_new_releases_for_user(self, user_id: str) -> int:
        # same visibility filters as list_new_releases_for_user, narrowed to
        # rows discovered after the seen marker; no marker row counts everything

        def operation(conn: sqlite3.Connection) -> int:
            owned_sql = _owned_release_groups_sql(conn)
            return conn.execute(
                f"""
                SELECT COUNT(*) AS c
                FROM new_release_feed nrf
                JOIN user_followed_artists ufa
                    ON ufa.artist_mbid_lower = nrf.artist_mbid_lower AND ufa.user_id = ?
                WHERE nrf.release_group_mbid_lower NOT IN (
                    {owned_sql}
                )
                AND nrf.discovered_at > COALESCE(
                    (SELECT seen_at FROM user_new_release_seen WHERE user_id = ?), 0
                )
                """,
                (user_id, user_id),
            ).fetchone()["c"]

        return await self._read(operation)

    async def mark_new_releases_seen(self, user_id: str) -> None:
        now = time.time()

        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO user_new_release_seen (user_id, seen_at) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET seen_at = excluded.seen_at
                """,
                (user_id, now),
            )

        await self._write(operation)
