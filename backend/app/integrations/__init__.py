"""
External storage integrations for Verida.

Each provider implements BaseConnector so new providers can be added without
changing the router or sync service.
"""

from app.integrations.base import (
    BaseConnector,
    FolderInfo,
    FileInfo,
    FileContent,
    TokenBundle,
    get_connector,
)

__all__ = [
    "BaseConnector",
    "FolderInfo",
    "FileInfo",
    "FileContent",
    "TokenBundle",
    "get_connector",
]
