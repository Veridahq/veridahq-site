"""Client management routes."""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks

from app.database import supabase_admin
from app.models import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    ClientListResponse,
    ClientDocumentCreate,
    ClientDocumentResponse,
    ClientDocumentListResponse,
    ClientComplianceCheckTrigger,
    ClientComplianceCheckResponse,
    ClientComplianceCheckListResponse,
)
from app.routers.auth import get_current_user
from app.routers.documents import get_user_org
from app.services.client_compliance_analyzer import run_comprehensive_client_check

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------
@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(
    request: ClientCreate,
    auth_data: dict = Depends(get_current_user),
):
    """
    Create a new NDIS client/participant profile.

    The participant is added to the authenticated user's organisation.
    """
    org_id = get_user_org(auth_data)

    # Verify NDIS participant number is unique within org
    existing = supabase_admin.table("clients").select("id").eq(
        "organization_id", org_id
    ).eq("ndis_participant_number", request.ndis_participant_number).execute()

    if existing.data:
        raise HTTPException(
            status_code=400,
            detail=f"A client with NDIS participant number '{request.ndis_participant_number}' already exists",
        )

    # Create client record
    client_data = {
        "organization_id": org_id,
        "first_name": request.first_name,
        "last_name": request.last_name,
        "date_of_birth": str(request.date_of_birth),
        "ndis_participant_number": request.ndis_participant_number,
        "email": request.email,
        "phone_number": request.phone_number,
        "address_line1": request.address_line1,
        "address_line2": request.address_line2,
        "suburb": request.suburb,
        "state": request.state,
        "postcode": request.postcode,
        "country": request.country,
        "current_plan_start_date": str(request.current_plan_start_date) if request.current_plan_start_date else None,
        "current_plan_end_date": str(request.current_plan_end_date) if request.current_plan_end_date else None,
        "current_plan_budget_amount": request.current_plan_budget_amount,
        "funded_support_categories": request.funded_support_categories or [],
        "requires_behaviour_support": request.requires_behaviour_support,
        "primary_contact_name": request.primary_contact_name,
        "primary_contact_relationship": request.primary_contact_relationship,
        "primary_contact_email": request.primary_contact_email,
        "primary_contact_phone": request.primary_contact_phone,
        "status": "active",
    }

    response = supabase_admin.table("clients").insert(client_data).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create client")

    client = response.data[0]
    logger.info(f"Client created: {client['id']} ({request.first_name} {request.last_name})")

    return ClientResponse(**client)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get("/", response_model=ClientListResponse)
async def list_clients(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    status: str = Query(None, description="Filter by status: active, inactive, exited"),
    search: str = Query(None, description="Search by name or NDIS participant number"),
    auth_data: dict = Depends(get_current_user),
):
    """
    List clients for the authenticated user's organisation with pagination.

    Optionally filter by status or search by name/NDIS number.
    """
    org_id = get_user_org(auth_data)

    query = supabase_admin.table("clients").select(
        "*",
        count="exact",
    ).eq("organization_id", org_id).is_("deleted_at", "null")

    if status:
        query = query.eq("status", status)

    if search:
        # Search by name (full text match on first_name or last_name)
        query = query.or_(f"first_name.ilike.%{search}%,last_name.ilike.%{search}%,ndis_participant_number.ilike.%{search}%")

    query = query.order("created_at", desc=True)

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)

    response = query.execute()

    return ClientListResponse(
        clients=[ClientResponse(**c) for c in (response.data or [])],
        total=response.count or 0,
        page=page,
        per_page=per_page,
    )


# ---------------------------------------------------------------------------
# GET /{client_id}
# ---------------------------------------------------------------------------
@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """Get full details for a specific client."""
    org_id = get_user_org(auth_data)

    response = supabase_admin.table("clients").select("*").eq(
        "id", client_id
    ).eq("organization_id", org_id).is_("deleted_at", "null").single().execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Client not found")

    return ClientResponse(**response.data)


