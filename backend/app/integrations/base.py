"""
Base connector abstraction for cloud-storage integrations.

Add a new provider by:
  1. Subclass BaseConnector and implement all abstract methods.
  2. Register the provider name in get_connector().
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """
    Provider-agnostic interface for cloud-storage integrations.

    Every connector receives the full integrations DB row on construction so it
    can self-refresh tokens without an extra round-trip.
    """

    def __init__(self, row: Dict[str, Any]) -> None:
        """
        Args:
            row: Full row from the ``integrations`` table, including
                 access_token, refresh_token, expires_at, etc.
        """
        self.row = row

    # ------------------------------------------------------------------
    # OAuth lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_authorize_url(self, state: str) -> str:
        """
        Build the provider's OAuth authorisation URL.

        Args:
            state: Signed state token to embed in the redirect URL.

        Returns:
            Full URL to redirect the user's browser to.
        """

    @abstractmethod
    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """
        Exchange an authorisation code for tokens.

        Returns a dict with at least:
          - access_token (str)
          - refresh_token (str)
          - expires_at (str ISO-8601)
          - account_email (str)
        """

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Use a refresh token to obtain a new access token.

        Returns the same shape as exchange_code().
        """

    # ------------------------------------------------------------------
    # File-system operations
    # ------------------------------------------------------------------

    @abstractmethod
    async def list_folders(self, parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List folders visible from parent_id (or root if None).

        Each item dict must contain at least:
          - id (str)      — opaque item identifier for subsequent calls
          - name (str)    — human-readable folder name
          - path (str)    — breadcrumb path, e.g. "/Documents/NDIS"
        """

    @abstractmethod
    async def list_files_in_folder(
        self,
        folder_id: str,
        since: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List files inside a folder, optionally filtered by modification date.

        Args:
            folder_id: Opaque folder identifier returned by list_folders.
            since:     ISO-8601 timestamp; if provided, return only files
                       modified after this time (best-effort — not all
                       providers support server-side filtering).

        Each item dict must contain at least:
          - id (str)
          - name (str)
          - size (int)       — bytes
          - modified (str)   — ISO-8601 last-modified timestamp
          - mime_type (str)
          - web_url (str)    — browser-accessible URL
        """

    @abstractmethod
    async def download_file(self, file_id: str) -> Tuple[bytes, str, str]:
        """
        Download the raw bytes of a file.

        Returns:
            (content_bytes, original_filename, mime_type)
        """

    @abstractmethod
    async def get_file_metadata(self, file_id: str) -> Dict[str, Any]:
        """
        Fetch metadata for a single file (same shape as list_files_in_folder items).
        """


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_connector(provider: str, row: Dict[str, Any]) -> BaseConnector:
    """
    Return an instantiated connector for *provider*.

    Args:
        provider: Lower-case provider name, e.g. ``"microsoft"``.
        row:      Full ``integrations`` DB row (may be a partial stub for
                  operations that don't need stored tokens, e.g. authorize).

    Raises:
        ValueError: If the provider is not registered.
    """
    if provider == "microsoft":
        from app.integrations.microsoft import MicrosoftConnector
        return MicrosoftConnector(row)

    # Future providers — add here:
    # if provider == "google":
    #     from app.integrations.google import GoogleConnector
    #     return GoogleConnector(row)
    # if provider == "dropbox":
    #     from app.integrations.dropbox import DropboxConnector
    #     return DropboxConnector(row)
    # if provider == "box":
    #     from app.integrations.box import BoxConnector
    #     return BoxConnector(row)

    raise ValueError(f"Unknown integration provider: '{provider}'")
