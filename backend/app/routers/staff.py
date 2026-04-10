"""Staff management routes."""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query

from app.database import supabase_admin
from app.models import StaffCreate, StaffUpdate, StaffResponse, StaffListResponse
from app.routers.auth import get_current_user
from app.routers.documents import get_user_org

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------
@router.post("/", response_model=StaffResponse, status_code=201)
async def create_staff(
    request: StaffCreate,
    auth_data: dict = Depends(get_current_user),
):
    """Create a new staff member for the authenticated user's organisation."""
    org_id = get_user_org(auth_data)

    # Verify email is unique within org
    existing = supabase_admin.table("staff").select("id").eq(
        "organization_id", org_id
    ).eq("email", request.email).is_("deleted_at", "null").execute()

    if existing.data:
        raise HTTPException(
            status_code=400,
            detail=f"A staff member with email '{request.email}' already exists",
        )

    staff_data = {
        "organization_id": org_id,
        "first_name": request.first_name,
        "last_name": request.last_name,
        "email": request.email,
        "role": request.role,
        "phone_number": request.phone_number,
        "employment_type": request.employment_type,
        "start_date": str(request.start_date) if request.start_date else None,
        "worker_screening_number": request.worker_screening_number,
        "worker_screening_expiry": str(request.worker_screening_expiry) if request.worker_screening_expiry else None,
        "status": "active",
    }

    response = supabase_admin.table("staff").insert(staff_data).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create staff member")

    member = response.data[0]
    logger.info(f"Staff created: {member['id']} ({request.first_name} {request.last_name})")

    return StaffResponse(**member)


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get("/", response_model=StaffListResponse)
async def list_staff(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str = Query(None, description="Filter by status: active, inactive"),
    search: str = Query(None, description="Search by name or email"),
    auth_data: dict = Depends(get_current_user),
):
    """List staff for the authenticated user's organisation."""
    org_id = get_user_org(auth_data)

    query = supabase_admin.table("staff").select(
        "*", count="exact"
    ).eq("organization_id", org_id).is_("deleted_at", "null")

    if status:
        query = query.eq("status", status)

    if search:
        query = query.or_(
            f"first_name.ilike.%{search}%,last_name.ilike.%{search}%,email.ilike.%{search}%"
        )

    query = query.order("created_at", desc=True)

    offset = (page - 1) * per_page
    query = query.range(offset, offset + per_page - 1)

    response = query.execute()

    return StaffListResponse(
        staff=[StaffResponse(**m) for m in (response.data or [])],
        total=response.count or 0,
        page=page,
        per_page=per_page,
    )


# ---------------------------------------------------------------------------
# DELETE /{staff_id}
# ---------------------------------------------------------------------------
@router.delete("/{staff_id}")
async def delete_staff(
    staff_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """Soft delete a staff member."""
    org_id = get_user_org(auth_data)

    existing = supabase_admin.table("staff").select("id").eq(
        "id", staff_id
    ).eq("organization_id", org_id).is_("deleted_at", "null").execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail="Staff member not found")

    response = supabase_admin.table("staff").update({
        "status": "inactive",
        "deleted_at": datetime.utcnow().isoformat(),
    }).eq("id", staff_id).eq("organization_id", org_id).execute()

    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to delete staff member")

    logger.info(f"Staff {staff_id} deleted (soft)")

    return {"message": "Staff member deleted successfully", "staff_id": staff_id}
