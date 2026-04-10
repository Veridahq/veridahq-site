"""Staff management routes."""

import logging
import secrets

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.database import supabase_admin
from app.routers.auth import get_current_user
from app.routers.documents import get_user_org

logger = logging.getLogger(__name__)
router = APIRouter()


class StaffCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: Optional[str] = "member"


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------
@router.post("/", status_code=201)
async def create_staff(
    request: StaffCreate,
    auth_data: dict = Depends(get_current_user),
):
    """
    Add a new staff member to the organisation.

    Creates a Supabase auth account and assigns them to the current org.
    A password-reset email is sent so they can set their own password.
    """
    org_id = get_user_org(auth_data)

    # Check for duplicate email within org
    existing = supabase_admin.table("profiles").select("id").eq(
        "email", request.email
    ).eq("organization_id", org_id).execute()

    if existing.data:
        raise HTTPException(
            status_code=400,
            detail=f"A staff member with email '{request.email}' already exists in this organisation",
        )

    # Create auth user (admin API bypasses email confirmation)
    temp_password = secrets.token_urlsafe(20)
    try:
        user_response = supabase_admin.auth.admin.create_user({
            "email": request.email,
            "password": temp_password,
            "email_confirm": True,
            "user_metadata": {"full_name": request.full_name},
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create staff account: {str(e)}")

    if not user_response.user:
        raise HTTPException(status_code=500, detail="Failed to create staff user")

    user_id = user_response.user.id
    role = request.role if request.role in ("admin", "member") else "member"

    # Upsert profile with org assignment
    supabase_admin.table("profiles").upsert({
        "id": user_id,
        "email": request.email,
        "full_name": request.full_name,
        "role": role,
        "organization_id": org_id,
    }).execute()

    logger.info(f"Staff member created: {request.email} ({user_id}) for org {org_id}")

    return {
        "id": user_id,
        "email": request.email,
        "full_name": request.full_name,
        "role": role,
        "organization_id": org_id,
    }


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get("/")
async def list_staff(
    auth_data: dict = Depends(get_current_user),
):
    """List all staff members in the authenticated user's organisation."""
    org_id = get_user_org(auth_data)

    response = supabase_admin.table("profiles").select(
        "id, email, full_name, role, created_at"
    ).eq("organization_id", org_id).order("created_at").execute()

    return {
        "staff": response.data or [],
        "total": len(response.data or []),
    }
