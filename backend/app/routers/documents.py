"""Document management routes."""

import logging
import uuid
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, BackgroundTasks

from app.database import supabase_admin
from app.models import (
    DocumentUploadResponse,
    DocumentResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    ProcessingStatusEnum,
)
from app.routers.auth import get_current_user
from app.services.document_processor import process_document_async

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ---------------------------------------------------------------------------
# Helper: get current user's organisation ID
# ---------------------------------------------------------------------------
def get_user_org(auth_data: dict) -> str:
    """
    Retrieve the organisation ID for the current user.

    Raises 400 if the user has not been assigned to an organisation yet.
    """
    user = auth_data["user"]
    profile = (
        supabase_admin.table("profiles")
        .select("organization_id")
        .eq("id", user.id)
        .single()
        .execute()
    )
    if not profile.data or not profile.data.get("organization_id"):
        raise HTTPException(
            status_code=400,
            detail="User is not associated with an organisation. Create or join an organisation first.",
        )
    return profile.data["organization_id"]


# ---------------------------------------------------------------------------
# POST /upload
# ---------------------------------------------------------------------------
@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    auth_data: dict = Depends(get_current_user),
):
    """
    Upload a compliance document and trigger the async analysis pipeline.

    Accepted formats: PDF, DOCX, TXT (max 50 MB).

    The upload returns immediately with a job ID. Use GET /compliance/jobs/{job_id}
    to poll the processing status.
    """
    org_id = get_user_org(auth_data)
    user_id = auth_data["user"].id

    # Validate file type
    original_filename = file.filename or "unknown"
    suffix = Path(original_filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{suffix}' is not supported. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read and size-check the file
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the maximum allowed size of 50 MB (received {len(content) / 1024 / 1024:.1f} MB)",
        )

    # Determine MIME type
    mime_type = (
        file.content_type
        or mimetypes.guess_type(original_filename)[0]
        or "application/octet-stream"
    )

    # Generate unique document ID and storage path
    doc_id = str(uuid.uuid4())
    storage_path = f"{org_id}/{doc_id}{suffix}"

    try:
        # Upload file to Supabase Storage
        supabase_admin.storage.from_("documents").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": mime_type},
        )
        logger.info(f"File uploaded to storage: {storage_path}")

        # Create document database record
        doc_response = supabase_admin.table("documents").insert({
            "id": doc_id,
            "organization_id": org_id,
            "uploaded_by": user_id,
            "filename": storage_path,
            "original_filename": original_filename,
            "file_size": len(content),
            "mime_type": mime_type,
            "storage_path": storage_path,
            "processing_status": "pending",
        }).execute()

        if not doc_response.data:
            raise HTTPException(status_code=500, detail="Failed to create document record")

        # Create analysis job record
        job_response = supabase_admin.table("analysis_jobs").insert({
            "organization_id": org_id,
            "document_id": doc_id,
            "job_type": "compliance_analysis",
            "status": "queued",
            "progress": 0,
        }).execute()

        job_id = job_response.data[0]["id"] if job_response.data else "unknown"

        # Enqueue background processing
        background_tasks.add_task(
            process_document_async,
            doc_id=doc_id,
            org_id=org_id,
            job_id=job_id,
            content=content,
            original_filename=original_filename,
            suffix=suffix,
        )

        logger.info(f"Document {doc_id} queued for processing (job {job_id})")

        return DocumentUploadResponse(
            id=doc_id,
            filename=storage_path,
            original_filename=original_filename,
            document_type=None,
            file_size=len(content),
            processing_status=ProcessingStatusEnum.PENDING,
            job_id=job_id,
            message="Document uploaded successfully. Analysis has started in the background.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while processing the upload")


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    status: str = Query(None, description="Filter by processing_status"),
    document_type: str = Query(None, description="Filter by document_type"),
    auth_data: dict = Depends(get_current_user),
):
    """
    List documents for the current organisation with optional filtering and pagination.
    """
    org_id = get_user_org(auth_data)

    query = (
        supabase_admin.table("documents")
        .select(
            "id, organization_id, filename, original_filename, file_size, mime_type, "
            "document_type, processing_status, created_at, updated_at",
            count="exact",
        )
        .eq("organization_id", org_id)
        .order("created_at", desc=True)
    )

    if status:
        query = query.eq("processing_status", status)
    if document_type:
        query = query.eq("document_type", document_type)

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)

    response = query.execute()

    return DocumentListResponse(
        documents=[DocumentResponse(**doc) for doc in (response.data or [])],
        total=response.count or 0,
        page=page,
        per_page=per_page,
    )


