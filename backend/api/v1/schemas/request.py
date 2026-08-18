from typing import Annotated
import msgspec
from infrastructure.msgspec_fastapi import AppStruct


class AlbumRequest(AppStruct):
    musicbrainz_id: str
    artist: str | None = None
    album: str | None = None
    year: int | None = None
    artist_mbid: str | None = None


class RequestAcceptedResponse(AppStruct):
    success: bool
    message: str
    musicbrainz_id: str
    status: str = "pending"


class BatchAlbumItem(AppStruct):
    musicbrainz_id: str
    artist_name: str = "Unknown"
    album_title: str = "Unknown"
    year: int | None = None
    artist_mbid: str | None = None


class BatchAlbumRequest(AppStruct):
    items: Annotated[list[BatchAlbumItem], msgspec.Meta(max_length=500)]


class BatchRequestResponse(AppStruct):
    success: bool
    message: str
    requested: int = 0
    skipped: int = 0
    overflow: int = 0


class BatchCancelRequest(AppStruct):
    musicbrainz_ids: Annotated[list[str], msgspec.Meta(max_length=500)]


class BatchCancelResponse(AppStruct):
    success: bool
    cancelled: int = 0
    failed: int = 0
    message: str = ""