# ---------------------------------------------------------------------------
# PUT /{client_id}
# ---------------------------------------------------------------------------
@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: str,
    request: ClientUpdate,
    auth_data: dict = Depends(get_current_user),
):
    """
    Update a client's profile information.

    Only provided fields are updated.
    """
    org_id = get_user_org(auth_data)

    # Verify client exists
    existing = supabase_admin.table("clients").select("id").eq(
        "id", client_id
    ).eq("organization_id", org_id).is_("deleted_at", "null").execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail="Client not found")

    # Build update data from non-null fields
    update_data = {}
    for field, value in request.dict(exclude_unset=True).items():
        if value is not None:
            if field in ("current_plan_start_date", "current_plan_end_date"):
                update_data[field] = str(value) if value else None
            else:
                update_data[field] = value

    response = supabase_admin.table("clients").update(update_data).eq(
        "id", client_id
    ).eq("organization_id", org_id).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to update client")

    logger.info(f"Client {client_id} updated")

    return ClientResponse(**response.data[0])


# ---------------------------------------------------------------------------
# DELETE /{client_id}
# ---------------------------------------------------------------------------
@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """
    Soft delete a client (sets status to inactive).

    The client record is retained for audit purposes.
    """
    org_id = get_user_org(auth_data)

    # Verify client exists
    existing = supabase_admin.table("clients").select("id").eq(
        "id", client_id
    ).eq("organization_id", org_id).is_("deleted_at", "null").execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail="Client not found")

    # Soft delete
    response = supabase_admin.table("clients").update({
        "status": "inactive",
        "deleted_at": datetime.utcnow().isoformat(),
    }).eq("id", client_id).eq("organization_id", org_id).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to delete client")

    logger.info(f"Client {client_id} deleted (soft)")

    return {"message": "Client deleted successfully", "client_id": client_id}


# ---------------------------------------------------------------------------
# POST /{client_id}/documents
# ---------------------------------------------------------------------------
@router.post("/{client_id}/documents", response_model=ClientDocumentResponse, status_code=201)
async def link_document_to_client(
    client_id: str,
    request: ClientDocumentCreate,
    auth_data: dict = Depends(get_current_user),
):
    """
    Link an uploaded document to a client for tracking.

    The document must already exist in the documents table.
    """
    org_id = get_user_org(auth_data)

    # Verify client exists
    client_check = supabase_admin.table("clients").select("id").eq(
        "id", client_id
    ).eq("organization_id", org_id).is_("deleted_at", "null").execute()

    if not client_check.data:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify document exists and belongs to org
    doc_check = supabase_admin.table("documents").select("id").eq(
        "id", request.document_id
    ).eq("organization_id", org_id).execute()

    if not doc_check.data:
        raise HTTPException(status_code=404, detail="Document not found or does not belong to this organisation")

    # Create client_document record
    doc_link_data = {
        "client_id": client_id,
        "organization_id": org_id,
        "document_id": request.document_id,
        "document_type": request.document_type,
        "document_date": str(request.document_date) if request.document_date else None,
        "document_version": request.document_version,
        "review_due_date": str(request.review_due_date) if request.review_due_date else None,
        "is_required": request.is_required,
        "notes": request.notes,
        "is_current": True,
        "status": "active",
    }

    response = supabase_admin.table("client_documents").insert(doc_link_data).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to link document to client")

    logger.info(f"Document {request.document_id} linked to client {client_id}")

    return ClientDocumentResponse(**response.data[0])


# ---------------------------------------------------------------------------
# GET /{client_id}/documents
# ---------------------------------------------------------------------------
@router.get("/{client_id}/documents", response_model=ClientDocumentListResponse)
async def list_client_documents(
    client_id: str,
    is_current: bool = Query(None, description="Filter by is_current flag"),
    document_type: str = Query(None, description="Filter by document_type"),
    auth_data: dict = Depends(get_current_user),
):
    """
    List all documents linked to a client with optional filtering.
    """
    org_id = get_user_org(auth_data)

    # Verify client exists
    client_check = supabase_admin.table("clients").select("id").eq(
        "id", client_id
    ).eq("organization_id", org_id).is_("deleted_at", "null").execute()

    if not client_check.data:
        raise HTTPException(status_code=404, detail="Client not found")

    query = supabase_admin.table("client_documents").select(
        "*",
        count="exact",
    ).eq("client_id", client_id).eq("organization_id", org_id).eq("status", "active")

    if is_current is not None:
        query = query.eq("is_current", is_current)

    if document_type:
        query = query.eq("document_type", document_type)

    query = query.order("created_at", desc=True)

    response = query.execute()

    return ClientDocumentListResponse(
        documents=[ClientDocumentResponse(**d) for d in (response.data or [])],
        total=response.count or 0,
    )


