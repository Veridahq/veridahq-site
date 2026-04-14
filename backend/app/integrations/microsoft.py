"""
Microsoft Graph connector — SharePoint / OneDrive integration.

Uses the delegated OAuth2 flow against the /common tenant so users of any
Microsoft 365 org (or personal Microsoft accounts) can connect. Scopes are
kept minimal and read-only.

Required env vars:
    MICROSOFT_CLIENT_ID       — Azure AD app registration Application (client) ID
    MICROSOFT_CLIENT_SECRET   — client secret from the same app registration
    MICROSOFT_REDIRECT_URI    — must match the redirect URI registered in Azure
                                (defaults to https://verida-api.onrender.com/api/integrations/microsoft/callback)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlencode

import httpx

from app.integrations.base import (
    BaseConnector,
    FileContent,
    FileInfo,
    FolderInfo,
    TokenBundle,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OAuth + Graph endpoints
# ---------------------------------------------------------------------------
AUTH_BASE = "https://login.microsoftonline.com/common/oauth2/v2.0"
AUTHORIZE_URL = f"{AUTH_BASE}/authorize"
TOKEN_URL = f"{AUTH_BASE}/token"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Minimum set of delegated scopes. `offline_access` is required to get a
# refresh token. Everything else is read-only.
DEFAULT_SCOPES = "offline_access Files.Read.All Sites.Read.All User.Read"

# Files larger than this are skipped during sync (safety net — Graph lets us
# stream but the current pipeline needs the full bytes in memory).
MAX_SYNC_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


class MicrosoftGraphConnector(BaseConnector):
    provider = "microsoft"

    def __init__(self, integration_row: Optional[dict] = None):
        super().__init__(integration_row=integration_row)
        self.client_id = _env("MICROSOFT_CLIENT_ID")
        self.client_secret = _env("MICROSOFT_CLIENT_SECRET")
        self.redirect_uri = _env(
            "MICROSOFT_REDIRECT_URI",
            "https://verida-api.onrender.com/api/integrations/microsoft/callback",
        )

    # ---- OAuth --------------------------------------------------------
    def get_authorize_url(self, state: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": DEFAULT_SCOPES,
            "state": state,
            "prompt": "select_account",
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> TokenBundle:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
            "scope": DEFAULT_SCOPES,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(TOKEN_URL, data=data)
        if resp.status_code != 200:
            logger.error(f"Microsoft token exchange failed: {resp.status_code} {resp.text}")
            raise RuntimeError(f"OAuth token exchange failed: {resp.status_code}")

        payload = resp.json()
        bundle = _bundle_from_token_response(payload)

        # Fetch the user's profile so we can store which account is connected
        try:
            me = await self._graph_get("/me", access_token=bundle.access_token)
            bundle.account_email = me.get("mail") or me.get("userPrincipalName")
            bundle.account_name = me.get("displayName")
        except Exception as e:
            logger.warning(f"Couldn't fetch /me after Microsoft auth: {e}")

        return bundle

    async def refresh_access_token(self, refresh_token: str) -> TokenBundle:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": DEFAULT_SCOPES,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(TOKEN_URL, data=data)
        if resp.status_code != 200:
            logger.error(f"Microsoft token refresh failed: {resp.status_code} {resp.text}")
            raise RuntimeError("OAuth token refresh failed")
        return _bundle_from_token_response(resp.json())

    # ---- Browsing -----------------------------------------------------
    async def list_folders(self, parent_id: Optional[str] = None) -> List[FolderInfo]:
        path = f"/me/drive/items/{parent_id}/children" if parent_id else "/me/drive/root/children"
        # $filter=folder ne null keeps only folders
        items = await self._graph_get(
            path,
            params={"$top": "200"},
        )

        results: List[FolderInfo] = []
        for item in items.get("value", []):
            if "folder" not in item:
                continue
            parent_path = (item.get("parentReference") or {}).get("path", "")
            full_path = f"{parent_path}/{item.get('name', '')}" if parent_path else item.get("name", "")
            results.append(
                FolderInfo(
                    id=item["id"],
                    name=item.get("name", ""),
                    path=full_path,
                    parent_id=parent_id,
                    has_children=(item.get("folder", {}).get("childCount", 0) > 0),
                    web_url=item.get("webUrl"),
                )
            )
        return results

    async def list_files_in_folder(
        self,
        folder_id: str,
        since: Optional[datetime] = None,
        recursive: bool = True,
    ) -> List[FileInfo]:
        results: List[FileInfo] = []
        await self._walk_folder(folder_id, results, since=since, recursive=recursive)
        return results

    async def _walk_folder(
        self,
        folder_id: str,
        results: List[FileInfo],
        since: Optional[datetime],
        recursive: bool,
    ) -> None:
        next_url = f"/me/drive/items/{folder_id}/children"
        params = {"$top": "200"}
        while next_url:
            # If we have a full odata.nextLink, use it; else use the relative path
            if next_url.startswith("http"):
                page = await self._graph_get_absolute(next_url)
            else:
                page = await self._graph_get(next_url, params=params)
                params = {}  # nextLink carries its own

            for item in page.get("value", []):
                modified = _parse_graph_datetime(item.get("lastModifiedDateTime"))
                if since and modified and modified < since:
                    continue

                if "folder" in item and recursive:
                    await self._walk_folder(item["id"], results, since=since, recursive=True)
                elif "file" in item:
                    f = item.get("file") or {}
                    parent_path = (item.get("parentReference") or {}).get("path", "")
                    full_path = f"{parent_path}/{item.get('name', '')}" if parent_path else item.get("name", "")
                    results.append(
                        FileInfo(
                            id=item["id"],
                            name=item.get("name", ""),
                            path=full_path,
                            mime_type=f.get("mimeType"),
                            size=item.get("size"),
                            modified_at=modified,
                            web_url=item.get("webUrl"),
                            folder_id=folder_id,
                        )
                    )

            next_url = page.get("@odata.nextLink")

    # ---- Content ------------------------------------------------------
    async def download_file(self, file_id: str) -> FileContent:
        meta = await self.get_file_metadata(file_id)
        if meta.size and meta.size > MAX_SYNC_FILE_SIZE_BYTES:
            raise RuntimeError(
                f"File '{meta.name}' exceeds the {MAX_SYNC_FILE_SIZE_BYTES // (1024*1024)}MB sync limit"
            )

        token = await self._valid_access_token()
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(
                f"{GRAPH_BASE}/me/drive/items/{file_id}/content",
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Graph download failed for {file_id}: {resp.status_code} {resp.text[:200]}"
            )

        return FileContent(
            filename=meta.name,
            content=resp.content,
            mime_type=meta.mime_type or "application/octet-stream",
            size=len(resp.content),
        )

    async def get_file_metadata(self, file_id: str) -> FileInfo:
        item = await self._graph_get(f"/me/drive/items/{file_id}")
        f = item.get("file") or {}
        parent_path = (item.get("parentReference") or {}).get("path", "")
        full_path = f"{parent_path}/{item.get('name', '')}" if parent_path else item.get("name", "")
        return FileInfo(
            id=item["id"],
            name=item.get("name", ""),
            path=full_path,
            mime_type=f.get("mimeType"),
            size=item.get("size"),
            modified_at=_parse_graph_datetime(item.get("lastModifiedDateTime")),
            web_url=item.get("webUrl"),
        )

    # ---- Internal helpers --------------------------------------------
    async def _valid_access_token(self) -> str:
        """
        Return a usable access token, transparently refreshing if the
        integration row's token is expired.
        """
        row = self.integration_row or {}
        access_token = row.get("access_token")
        expires_at = row.get("expires_at")
        refresh_token = row.get("refresh_token")

        # Parse Supabase ISO timestamp
        needs_refresh = True
        if expires_at:
            try:
                exp = (
                    expires_at
                    if isinstance(expires_at, datetime)
                    else datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                )
                needs_refresh = exp < datetime.utcnow().replace(tzinfo=exp.tzinfo)
            except Exception:
                needs_refresh = True

        if access_token and not needs_refresh:
            return access_token

        if not refresh_token:
            raise RuntimeError("Integration has no refresh token — reconnect required")

        new_bundle = await self.refresh_access_token(refresh_token)

        # Persist the new token in the DB so future requests see it
        from app.database import supabase_admin  # local import, avoids cycles

        integration_id = row.get("id")
        if integration_id:
            supabase_admin.table("integrations").update({
                "access_token": new_bundle.access_token,
                "refresh_token": new_bundle.refresh_token or refresh_token,
                "expires_at": new_bundle.expires_at.isoformat(),
            }).eq("id", integration_id).execute()

        # Update the in-memory copy too
        self.integration_row["access_token"] = new_bundle.access_token
        self.integration_row["refresh_token"] = new_bundle.refresh_token or refresh_token
        self.integration_row["expires_at"] = new_bundle.expires_at.isoformat()

        return new_bundle.access_token

    async def _graph_get(self, path: str, params: Optional[dict] = None) -> dict:
        token = await self._valid_access_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{GRAPH_BASE}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params=params or {},
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Graph GET {path} failed: {resp.status_code} {resp.text[:200]}"
            )
        return resp.json()

    async def _graph_get_absolute(self, url: str) -> dict:
        token = await self._valid_access_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Graph GET {url} failed: {resp.status_code} {resp.text[:200]}"
            )
        return resp.json()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _bundle_from_token_response(payload: dict) -> TokenBundle:
    expires_in = int(payload.get("expires_in", 3600))
    return TokenBundle(
        access_token=payload["access_token"],
        refresh_token=payload.get("refresh_token"),
        # 60s buffer so we refresh slightly early
        expires_at=datetime.utcnow() + timedelta(seconds=expires_in - 60),
        scope=payload.get("scope"),
    )


def _parse_graph_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
