from __future__ import annotations

from typing import Any

import msgspec


class PlexOAuthPin(msgspec.Struct):
    id: int = 0
    code: str = ""
    authToken: str | None = None


class PlexAccount(msgspec.Struct):
    uuid: str = ""
    username: str = ""
    title: str = ""
    email: str | None = None
    thumb: str | None = None
    source: str = ""  # "home" | "friend"


class PlexUserProfile(msgspec.Struct):
    uuid: str = ""
    email: str | None = None
    display_name: str = "Plex User"
    thumb: str | None = None


def parse_plex_account(entry: dict[str, Any], source: str) -> PlexAccount | None:
    # The account uuid is the join key (== account.uuid from get_token_details).
    # Skip any entry without it rather than risk a wrong provider_uid.
    uuid = (entry.get("uuid") or "").strip()
    if not uuid:
        return None
    username = entry.get("username") or ""
    title = entry.get("title") or entry.get("friendlyName") or username
    email = entry.get("email") or None
    thumb = entry.get("thumb") or None
    return PlexAccount(
        uuid=uuid,
        username=username,
        title=title,
        email=email,
        thumb=thumb,
        source=source,
    )


def parse_plex_user_profile(data: dict[str, Any]) -> PlexUserProfile:
    # /api/v2/user (token details). Lenient by design: we read only the identity
    # fields we need, so extra or missing fields in Plex's response never break
    # login. The generated plex-api-client model marked many fields required and
    # rejected real responses (e.g. accounts without all attributes).
    display = (
        data.get("friendlyName")
        or data.get("username")
        or data.get("title")
        or "Plex User"
    )
    return PlexUserProfile(
        uuid=(data.get("uuid") or "").strip(),
        email=data.get("email") or None,
        display_name=display,
        thumb=data.get("thumb") or None,
    )


def parse_plex_users(payload: Any, source: str) -> list[PlexAccount]:
    # /api/v2/home/users returns {"users": [...]}; /api/v2/friends returns a bare
    # list. Handle both.
    if isinstance(payload, dict):
        items = payload.get("users") or payload.get("friends") or []
    elif isinstance(payload, list):
        items = payload
    else:
        items = []
    accounts: list[PlexAccount] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        account = parse_plex_account(item, source)
        if account is not None:
            accounts.append(account)
    return accounts
