from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.routes.stream import router
from core.exceptions import ResourceNotFoundError
from core.dependencies import get_local_files_service


@pytest.fixture
def mock_local_service():
    mock = MagicMock()
    mock.head_track = AsyncMock(
        return_value={
            "Content-Type": "audio/flac",
            "Content-Length": "30000000",
            "Accept-Ranges": "bytes",
        }
    )
    return mock


@pytest.fixture
def local_client(mock_local_service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_local_files_service] = lambda: mock_local_service
    return TestClient(app)


def test_head_local_returns_200_with_headers(local_client, mock_local_service):
    response = local_client.request("HEAD", "/stream/local/42")

    assert response.status_code == 200
    assert response.headers["accept-ranges"] == "bytes"
    mock_local_service.head_track.assert_awaited_once_with("42")


def test_head_local_returns_404_when_not_found(local_client, mock_local_service):
    mock_local_service.head_track.side_effect = ResourceNotFoundError("not found")

    response = local_client.request("HEAD", "/stream/local/999")

    assert response.status_code == 404


def test_head_local_returns_403_on_permission_error(local_client, mock_local_service):
    mock_local_service.head_track.side_effect = PermissionError("outside dir")

    response = local_client.request("HEAD", "/stream/local/42")

    assert response.status_code == 403