# ---------------------------------------------------------------------------
# POST /{client_id}/compliance-check
# ---------------------------------------------------------------------------
@router.post("/{client_id}/compliance-check", response_model=ClientComplianceCheckResponse, status_code=201)
async def trigger_compliance_check(
    client_id: str,
    request: ClientComplianceCheckTrigger,
    background_tasks: BackgroundTasks,
    auth_data: dict = Depends(get_current_user),
):
    """
    Trigger a compliance check for a client.

    The check runs asynchronously. Use the returned check ID to poll for results.
    """
    org_id = get_user_org(auth_data)
    user_id = auth_data["user"].id

    # Verify client exists
    client_check = supabase_admin.table("clients").select("id").eq(
        "id", client_id
    ).eq("organization_id", org_id).is_("deleted_at", "null").execute()

    if not client_check.data:
        raise HTTPException(status_code=404, detail="Client not found")

    # Create check record
    check_data = {
        "client_id": client_id,
        "organization_id": org_id,
        "check_type": request.check_type,
        "status": "processing",
        "created_by": user_id,
    }

    response = supabase_admin.table("client_compliance_checks").insert(check_data).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create compliance check")

    check = response.data[0]
    check_id = check["id"]

    # Queue background task for comprehensive check
    if request.check_type == "comprehensive":
        background_tasks.add_task(
            _run_check_async,
            check_id=check_id,
            client_id=client_id,
            org_id=org_id,
        )

    logger.info(f"Compliance check {check_id} initiated for client {client_id}")

    return ClientComplianceCheckResponse(**check)


async def _run_check_async(check_id: str, client_id: str, org_id: str):
    """Background task: run comprehensive check and update results."""
    try:
        result = await run_comprehensive_client_check(client_id, org_id)

        # Update check record with results
        supabase_admin.table("client_compliance_checks").update({
            "status": result.get("status"),
            "overall_score": result.get("overall_score"),
            "findings": result.get("findings"),
            "ai_model_used": result.get("ai_model_used"),
            "executed_at": result.get("executed_at"),
        }).eq("id", check_id).execute()

        logger.info(f"Compliance check {check_id} completed with status={result.get('status')}")

    except Exception as e:
        logger.error(f"Compliance check {check_id} failed: {e}", exc_info=True)
        supabase_admin.table("client_compliance_checks").update({
            "status": "failed",
            "findings": [{"finding_type": "check_error", "severity": "critical", "message": str(e)}],
        }).eq("id", check_id).execute()


# ---------------------------------------------------------------------------
# GET /{client_id}/compliance-checks
# ---------------------------------------------------------------------------
@router.get("/{client_id}/compliance-checks", response_model=ClientComplianceCheckListResponse)
async def list_client_compliance_checks(
    client_id: str,
    check_type: str = Query(None, description="Filter by check_type"),
    status: str = Query(None, description="Filter by status: passed, failed, warning"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    auth_data: dict = Depends(get_current_user),
):
    """
    List compliance checks for a client, most recent first.
    """
    org_id = get_user_org(auth_data)

    # Verify client exists
    client_check = supabase_admin.table("clients").select("id").eq(
        "id", client_id
    ).eq("organization_id", org_id).is_("deleted_at", "null").execute()

    if not client_check.data:
        raise HTTPException(status_code=404, detail="Client not found")

    query = supabase_admin.table("client_compliance_checks").select(
        "*",
        count="exact",
    ).eq("client_id", client_id).eq("organization_id", org_id)

    if check_type:
        query = query.eq("check_type", check_type)

    if status:
        query = query.eq("status", status)

    query = query.order("created_at", desc=True).limit(limit)

    response = query.execute()

    return ClientComplianceCheckListResponse(
        checks=[ClientComplianceCheckResponse(**c) for c in (response.data or [])],
        total=response.count or 0,
    )
