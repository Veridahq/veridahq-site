"""
Microsoft Graph connector — SharePoint / OneDrive.

Handles OAuth via login.microsoftonline.com and file operations via
graph.microsoft.com/v1.0 using the delegated-permission model.

Required env vars (set on Render / local .env):
    MICROSOFT_CLIENT_ID      — Azure AD app registration client ID
    MICROSOFT_CLIENT_SECRET  — Azure AD client secret value
    MICROSOFT_REDIRECT_URI   — Must match the redirect URI in Azure portal
                               (default: https://verida-api.onrender.com/api/integrations/microsoft/callback)
"""

from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx

from app.config import settings
from app.integrations.base import BaseConnector

logger = logging.getLogger(__name__)

_AUTHORITY = "https://login.microsoftonline.com/common/oauth2/v2.0"
_GRAPH = "https://graph.microsoft.com/v1.0"
_SCOPES = "offline_access Files.Read.All Sites.Read.All User.Read"


class MicrosoftConnector(BaseConnector):
    """
    SharePoint / OneDrive connector using Microsoft Graph API.

    File-system model
    -----------------
    Root level (parent_id=None):
        • /me/drive/root/children  — personal OneDrive root folders
        • /me/followedSites         — SharePoint sites the user follows
          Each site is exposed as a synthetic folder with id="site:{site_id}".

    Under a site (parent_id starts with "site:"):
        • /sites/{site_id}/drives  — document libraries within the site.
          Each library is exposed as a synthetic folder with id="drive:{drive_id}:root".

    Under a drive root or any item (parent_id starts with "drive:"):
        • /drives/{drive_id}/items/{item_id}/children  — real drive items.
          Items use id="drive:{drive_id}:{item_id}".

    This compound-key scheme means the front-end can pass any id back to
    list_folders / list_files_in_folder without extra context.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _access_token(self) -> str:
        """
        Return a valid access token, refreshing transparently when expired.

        Updates self.row in-place so callers can inspect the new values if
        they need to persist them (the router does this after exchange_code).
        """
        expires_at = self.row.get("expires_at")
        if expires_at:
            # Parse ISO string → aware datetime
            if isinstance(expires_at, str):
                # Supabase returns e.g. "2025-01-01T12:00:00+00:00"
                try:
                    exp_dt = datetime.fromisoformat(expires_at)
                    if exp_dt.tzinfo is None:
                        exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    exp_dt = None
            else:
                exp_dt = expires_at  # already a datetime

            now = datetime.now(timezone.utc)
            if exp_dt and now < exp_dt:
                return self.row["access_token"]

        # Token expired or unknown — refresh
        refreshed = await self.refresh_access_token(self.row.get("refresh_token", ""))
        self.row.update(refreshed)
        return self.row["access_token"]

    async def _get(self, path: str, **params) -> Any:
        """Authenticated GET against Microsoft Graph."""
        token = await self._access_token()
        url = f"{_GRAPH}{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params or None,
            )
        resp.raise_for_status()
        return resp.json()

    async def _get_bytes(self, url: str) -> bytes:
        """Download raw bytes from an arbitrary URL (follows redirects)."""
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
        resp.raise_for_status()
        return resp.content

    # ------------------------------------------------------------------
    # OAuth lifecycle
    # ------------------------------------------------------------------

    async def get_authorize_url(self, state: str) -> str:
        params = {
            "client_id": settings.microsoft_client_id,
            "response_type": "code",
            "redirect_uri": settings.microsoft_redirect_uri,
            "response_mode": "query",
            "scope": _SCOPES,
            "state": state,
            # Force account picker so multi-tenant users choose the right org
            "prompt": "select_account",
        }
        return f"{_AUTHORITY}/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_AUTHORITY}/token",
                data={
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.microsoft_redirect_uri,
                    "scope": _SCOPES,
                },
            )
        resp.raise_for_status()
        return self._parse_token_response(resp.json())

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        if not refresh_token:
            raise ValueError("No refresh token available for Microsoft connector")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_AUTHORITY}/token",
                data={
                    "client_id": settings.microsoft_client_id,
                    "client_secret": settings.microsoft_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "scope": _SCOPES,
                },
            )
        resp.raise_for_status()
        return self._parse_token_response(resp.json())

    def _parse_token_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        import time

        expires_in = int(data.get("expires_in", 3600))
        expires_at = datetime.fromtimestamp(
            time.time() + expires_in, tz=timezone.utc
        ).isoformat()

        # Fetch the user's email from the id_token claims if present
        account_email = data.get("id_token_claims", {}).get("preferred_username", "")
        if not account_email and "id_token" in data:
            # Decode without verification — we trust Microsoft's response
            try:
                import base64, json as _json
                payload = data["id_token"].split(".")[1]
                payload += "=" * (-len(payload) % 4)
                claims = _json.loads(base64.urlsafe_b64decode(payload))
                account_email = claims.get("preferred_username", "")
            except Exception:
                pass

        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", self.row.get("refresh_token", "")),
            "expires_at": expires_at,
            "account_email": account_email,
        }

    # ------------------------------------------------------------------
    # File-system operations
    # ------------------------------------------------------------------

    async def list_folders(self, parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        if parent_id is None:
            # Root: OneDrive personal root + followed SharePoint sites
            data = await self._get("/me/drive/root/children", **{"$select": "id,name,folder,webUrl", "$filter": "folder ne null"})
            for item in data.get("value", []):
                if "folder" in item:
                    results.append({
                        "id": f"drive:me:{item['id']}",
                        "name": item["name"],
                        "path": f"/{item['name']}",
                        "type": "folder",
                        "provider_type": "onedrive",
                    })

            # Followed SharePoint sites
            try:
                sites_data = await self._get("/me/followedSites", **{"$select": "id,displayName,webUrl"})
                for site in sites_data.get("value", []):
                    results.append({
                        "id": f"site:{site['id']}",
                        "name": site.get("displayName") or site.get("name", "SharePoint Site"),
                        "path": site.get("webUrl", ""),
                        "type": "site",
                        "provider_type": "sharepoint",
                    })
            except httpx.HTTPStatusError:
                # /me/followedSites may not be available in all tenants
                logger.warning("Could not list followed SharePoint sites")

        elif parent_id.startswith("site:"):
            # List document libraries (drives) for this site
            site_id = parent_id[len("site:"):]
            data = await self._get(f"/sites/{site_id}/drives", **{"$select": "id,name,webUrl"})
            for drive in data.get("value", []):
                results.append({
                    "id": f"drive:{drive['id']}:root",
                    "name": drive.get("name", "Documents"),
                    "path": drive.get("webUrl", ""),
                    "type": "drive",
                    "provider_type": "sharepoint",
                })

        elif parent_id.startswith("drive:me:"):
            # Children of a personal OneDrive folder
            item_id = parent_id[len("drive:me:"):]
            data = await self._get(
                f"/me/drive/items/{item_id}/children",
                **{"$select": "id,name,folder,webUrl", "$filter": "folder ne null"},
            )
            for item in data.get("value", []):
                if "folder" in item:
                    results.append({
                        "id": f"drive:me:{item['id']}",
                        "name": item["name"],
                        "path": f"/{item['name']}",
                        "type": "folder",
                        "provider_type": "onedrive",
                    })

        elif parent_id.startswith("drive:"):
            # Children of a SharePoint drive item
            # Format: drive:{drive_id}:{item_id}
            parts = parent_id[len("drive:"):].split(":", 1)
            drive_id = parts[0]
            item_id = parts[1] if len(parts) > 1 else "root"

            if item_id == "root":
                path = f"/drives/{drive_id}/root/children"
            else:
                path = f"/drives/{drive_id}/items/{item_id}/children"

            data = await self._get(path, **{"$select": "id,name,folder,webUrl", "$filter": "folder ne null"})
            for item in data.get("value", []):
                if "folder" in item:
                    results.append({
                        "id": f"drive:{drive_id}:{item['id']}",
                        "name": item["name"],
                        "path": item.get("webUrl", item["name"]),
                        "type": "folder",
                        "provider_type": "sharepoint",
                    })

        return results

    async def list_files_in_folder(
        self,
        folder_id: str,
        since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List downloadable files (PDF / DOCX / TXT) within a folder."""
        allowed_ext = {".pdf", ".docx", ".txt"}

        if folder_id.startswith("drive:me:"):
            item_id = folder_id[len("drive:me:"):]
            path = f"/me/drive/items/{item_id}/children"
        elif folder_id.startswith("drive:"):
            parts = folder_id[len("drive:"):].split(":", 1)
            drive_id = parts[0]
            item_id = parts[1] if len(parts) > 1 else "root"
            path = (
                f"/drives/{drive_id}/root/children"
                if item_id == "root"
                else f"/drives/{drive_id}/items/{item_id}/children"
            )
        else:
            return []

        data = await self._get(
            path,
            **{
                "$select": "id,name,file,size,lastModifiedDateTime,webUrl,@microsoft.graph.downloadUrl",
                "$filter": "file ne null",
            },
        )

        results = []
        for item in data.get("value", []):
            if "file" not in item:
                continue
            name: str = item.get("name", "")
            ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in allowed_ext:
                continue
            modified = item.get("lastModifiedDateTime", "")
            if since and modified and modified <= since:
                continue
            results.append({
                "id": item["id"],
                "name": name,
                "size": item.get("size", 0),
                "modified": modified,
                "mime_type": item.get("file", {}).get("mimeType") or mimetypes.guess_type(name)[0] or "application/octet-stream",
                "web_url": item.get("webUrl", ""),
                "download_url": item.get("@microsoft.graph.downloadUrl", ""),
            })

        return results

    async def download_file(self, file_id: str) -> Tuple[bytes, str, str]:
        """
        Download a drive item by its raw Graph item ID.

        Returns:
            (bytes, filename, mime_type)
        """
        meta = await self.get_file_metadata(file_id)
        download_url = meta.get("download_url") or meta.get("@microsoft.graph.downloadUrl")
        if not download_url:
            # Fall back to /content redirect
            token = await self._access_token()
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(
                    f"{_GRAPH}/me/drive/items/{file_id}/content",
                    headers={"Authorization": f"Bearer {token}"},
                )
            resp.raise_for_status()
            content = resp.content
        else:
            content = await self._get_bytes(download_url)

        name = meta.get("name", "document")
        mime = meta.get("mime_type") or mimetypes.guess_type(name)[0] or "application/octet-stream"
        return content, name, mime

    async def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        data = await self._get(
            f"/me/drive/items/{file_id}",
            **{"$select": "id,name,file,size,lastModifiedDateTime,webUrl,@microsoft.graph.downloadUrl"},
        )
        name = data.get("name", "")
        return {
            "id": data["id"],
            "name": name,
            "size": data.get("size", 0),
            "modified": data.get("lastModifiedDateTime", ""),
            "mime_type": data.get("file", {}).get("mimeType") or mimetypes.guess_type(name)[0] or "application/octet-stream",
            "web_url": data.get("webUrl", ""),
            "download_url": data.get("@microsoft.graph.downloadUrl", ""),
        }
