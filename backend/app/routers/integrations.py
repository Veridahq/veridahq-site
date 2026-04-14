"""
External storage integrations routes.

Handles OAuth connect/callback for storage providers (SharePoint/OneDrive
today, more later), folder browsing during onboarding, manual resync, and
disconnect.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel

from app.database import supabase_admin
from app.integrations import get_connector
from app.routers.auth import get_current_user
from app.routers.documents import get_user_org
from app.services.integration_sync import sync_integration

logger = logging.getLogger(__name__)
router = APIRouter()


# Secret used to sign the OAuth state parameter. Falls back to the Supabase
# service key so we always have *some* secret in production — but prefer
# INTEGRATIONS_STATE_SECRET as a dedicated env var.
STATE_SECRET = (
    os.environ.get("INTEGRATIONS_STATE_SECRET")
    or os.environ.get("SECRET_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or "verida-dev-only-secret"
)
STATE_SALT = "verida.integrations.oauth.v1"
STATE_MAX_AGE_SECONDS = 600  # 10 minutes
_serializer = URLSafeTimedSerializer(STATE_SECRET, salt=STATE_SALT)

FRONTEND_SETTINGS_URL = os.environ.get(
    "FRONTEND_SETTINGS_URL",
    "https://veridahq.com/app.html#settings",
)


SUPPORTED_PROVIDERS = {"microsoft"}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class IntegrationOut(BaseModel):
    id: str
    provider: str
    account_email: Optional[str] = None
    account_name: Optional[str] = None
    sync_status: str
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    root_folders: List[dict] = []
    created_at: Optional[datetime] = None


class AuthorizeResponse(BaseModel):
    url: str


class FoldersSelection(BaseModel):
    folders: List[dict]  # [{ id, name, path }]


class FolderOut(BaseModel):
    id: str
    name: str
    path: str
    has_children: bool
    web_url: Optional[str] = None


# ---------------------------------------------------------------------------
# GET / — list integrations for the current org
# ---------------------------------------------------------------------------
@router.get("/", response_model=List[IntegrationOut])
async def list_integrations(auth_data: dict = Depends(get_current_user)):
    org_id = get_user_org(auth_data)

    resp = (
        supabase_admin.table("integrations")
        .select(
            "id, provider, account_email, account_name, sync_status, "
            "last_sync_at, last_error, root_folders, created_at"
        )
        .eq("organization_id", org_id)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


# ---------------------------------------------------------------------------
# GET /{provider}/authorize — start OAuth, return consent URL
# ---------------------------------------------------------------------------
@router.get("/{provider}/authorize", response_model=AuthorizeResponse)
async def start_authorize(
    provider: str,
    auth_data: dict = Depends(get_current_user),
):
    _require_supported(provider)
    org_id = get_user_org(auth_data)

    state = _serializer.dumps({
        "org_id": org_id,
        "provider": provider,
        "user_id": str(auth_data["user"].id),
    })

    connector = get_connector(provider)
    return AuthorizeResponse(url=connector.get_authorize_url(state=state))


# ---------------------------------------------------------------------------
# GET /{provider}/callback — OAuth redirect target
# ---------------------------------------------------------------------------
@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    """
    Handles the OAuth redirect from the provider. Verifies state, exchanges
    the code for tokens, stores the integration row, and redirects the user
    back to the Verida Settings page.
    """
    _require_supported(provider)

    if error:
        logger.warning(f"OAuth error from {provider}: {error} - {error_description}")
        return RedirectResponse(
            url=f"{FRONTEND_SETTINGS_URL}?integration=error&message={error}",
            status_code=302,
        )

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        payload = _serializer.loads(state, max_age=STATE_MAX_AGE_SECONDS)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="State expired — please try again")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid state")

    if payload.get("provider") != provider:
        raise HTTPException(status_code=400, detail="Provider mismatch in state")

    org_id = payload.get("org_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing org in state")

    connector = get_connector(provider)
    try:
        bundle = await connector.exchange_code(code)
    except Exception as exc:
        logger.error(f"OAuth exchange failed for {provider}: {exc}", exc_info=True)
        return RedirectResponse(
            url=f"{FRONTEND_SETTINGS_URL}?integration=error&message=exchange_failed",
            status_code=302,
        )

    # Upsert — one integration per (org, provider) for the MVP
    existing = (
        supabase_admin.table("integrations")
        .select("id")
        .eq("organization_id", org_id)
        .eq("provider", provider)
        .execute()
    )

    row_payload = {
        "organization_id": org_id,
        "provider": provider,
        "account_email": bundle.account_email,
        "account_name": bundle.account_name,
        "access_token": bundle.access_token,
        "refresh_token": bundle.refresh_token,
        "expires_at": bundle.expires_at.isoformat(),
        "scope": bundle.scope,
        "sync_status": "idle",
        "last_error": None,
    }

    if existing.data:
        integration_id = existing.data[0]["id"]
        supabase_admin.table("integrations").update(row_payload).eq("id", integration_id).execute()
    else:
        row_payload["root_folders"] = []
        created = supabase_admin.table("integrations").insert(row_payload).execute()
        integration_id = created.data[0]["id"] if created.data else None

    return RedirectResponse(
        url=f"{FRONTEND_SETTINGS_URL}?integration=connected&provider={provider}&id={integration_id}",
        status_code=302,
    )


# ---------------------------------------------------------------------------
# GET /{id}/folders — browse folders for the picker modal
# ---------------------------------------------------------------------------
@router.get("/{integration_id}/folders", response_model=List[FolderOut])
async def list_folders(
    integration_id: str,
    parent_id: Optional[str] = Query(None),
    auth_data: dict = Depends(get_current_user),
):
    row = _load_and_authorize(integration_id, auth_data)
    connector = get_connector(row["provider"], integration_row=row)
    try:
        folders = await connector.list_folders(parent_id=parent_id)
    except Exception as exc:
        logger.error(f"list_folders failed: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Could not list folders: {exc}")

    return [
        FolderOut(
            id=f.id,
            name=f.name,
            path=f.path,
            has_children=f.has_children,
            web_url=f.web_url,
        )
        for f in folders
    ]


# ---------------------------------------------------------------------------
# POST /{id}/folders/select — save selected folders + kick off initial sync
# ---------------------------------------------------------------------------
@router.post("/{integration_id}/folders/select")
async def select_folders(
    integration_id: str,
    selection: FoldersSelection,
    background_tasks: BackgroundTasks,
    auth_data: dict = Depends(get_current_user),
):
    row = _load_and_authorize(integration_id, auth_data)

    # Store selection
    supabase_admin.table("integrations").update({
        "root_folders": selection.folders or [],
    }).eq("id", integration_id).execute()

    # Kick off sync (fire and forget)
    background_tasks.add_task(sync_integration, integration_id)

    return {
        "message": "Folders saved — sync started",
        "integration_id": integration_id,
        "folder_count": len(selection.folders or []),
    }


# ---------------------------------------------------------------------------
# POST /{id}/sync — manual resync
# ---------------------------------------------------------------------------
@router.post("/{integration_id}/sync")
async def manual_sync(
    integration_id: str,
    background_tasks: BackgroundTasks,
    auth_data: dict = Depends(get_current_user),
):
    _load_and_authorize(integration_id, auth_data)
    background_tasks.add_task(sync_integration, integration_id)
    return {"message": "Sync started", "integration_id": integration_id}


# ---------------------------------------------------------------------------
# DELETE /{id} — disconnect
# ---------------------------------------------------------------------------
@router.delete("/{integration_id}")
async def disconnect(
    integration_id: str,
    auth_data: dict = Depends(get_current_user),
):
    _load_and_authorize(integration_id, auth_data)
    supabase_admin.table("integrations").delete().eq("id", integration_id).execute()
    return {"message": "Integration disconnected"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require_supported(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' is not supported yet",
        )


def _load_and_authorize(integration_id: str, auth_data: dict) -> dict:
    """Load an integration row and verify the caller belongs to the owning org."""
    org_id = get_user_org(auth_data)
    resp = (
        supabase_admin.table("integrations")
        .select("*")
        .eq("id", integration_id)
        .eq("organization_id", org_id)
        .single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Integration not found")
    return resp.data
