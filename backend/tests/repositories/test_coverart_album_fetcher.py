from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from repositories.coverart_album import AlbumCoverFetcher


def _audiodb_fetcher(audiodb_service, browse_queue=None, http_get=None):
    return AlbumCoverFetcher(
        http_get_fn=http_get or AsyncMock(),
        write_cache_fn=AsyncMock(),
        audiodb_service=audiodb_service,
        audiodb_browse_queue=browse_queue,
    )


@pytest.mark.asyncio
async def test_audiodb_cache_miss_enqueues_warm_and_returns_none():
    audiodb_service = MagicMock()
    audiodb_service.get_cached_album_images = AsyncMock(return_value=None)
    audiodb_service.fetch_and_cache_album_images = AsyncMock()
    browse_queue = MagicMock()
    browse_queue.enqueue = AsyncMock()

    fetcher = _audiodb_fetcher(audiodb_service, browse_queue)

    result = await fetcher._fetch_from_audiodb('rg-id', Path('/tmp/cover.bin'))

    assert result is None
    browse_queue.enqueue.assert_awaited_once_with('album', 'rg-id')
    audiodb_service.fetch_and_cache_album_images.assert_not_awaited()


@pytest.mark.asyncio
async def test_audiodb_negative_cache_does_not_enqueue():
    audiodb_service = MagicMock()
    audiodb_service.get_cached_album_images = AsyncMock(
        return_value=MagicMock(is_negative=True, album_thumb_url=None)
    )
    browse_queue = MagicMock()
    browse_queue.enqueue = AsyncMock()

    fetcher = _audiodb_fetcher(audiodb_service, browse_queue)

    result = await fetcher._fetch_from_audiodb('rg-id', Path('/tmp/cover.bin'))

    assert result is None
    browse_queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_audiodb_cache_hit_returns_image_without_live_lookup():
    audiodb_service = MagicMock()
    audiodb_service.get_cached_album_images = AsyncMock(
        return_value=MagicMock(
            is_negative=False,
            album_thumb_url='https://r2.theaudiodb.com/images/media/album/thumb/x.jpg',
        )
    )
    audiodb_service.fetch_and_cache_album_images = AsyncMock()
    browse_queue = MagicMock()
    browse_queue.enqueue = AsyncMock()

    response = MagicMock()
    response.status_code = 200
    response.headers = {'content-type': 'image/jpeg'}
    response.content = b'img-bytes'
    http_get = AsyncMock(return_value=response)

    fetcher = _audiodb_fetcher(audiodb_service, browse_queue, http_get=http_get)

    result = await fetcher._fetch_from_audiodb('rg-id', Path('/tmp/cover.bin'))

    assert result == (b'img-bytes', 'image/jpeg', 'audiodb')
    browse_queue.enqueue.assert_not_awaited()
    audiodb_service.fetch_and_cache_album_images.assert_not_awaited()


@pytest.mark.asyncio
async def test_release_group_uses_caa_while_cold_audiodb_warms():
    audiodb_service = MagicMock()
    audiodb_service.is_enabled.return_value = True
    audiodb_service.get_cached_album_images = AsyncMock(return_value=None)
    browse_queue = MagicMock()
    browse_queue.enqueue = AsyncMock()
    browse_queue.is_pending.return_value = True
    http_get = AsyncMock(
        return_value=MagicMock(
            status_code=200,
            content=b'caa-image',
            headers={'content-type': 'image/jpeg'},
        )
    )
    fetcher = _audiodb_fetcher(
        audiodb_service, browse_queue, http_get=http_get
    )

    result = await fetcher.fetch_release_group_cover(
        'rg-id', '500', Path('/tmp/cover.bin')
    )

    assert result == (b'caa-image', 'image/jpeg', 'cover-art-archive')
    browse_queue.enqueue.assert_awaited_once_with('album', 'rg-id')
    http_get.assert_awaited_once()


@pytest.mark.asyncio
async def test_disabled_audiodb_falls_through_without_enqueuing():
    audiodb_service = MagicMock()
    audiodb_service.is_enabled.return_value = False
    browse_queue = MagicMock()
    browse_queue.enqueue = AsyncMock()
    fetcher = _audiodb_fetcher(audiodb_service, browse_queue)

    result = await fetcher._fetch_from_audiodb('rg-id', Path('/tmp/cover.bin'))

    assert result is None
    browse_queue.enqueue.assert_not_awaited()
