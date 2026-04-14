"""
Integration sync service.

sync_integration(integration_id) is the main entry point, called as a
FastAPI BackgroundTask from the integrations router.

For each selected folder:
  1. List NDIS-relevant files (PDF / DOCX / TXT)
  2. Skip files already imported (dedup by external_provider + external_id)
  3. Download bytes via the connector
  4. Upload to Supabase Storage (same bucket / path scheme as manual uploads)
  5. Insert a documents row with source='integration' + external_* fields
  6. Create an analysis_jobs row
  7. Invoke the existing OCR→classify→score pipeline (process_document_async)

Sync status lifecycle:
  idle → syncing → idle   (success)
  idle → syncing → error  (failure, last_error populated)
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.database import supabase_admin
from app.integrations.base import get_connector
from app.services.document_processor import process_document_async

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


async def sync_integration(integration_id: str) -> None:
    """
    Walk all selected folders for the integration and ingest any new files.

    Designed to be called as a FastAPI BackgroundTask:
        background_tasks.add_task(sync_integration, integration_id)
    """
    # Fetch integration row
    resp = (
        supabase_admin.table("integrations")
        .select("*")
        .eq("id", integration_id)
        .single()
        .execute()
    )
    if not resp.data:
        logger.error(f"sync_integration: integration {integration_id} not found")
        return

    row = resp.data
    org_id: str = row["organization_id"]
    provider: str = row["provider"]
    root_folders: list = row.get("root_folders") or []

    if not root_folders:
        logger.info(f"[Sync {integration_id}] No folders selected — skipping")
        return

    # Mark as syncing
    _update_sync_status(integration_id, "syncing")

    try:
        connector = get_connector(provider, row)

        synced = 0
        skipped = 0
        errors = 0

        for folder_id in root_folders:
            try:
                files = await connector.list_files_in_folder(folder_id)
            except Exception as exc:
                logger.error(
                    f"[Sync {integration_id}] list_files_in_folder({folder_id}) failed: {exc}",
                    exc_info=True,
                )
                errors += 1
                continue

            for file_meta in files:
                external_id: str = file_meta["id"]
                filename: str = file_meta.get("name", "document")
                file_size: int = file_meta.get("size", 0)
                web_url: str = file_meta.get("web_url", "")
                mime_type: str = file_meta.get("mime_type", "application/octet-stream")

                # Validate extension
                suffix = Path(filename).suffix.lower()
                if suffix not in ALLOWED_EXTENSIONS:
                    skipped += 1
                    continue

                # Size guard (pre-download)
                if file_size > MAX_FILE_SIZE:
                    logger.warning(
                        f"[Sync {integration_id}] Skipping {filename}: "
                        f"{file_size / 1024 / 1024:.1f} MB exceeds 50 MB limit"
                    )
                    skipped += 1
                    continue

                # Dedup: skip if already imported
                existing = (
                    supabase_admin.table("documents")
                    .select("id")
                    .eq("external_provider", provider)
                    .eq("external_id", external_id)
                    .execute()
                )
                if existing.data:
                    skipped += 1
                    continue

                # Download bytes
                try:
                    content, dl_filename, dl_mime = await connector.download_file(external_id)
                except Exception as exc:
                    logger.error(
                        f"[Sync {integration_id}] download_file({external_id}) failed: {exc}",
                        exc_info=True,
                    )
                    errors += 1
                    continue

                # Use download-time values if richer
                filename = dl_filename or filename
                mime_type = dl_mime or mime_type
                suffix = Path(filename).suffix.lower()

                if len(content) > MAX_FILE_SIZE:
                    logger.warning(f"[Sync {integration_id}] Skipping {filename}: downloaded size exceeds limit")
                    skipped += 1
                    continue

                # Generate doc ID and storage path (mirrors documents.py)
                doc_id = str(uuid.uuid4())
                storage_path = f"{org_id}/{doc_id}{suffix}"

                # Upload to Supabase Storage
                try:
                    supabase_admin.storage.from_("documents").upload(
                        path=storage_path,
                        file=content,
                        file_options={"content-type": mime_type},
                    )
                except Exception as exc:
                    logger.error(
                        f"[Sync {integration_id}] Storage upload failed for {filename}: {exc}",
                        exc_info=True,
                    )
                    errors += 1
                    continue

                # Insert document record
                try:
                    doc_resp = supabase_admin.table("documents").insert({
                        "id": doc_id,
                        "organization_id": org_id,
                        "uploaded_by": None,        # no human uploader for synced docs
                        "filename": storage_path,
                        "original_filename": filename,
                        "file_size": len(content),
                        "mime_type": mime_type,
                        "storage_path": storage_path,
                        "processing_status": "pending",
                        # Integration-specific fields
                        "source": "integration",
                        "external_provider": provider,
                        "external_id": external_id,
                        "external_url": web_url,
                        "integration_id": integration_id,
                    }).execute()

                    if not doc_resp.data:
                        raise RuntimeError("No data returned from documents insert")
                except Exception as exc:
                    logger.error(
                        f"[Sync {integration_id}] DB insert failed for {filename}: {exc}",
                        exc_info=True,
                    )
                    # Clean up storage file to avoid orphans
                    try:
                        supabase_admin.storage.from_("documents").remove([storage_path])
                    except Exception:
                        pass
                    errors += 1
                    continue

                # Create analysis job (mirrors documents.py)
                try:
                    job_resp = supabase_admin.table("analysis_jobs").insert({
                        "organization_id": org_id,
                        "document_id": doc_id,
                        "job_type": "compliance_analysis",
                        "status": "queued",
                        "progress": 0,
                    }).execute()
                    job_id = job_resp.data[0]["id"] if job_resp.data else "unknown"
                except Exception as exc:
                    logger.error(
                        f"[Sync {integration_id}] analysis_jobs insert failed: {exc}",
                        exc_info=True,
                    )
                    job_id = "unknown"

                # Trigger OCR → classify → compliance-score pipeline
                asyncio.ensure_future(
                    process_document_async(
                        doc_id=doc_id,
                        org_id=org_id,
                        job_id=job_id,
                        content=content,
                        original_filename=filename,
                        suffix=suffix,
                    )
                )

                synced += 1
                logger.info(
                    f"[Sync {integration_id}] Imported '{filename}' "
                    f"(doc_id={doc_id}, job_id={job_id})"
                )

        # Persist refreshed tokens if the connector auto-refreshed
        _maybe_persist_tokens(integration_id, row, connector.row)

        # Done — update sync metadata
        supabase_admin.table("integrations").update({
            "sync_status": "idle",
            "last_sync_at": datetime.now(timezone.utc).isoformat(),
            "last_error": None,
        }).eq("id", integration_id).execute()

        logger.info(
            f"[Sync {integration_id}] Complete — "
            f"imported={synced} skipped={skipped} errors={errors}"
        )

    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"[Sync {integration_id}] Fatal error: {error_msg}", exc_info=True)
        supabase_admin.table("integrations").update({
            "sync_status": "error",
            "last_error": error_msg,
        }).eq("id", integration_id).execute()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update_sync_status(integration_id: str, status: str) -> None:
    supabase_admin.table("integrations").update({
        "sync_status": status,
    }).eq("id", integration_id).execute()


def _maybe_persist_tokens(integration_id: str, old_row: dict, new_row: dict) -> None:
    """Write back refreshed tokens if the connector auto-refreshed them."""
    if new_row.get("access_token") and new_row.get("access_token") != old_row.get("access_token"):
        supabase_admin.table("integrations").update({
            "access_token": new_row.get("access_token"),
            "refresh_token": new_row.get("refresh_token"),
            "expires_at": new_row.get("expires_at"),
        }).eq("id", integration_id).execute()
