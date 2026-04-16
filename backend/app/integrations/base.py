"""
Connector abstraction for external storage providers.

Every provider (Microsoft Graph, Google Drive, Dropbox, Box, ...) implements
`BaseConnector`. The router and sync service only talk to this interface so
adding a new provider is mostly boilerplate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------
@dataclass
class TokenBundle:
    """OAuth token material returned from exchange_code / refresh."""
    access_token: str
    refresh_token: Optional[str]
    expires_at: datetime
    scope: Optional[str] = None
    account_email: Optional[str] = None
    account_name: Optional[str] = None


@dataclass
class FolderInfo:
    """A folder in the provider's file tree."""
    id: str
    name: str
    path: str
    parent_id: Optional[str] = None
    has_children: bool = True
    web_url: Optional[str] = None


@dataclass
class FileInfo:
    """A file listing entry (metadata only, no content)."""
    id: str
    name: str
    path: str
    mime_type: Optional[str]
    size: Optional[int]
    modified_at: Optional[datetime]
    web_url: Optional[str]
    folder_id: Optional[str] = None


@dataclass
class FileContent:
    """A downloaded file's bytes and headers."""
    filename: str
    content: bytes
    mime_type: str
    size: int


# ---------------------------------------------------------------------------
# BaseConnector
# ---------------------------------------------------------------------------
class BaseConnector(ABC):
    """
    Abstract base class for provider connectors.

    Implementations hold an optional `integration_row` (the row from the
    `integrations` table). When constructing for a pre-connect OAuth flow
    (authorize URL / exchange code) `integration_row` can be None.
    """

    provider: str = "base"

    def __init__(self, integration_row: Optional[dict] = None):
        self.integration_row = integration_row or {}

    # ---- OAuth ------------------------------------------------------------
    @abstractmethod
    def get_authorize_url(self, state: str) -> str:
        """Return the provider's OAuth consent URL, with state param embedded."""

    @abstractmethod
    async def exchange_code(self, code: str) -> TokenBundle:
        """Exchange an authorization code for access/refresh tokens."""

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> TokenBundle:
        """Swap a refresh token for a new access token."""

    # ---- Browsing ---------------------------------------------------------
    @abstractmethod
    async def list_folders(self, parent_id: Optional[str] = None) -> List[FolderInfo]:
        """List immediate child folders. parent_id=None → root."""

    @abstractmethod
    async def list_files_in_folder(
        self,
        folder_id: str,
        since: Optional[datetime] = None,
        recursive: bool = True,
    ) -> List[FileInfo]:
        """List files inside a folder. If recursive, descend into subfolders."""

    # ---- Content ----------------------------------------------------------
    @abstractmethod
    async def download_file(self, file_id: str) -> FileContent:
        """Fetch the full bytes of a file."""

    @abstractmethod
    async def get_file_metadata(self, file_id: str) -> FileInfo:
        """Get metadata for a single file without downloading it."""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_connector(provider: str, integration_row: Optional[dict] = None) -> BaseConnector:
    """
    Return an instantiated connector for the given provider.

    Raises ValueError if the provider isn't implemented yet.
    """
    provider = (provider or "").lower()

    if provider == "microsoft":
        # Local import avoids a circular dependency via httpx at module load time
        from app.integrations.microsoft import MicrosoftGraphConnector
        return MicrosoftGraphConnector(integration_row=integration_row)

    raise ValueError(
        f"Provider '{provider}' is not yet supported. "
        f"Implemented providers: microsoft"
    )
