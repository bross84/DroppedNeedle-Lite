"""Domain-specific repository protocol definitions.

Re-exports all protocols and associated data classes for backward compatibility
with code that previously imported from `repositories.protocols`.
"""

from repositories.protocols.coverart import CoverArtRepositoryProtocol as CoverArtRepositoryProtocol
from repositories.protocols.lastfm import LastFmRepositoryProtocol as LastFmRepositoryProtocol
from repositories.protocols.library import LibraryRepositoryProtocol as LibraryRepositoryProtocol
from repositories.protocols.listenbrainz import ListenBrainzRepositoryProtocol as ListenBrainzRepositoryProtocol
from repositories.protocols.musicbrainz import MusicBrainzRepositoryProtocol as MusicBrainzRepositoryProtocol
from repositories.protocols.navidrome import NavidromeRepositoryProtocol as NavidromeRepositoryProtocol
from repositories.protocols.wikidata import WikidataRepositoryProtocol as WikidataRepositoryProtocol
from repositories.protocols.youtube import YouTubeRepositoryProtocol as YouTubeRepositoryProtocol

from repositories.listenbrainz_models import (
    ListenBrainzArtist as ListenBrainzArtist,
    ListenBrainzFeedbackRecording as ListenBrainzFeedbackRecording,
    ListenBrainzReleaseGroup as ListenBrainzReleaseGroup,
)

__all__ = [
    "CoverArtRepositoryProtocol",
    "LastFmRepositoryProtocol",
    "LibraryRepositoryProtocol",
    "ListenBrainzRepositoryProtocol",
    "MusicBrainzRepositoryProtocol",
    "NavidromeRepositoryProtocol",
    "WikidataRepositoryProtocol",
    "YouTubeRepositoryProtocol",
    "ListenBrainzArtist",
    "ListenBrainzFeedbackRecording",
    "ListenBrainzReleaseGroup",
]
