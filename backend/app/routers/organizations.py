"""Organisation management routes."""

import logging
from fastapi import APIRouter, HTTPException, Depends

from app.database import supabase_admin
from app.models import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
)
from app.routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: verify user has access to a given organisation
# ---------------------------------------------------------------------------
def require_org_access(
    auth_data: dict,
    organization_id: str,
    require_admin: bool = False,
) -> dict:
    """
    Verify the current user belongs to the specified organisation.

    Args:
        auth_data: output of get_current_user()
        organization_id: the UUID of the organisation to check
        require_admin: if True, also require owner or admin role

    Returns:
        The user's profile dict if access is granted.

    Raises:
        HTTPException 403 if the user does not belong to the org or lacks role.
        HTTPException 404 if the user profile is not found.
    """
    user = auth_data["user"]
    profile_response = supabase_admin.table("profiles").select("*").eq("id", user.id).single().execute()
    profile = profile_response.data

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    if profile.get("organization_id") != organization_id:
        raise HTTPException(status_code=403, detail="Access denied: you do not belong to this organisation")

    if require_admin and profile.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required for this operation")

    return profile


# ---------------------------------------------------------------------------
# POST /
# ---------------------------------------------------------------------------
@router.post("/", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    org: OrganizationCreate,
    auth_data: dict = Depends(get_current_user),
):
    """
    Create a new organisation and assign the current user as owner.

    A user can only belong to one organisation. Returns 400 if the user is
    already associated with an organisation.
    """
    user = auth_data["user"]

    # Prevent creating duplicate organisations
    profile_response = supabase_admin.table("profiles").select("organization_id").eq("id", user.id).single().execute()
    if profile_response.data and profile_response.data.get("organization_id"):
        raise HTTPException(
            status_code=400,
            detail="User already belongs to an organisation. Leave the current organisation before creating a new one.",
        )

    try:
        org_data = {k: v for k, v in org.dict().items() if v is not None}
        org_response = supabase_admin.table("organizations").insert(org_data).execute()

        if not org_response.data:
            raise HTTPException(status_code=400, detail="Failed to create organisation")

        new_org = org_response.data[0]

        # Assign the creating user as owner
        supabase_admin.table("profiles").update({
            "organization_id": new_org["id"],
            "role": "owner",
        }).eq("id", user.id).execute()

        logger.info(f"Organisation created: '{new_org['name']}' ({new_org['id']}) by user {user.id}")

        return OrganizationResponse(**new_org)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create organisation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# GET /{organization_id}
# ---------------------------------------------------------------------------
@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """Get organisation details. Requires membership of the organisation."""
    require_org_access(auth_data, organization_id)

    response = supabase_admin.table("organizations").select("*").eq("id", organization_id).single().execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Organisation not found")

    return OrganizationResponse(**response.data)


# ---------------------------------------------------------------------------
# PUT /{organization_id}
# ---------------------------------------------------------------------------
@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: str,
    update: OrganizationUpdate,
    auth_data: dict = Depends(get_current_user),
):
    """
    Update organisation details.

    Requires owner or admin role within the organisation.
    """
    require_org_access(auth_data, organization_id, require_admin=True)

    # Only include fields that were explicitly set (not None)
    update_data = {k: v for k, v in update.dict().items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    # Serialise date fields to ISO strings for Supabase
    if "audit_date" in update_data and update_data["audit_date"]:
        update_data["audit_date"] = update_data["audit_date"].isoformat()

    response = supabase_admin.table("organizations").update(update_data).eq("id", organization_id).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Organisation not found")

    logger.info(f"Organisation {organization_id} updated by user {auth_data['user'].id}")

    return OrganizationResponse(**response.data[0])


# ---------------------------------------------------------------------------
# GET /{organization_id}/members
# ---------------------------------------------------------------------------
@router.get("/{organization_id}/members")
async def get_members(
    organization_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """
    List all members of an organisation.

    Any member of the organisation can view the member list.
    """
    require_org_access(auth_data, organization_id)

    response = supabase_admin.table("profiles").select(
        "id, email, full_name, role, created_at"
    ).eq("organization_id", organization_id).order("created_at").execute()

    return {
        "members": response.data or [],
        "total": len(response.data or []),
    }


# ---------------------------------------------------------------------------
# PATCH /{organization_id}/members/{user_id}/role
# ---------------------------------------------------------------------------
@router.patch("/{organization_id}/members/{user_id}/role")
async def update_member_role(
    organization_id: str,
    user_id: str,
    role: str,
    auth_data: dict = Depends(get_current_user),
):
    """
    Update a member's role within the organisation.

    Only owners can change roles. Valid roles: admin, member.
    Owners cannot demote themselves.
    """
    profile = require_org_access(auth_data, organization_id, require_admin=True)

    if profile.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Only owners can change member roles")

    if role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Valid roles are: admin, member")

    # Prevent owner from changing their own role
    if user_id == auth_data["user"].id:
        raise HTTPException(status_code=400, detail="You cannot change your own role")

    # Verify the target user is in the same organisation
    target_profile = supabase_admin.table("profiles").select("organization_id, role").eq("id", user_id).single().execute()
    if not target_profile.data or target_profile.data.get("organization_id") != organization_id:
        raise HTTPException(status_code=404, detail="Member not found in this organisation")

    supabase_admin.table("profiles").update({"role": role}).eq("id", user_id).execute()

    return {"message": f"Member role updated to '{role}'"}