# ---------------------------------------------------------------------------
# GET /{document_id}
# ---------------------------------------------------------------------------
@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """Get full details for a specific document, including extracted text."""
    org_id = get_user_org(auth_data)

    response = (
        supabase_admin.table("documents")
        .select("*")
        .eq("id", document_id)
        .eq("organization_id", org_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = response.data

    return DocumentDetailResponse(
        id=doc["id"],
        organization_id=doc["organization_id"],
        filename=doc["filename"],
        original_filename=doc["original_filename"],
        file_size=doc.get("file_size"),
        mime_type=doc.get("mime_type"),
        document_type=doc.get("document_type"),
        processing_status=doc["processing_status"],
        storage_path=doc["storage_path"],
        extracted_text=doc.get("extracted_text"),
        processing_error=doc.get("processing_error"),
        metadata=doc.get("metadata") or {},
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


# ---------------------------------------------------------------------------
# DELETE /{document_id}
# ---------------------------------------------------------------------------
@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """
    Delete a document and its associated storage file.

    Cascades to compliance_scores and gap_analysis records.
    Requires the requesting user to be the uploader or an admin/owner.
    """
    org_id = get_user_org(auth_data)
    user_id = auth_data["user"].id

    # Fetch the document to verify ownership and get storage path
    doc_response = (
        supabase_admin.table("documents")
        .select("storage_path, uploaded_by")
        .eq("id", document_id)
        .eq("organization_id", org_id)
        .single()
        .execute()
    )

    if not doc_response.data:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = doc_response.data

    # Check the user has permission to delete
    if doc.get("uploaded_by") != user_id:
        profile = supabase_admin.table("profiles").select("role").eq("id", user_id).single().execute()
        role = profile.data.get("role") if profile.data else None
        if role not in ("owner", "admin"):
            raise HTTPException(
                status_code=403,
                detail="You can only delete documents you uploaded (or you must be an admin/owner)",
            )

    # Remove file from Supabase Storage
    storage_path = doc.get("storage_path")
    if storage_path:
        try:
            supabase_admin.storage.from_("documents").remove([storage_path])
            logger.info(f"Storage file removed: {storage_path}")
        except Exception as e:
            logger.warning(f"Failed to remove storage file '{storage_path}': {e}")

    # Delete the database record (cascades to compliance_scores and gap_analysis)
    supabase_admin.table("documents").delete().eq("id", document_id).eq("organization_id", org_id).execute()

    logger.info(f"Document {document_id} deleted by user {user_id}")

    return {"message": "Document deleted successfully", "document_id": document_id}


# ---------------------------------------------------------------------------
# GET /{document_id}/jobs
# ---------------------------------------------------------------------------
@router.get("/{document_id}/jobs")
async def get_document_jobs(
    document_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """List all analysis jobs associated with a specific document."""
    org_id = get_user_org(auth_data)

    # Verify document belongs to this org
    doc_check = (
        supabase_admin.table("documents")
        .select("id")
        .eq("id", document_id)
        .eq("organization_id", org_id)
        .single()
        .execute()
    )

    if not doc_check.data:
        raise HTTPException(status_code=404, detail="Document not found")

    response = (
        supabase_admin.table("analysis_jobs")
        .select("*")
        .eq("document_id", document_id)
        .eq("organization_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "document_id": document_id,
        "jobs": response.data or [],
        "total": len(response.data or []),
    }
