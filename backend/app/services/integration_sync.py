"""
Integration sync service.

Walks the user-selected folders on a connected storage provider, downloads
files that haven't been seen before, uploads them to Supabase Storage, creates
a `documents` row for each, and kicks off the existing OCR → classify → score
pipeline. Files already synced (matched by external_id) are skipped.
"""

from __future__ import annotations

import logging
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.database import supabase_admin
from app.integrations import get_connector
from app.integrations.base import BaseConnector, FileInfo
from app.services.document_processor import process_document_async

logger = logging.getLogger(__name__)

# Extensions the existing analysis pipeline knows how to read.
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


async def sync_integration(integration_id: str) -> None:
    """
    Full sync of a single integration. Safe to call as a FastAPI BackgroundTask.

    Steps:
      1. Mark integration as 'syncing'
      2. Load its row + root_folders
      3. For each selected root folder: walk, dedup, download, insert, enqueue
      4. Mark integration 'idle' with last_sync_at set (or 'error' with last_error)
    """
    logger.info(f"[Sync {integration_id}] Starting")

    row = _load_integration(integration_id)
    if not row:
        logger.error(f"[Sync {integration_id}] Integration not found")
        return

    org_id = row["organization_id"]
    provider = row["provider"]
    last_sync_at = _parse_ts(row.get("last_sync_at"))
    selected = row.get("root_folders") or []

    # Mark syncing
    supabase_admin.table("integrations").update({
        "sync_status": "syncing",
        "last_error": None,
    }).eq("id", integration_id).execute()

    stats = {"scanned": 0, "new": 0, "skipped": 0, "errors": 0}

    try:
        connector = get_connector(provider, integration_row=row)

        if not selected:
            logger.info(f"[Sync {integration_id}] No root folders selected — nothing to sync")
        else:
            for folder in selected:
                folder_id = folder.get("id") if isinstance(folder, dict) else folder
                if not folder_id:
                    continue
                await _sync_folder(
                    connector=connector,
                    integration_id=integration_id,
                    org_id=org_id,
                    provider=provider,
                    folder_id=folder_id,
                    since=last_sync_at,
                    stats=stats,
                )

        supabase_admin.table("integrations").update({
            "sync_status": "idle",
            "last_sync_at": datetime.utcnow().isoformat(),
            "last_error": None,
        }).eq("id", integration_id).execute()

        logger.info(
            f"[Sync {integration_id}] Complete — "
            f"scanned={stats['scanned']} new={stats['new']} "
            f"skipped={stats['skipped']} errors={stats['errors']}"
        )

    except Exception as exc:
        logger.error(f"[Sync {integration_id}] Failed: {exc}", exc_info=True)
        supabase_admin.table("integrations").update({
            "sync_status": "error",
            "last_error": str(exc)[:500],
        }).eq("id", integration_id).execute()


# ---------------------------------------------------------------------------
# Per-folder walker
# ---------------------------------------------------------------------------
async def _sync_folder(
    connector: BaseConnector,
    integration_id: str,
    org_id: str,
    provider: str,
    folder_id: str,
    since: Optional[datetime],
    stats: dict,
) -> None:
    try:
        files = await connector.list_files_in_folder(folder_id, since=since, recursive=True)
    except Exception as exc:
        logger.error(f"[Sync {integration_id}] list_files failed for folder {folder_id}: {exc}")
        stats["errors"] += 1
        return

    for file_info in files:
        stats["scanned"] += 1

        try:
            if not _is_supported(file_info):
                stats["skipped"] += 1
                continue

            if _already_synced(provider, file_info.id, org_id):
                stats["skipped"] += 1
                continue

            await _ingest_file(
                connector=connector,
                integration_id=integration_id,
                org_id=org_id,
                provider=provider,
                file_info=file_info,
            )
            stats["new"] += 1

        except Exception as exc:
            logger.error(
                f"[Sync {integration_id}] Failed on file {file_info.id} ({file_info.name}): {exc}"
            )
            stats["errors"] += 1


# ---------------------------------------------------------------------------
# Single-file ingestion — reuses the existing upload/processing pipeline
# ---------------------------------------------------------------------------
async def _ingest_file(
    connector: BaseConnector,
    integration_id: str,
    org_id: str,
    provider: str,
    file_info: FileInfo,
) -> None:
    download = await connector.download_file(file_info.id)
    suffix = Path(download.filename).suffix.lower()
    doc_id = str(uuid.uuid4())
    storage_path = f"{org_id}/{doc_id}{suffix}"
    mime_type = (
        download.mime_type
        or mimetypes.guess_type(download.filename)[0]
        or "application/octet-stream"
    )

    # Upload bytes to Supabase Storage (same bucket manual uploads use)
    supabase_admin.storage.from_("documents").upload(
        path=storage_path,
        file=download.content,
        file_options={"content-type": mime_type},
    )

    # Create the documents row — tagged with the integration source
    doc_response = supabase_admin.table("documents").insert({
        "id": doc_id,
        "organization_id": org_id,
        "filename": storage_path,
        "original_filename": download.filename,
        "file_size": download.size,
        "mime_type": mime_type,
        "storage_path": storage_path,
        "processing_status": "pending",
        "source": "integration",
        "external_provider": provider,
        "external_id": file_info.id,
        "external_url": file_info.web_url,
        "integration_id": integration_id,
    }).execute()

    if not doc_response.data:
        raise RuntimeError("Failed to create document row")

    # Analysis job
    job_response = supabase_admin.table("analysis_jobs").insert({
        "organization_id": org_id,
        "document_id": doc_id,
        "job_type": "compliance_analysis",
        "status": "queued",
        "progress": 0,
    }).execute()
    job_id = job_response.data[0]["id"] if job_response.data else "unknown"

    # Run processing inline — we're already off the request thread
    await process_document_async(
        doc_id=doc_id,
        org_id=org_id,
        job_id=job_id,
        content=download.content,
        original_filename=download.filename,
        suffix=suffix,
    )


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _load_integration(integration_id: str) -> Optional[dict]:
    resp = (
        supabase_admin.table("integrations")
        .select("*")
        .eq("id", integration_id)
        .single()
        .execute()
    )
    return resp.data


def _already_synced(provider: str, external_id: str, org_id: str) -> bool:
    resp = (
        supabase_admin.table("documents")
        .select("id")
        .eq("organization_id", org_id)
        .eq("external_provider", provider)
        .eq("external_id", external_id)
        .limit(1)
        .execute()
    )
    return bool(resp.data)


def _is_supported(file_info: FileInfo) -> bool:
    suffix = Path(file_info.name or "").suffix.lower()
    return suffix in SUPPORTED_EXTENSIONS


def _parse_ts(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
