"""Staff management routes."""

import logging
import secrets
from datetime import date

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional, List

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


# ---------------------------------------------------------------------------
# PUT /{user_id} — update role
# ---------------------------------------------------------------------------
class StaffUpdate(BaseModel):
    role: str


@router.put("/{user_id}")
async def update_staff(
    user_id: str,
    request: StaffUpdate,
    auth_data: dict = Depends(get_current_user),
):
    """Update a staff member's role."""
    org_id = get_user_org(auth_data)
    role = request.role if request.role in ("owner", "admin", "member") else "member"

    existing = supabase_admin.table("profiles").select("id").eq(
        "id", user_id
    ).eq("organization_id", org_id).execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail="Staff member not found in this organisation")

    supabase_admin.table("profiles").update({"role": role}).eq("id", user_id).execute()

    return {"id": user_id, "role": role}


# ---------------------------------------------------------------------------
# DELETE /{user_id} — remove from org
# ---------------------------------------------------------------------------
@router.delete("/{user_id}", status_code=204)
async def remove_staff(
    user_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """Remove a staff member from the organisation (clears organization_id, does not delete auth user)."""
    org_id = get_user_org(auth_data)
    caller_id = auth_data.get("user", {}).get("id") or auth_data.get("id")

    if user_id == caller_id:
        raise HTTPException(status_code=400, detail="You cannot remove yourself")

    existing = supabase_admin.table("profiles").select("id").eq(
        "id", user_id
    ).eq("organization_id", org_id).execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail="Staff member not found in this organisation")

    supabase_admin.table("profiles").update({"organization_id": None}).eq("id", user_id).execute()


VALID_CERT_TYPES = {"worker_screening", "first_aid", "ndis_orientation"}


class CertUpsert(BaseModel):
    issued_date: Optional[date] = None
    expiry_date: Optional[date] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# GET /certifications — all certs for the org
# ---------------------------------------------------------------------------
@router.get("/certifications")
async def list_org_certifications(
    auth_data: dict = Depends(get_current_user),
):
    """Return all staff certifications for the current organisation."""
    org_id = get_user_org(auth_data)
    response = supabase_admin.table("staff_certifications").select(
        "id, profile_id, cert_type, issued_date, expiry_date, notes, updated_at"
    ).eq("organization_id", org_id).execute()
    return {"certifications": response.data or []}


# ---------------------------------------------------------------------------
# PUT /{user_id}/certifications/{cert_type} — upsert one cert
# ---------------------------------------------------------------------------
@router.put("/{user_id}/certifications/{cert_type}", status_code=200)
async def upsert_certification(
    user_id: str,
    cert_type: str,
    body: CertUpsert,
    auth_data: dict = Depends(get_current_user),
):
    """
    Create or update a single certification record for a staff member.

    Allowed cert_type values: worker_screening, first_aid, ndis_orientation.
    Requires admin or owner role.
    """
    org_id = get_user_org(auth_data)

    if cert_type not in VALID_CERT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cert_type. Must be one of: {', '.join(sorted(VALID_CERT_TYPES))}",
        )

    # Verify the target staff member belongs to this org
    profile_resp = supabase_admin.table("profiles").select("id").eq(
        "id", user_id
    ).eq("organization_id", org_id).single().execute()
    if not profile_resp.data:
        raise HTTPException(status_code=404, detail="Staff member not found in this organisation")

    # Only admins/owners may write certs
    caller_profile = supabase_admin.table("profiles").select("role").eq(
        "id", auth_data["user"].id
    ).single().execute()
    caller_role = (caller_profile.data or {}).get("role", "member")
    if caller_role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin or owner role required to update certifications")

    record = {
        "profile_id": user_id,
        "organization_id": org_id,
        "cert_type": cert_type,
    }
    if body.issued_date is not None:
        record["issued_date"] = body.issued_date.isoformat()
    if body.expiry_date is not None:
        record["expiry_date"] = body.expiry_date.isoformat()
    if body.notes is not None:
        record["notes"] = body.notes

    result = supabase_admin.table("staff_certifications").upsert(
        record,
        on_conflict="profile_id,cert_type",
    ).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to save certification")

    logger.info(f"Cert upsert: {cert_type} for user {user_id} by {auth_data['user'].id}")
    return result.data[0]


# ---------------------------------------------------------------------------
# DELETE /{user_id}/certifications/{cert_type}
# ---------------------------------------------------------------------------
@router.delete("/{user_id}/certifications/{cert_type}", status_code=204)
async def delete_certification(
    user_id: str,
    cert_type: str,
    auth_data: dict = Depends(get_current_user),
):
    """Remove a certification record for a staff member."""
    org_id = get_user_org(auth_data)
    if cert_type not in VALID_CERT_TYPES:
        raise HTTPException(status_code=400, detail="Invalid cert_type")

    supabase_admin.table("staff_certifications").delete().eq(
        "profile_id", user_id
    ).eq("cert_type", cert_type).eq("organization_id", org_id).execute()


# ---------------------------------------------------------------------------
# PATCH /{user_id}/deactivate
# ---------------------------------------------------------------------------
@router.patch("/{user_id}/deactivate", status_code=204)
async def deactivate_staff(
    user_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """Deactivate a staff member by removing them from the organisation."""
    org_id = get_user_org(auth_data)
    caller_id = auth_data.get("user", {}).get("id") or auth_data.get("id")

    if user_id == caller_id:
        raise HTTPException(status_code=400, detail="You cannot deactivate yourself")

    existing = supabase_admin.table("profiles").select("id").eq(
        "id", user_id
    ).eq("organization_id", org_id).execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail="Staff member not found in this organisation")

    supabase_admin.table("profiles").update({"organization_id": None}).eq("id", user_id).execute()
