"""
Cloud-storage integration routes.

Prefix: /api/integrations  (registered in main.py)

Endpoints:
    GET  /                          — list org's active integrations
    GET  /{provider}/authorize      — get OAuth URL (signed state, 10-min TTL)
    GET  /{provider}/callback       — OAuth callback (exchange code, upsert row, redirect)
    GET  /{id}/folders              — browse connector folders (?parent_id=)
    POST /{id}/folders/select       — store folder selection, enqueue initial sync
    POST /{id}/sync                 — manual resync
    DELETE /{id}                    — disconnect / delete integration row
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel

from app.config import settings
from app.database import supabase_admin
from app.integrations.base import get_connector
from app.routers.auth import get_current_user
from app.routers.documents import get_user_org
from app.services.integration_sync import sync_integration

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# State signing (10-minute TTL)
# ---------------------------------------------------------------------------
# We use the Supabase service key as the signing secret — it's already a
# high-entropy secret that's present in the environment.
_signer = URLSafeTimedSerializer(settings.supabase_service_key, salt="integration-oauth-state")

SUPPORTED_PROVIDERS = {"microsoft"}
REDIRECT_AFTER_CONNECT = "https://veridahq.com/app.html#settings?integration=connected"

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class FolderSelectRequest(BaseModel):
    folder_ids: List[str]


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

@router.get("/")
async def list_integrations(auth_data: dict = Depends(get_current_user)):
    """List all integrations for the current organisation."""
    org_id = get_user_org(auth_data)

    resp = (
        supabase_admin.table("integrations")
        .select(
            "id, provider, account_email, sync_status, last_sync_at, last_error, "
            "root_folders, created_at, updated_at"
        )
        .eq("organization_id", org_id)
        .order("created_at", desc=False)
        .execute()
    )
    return {"integrations": resp.data or []}


# ---------------------------------------------------------------------------
# GET /{provider}/authorize
# ---------------------------------------------------------------------------

@router.get("/{provider}/authorize")
async def get_authorize_url(
    provider: str,
    auth_data: dict = Depends(get_current_user),
):
    """Return a signed OAuth URL for the given provider."""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    org_id = get_user_org(auth_data)

    # Sign state: {org_id, provider} with 10-min TTL
    state = _signer.dumps({"org_id": org_id, "provider": provider})

    connector = get_connector(provider, {})
    url = await connector.get_authorize_url(state)
    return {"url": url, "provider": provider}


# ---------------------------------------------------------------------------
# GET /{provider}/callback
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
    Handles the OAuth redirect from the provider.

    Verifies the signed state, exchanges the code for tokens, upserts the
    integrations row, then redirects the user back to the app.
    """
    if error:
        logger.warning(f"OAuth error from {provider}: {error} — {error_description}")
        return RedirectResponse(
            f"https://veridahq.com/app.html#settings?integration=error&reason={error}"
        )

    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing 'code' or 'state' parameter")

    # Verify state signature (max_age=600 → 10 minutes)
    try:
        payload = _signer.loads(state, max_age=600)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="OAuth state expired — please try connecting again")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF attempt")

    if payload.get("provider") != provider:
        raise HTTPException(status_code=400, detail="Provider mismatch in OAuth state")

    org_id: str = payload["org_id"]

    # Exchange code for tokens
    connector = get_connector(provider, {})
    try:
        tokens = await connector.exchange_code(code)
    except Exception as exc:
        logger.error(f"Token exchange failed for {provider}: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to exchange authorisation code")

    # Upsert integrations row (one row per org+provider)
    upsert_data = {
        "organization_id": org_id,
        "provider": provider,
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_at": tokens["expires_at"],
        "account_email": tokens.get("account_email", ""),
        "sync_status": "idle",
        "last_error": None,
    }

    try:
        supabase_admin.table("integrations").upsert(
            upsert_data,
            on_conflict="organization_id,provider",
        ).execute()
    except Exception as exc:
        logger.error(f"Failed to upsert integration row: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save integration")

    logger.info(f"Integration connected: org={org_id} provider={provider} email={tokens.get('account_email')}")

    # Redirect user back to app — JavaScript will detect #settings?integration=connected
    return RedirectResponse(REDIRECT_AFTER_CONNECT)


# ---------------------------------------------------------------------------
# GET /{id}/folders
# ---------------------------------------------------------------------------

@router.get("/{integration_id}/folders")
async def list_folders(
    integration_id: str,
    parent_id: Optional[str] = Query(None, description="Opaque folder ID from previous call; omit for root"),
    auth_data: dict = Depends(get_current_user),
):
    """Browse folders for the connected integration."""
    org_id = get_user_org(auth_data)
    row = _get_integration_row(integration_id, org_id)

    connector = get_connector(row["provider"], row)
    try:
        folders = await connector.list_folders(parent_id=parent_id)
        # Persist refreshed tokens if connector updated them
        _maybe_persist_tokens(integration_id, row, connector.row)
    except Exception as exc:
        logger.error(f"list_folders failed for integration {integration_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to list folders: {exc}")

    return {"folders": folders, "parent_id": parent_id}


# ---------------------------------------------------------------------------
# POST /{id}/folders/select
# ---------------------------------------------------------------------------

@router.post("/{integration_id}/folders/select")
async def select_folders(
    integration_id: str,
    body: FolderSelectRequest,
    background_tasks: BackgroundTasks,
    auth_data: dict = Depends(get_current_user),
):
    """
    Store selected folder IDs and trigger the initial background sync.

    Body: { "folder_ids": ["drive:me:abc123", ...] }
    """
    org_id = get_user_org(auth_data)
    row = _get_integration_row(integration_id, org_id)

    if not body.folder_ids:
        raise HTTPException(status_code=400, detail="folder_ids must not be empty")

    # Persist selected folders
    supabase_admin.table("integrations").update({
        "root_folders": body.folder_ids,
        "sync_status": "idle",
    }).eq("id", integration_id).execute()

    # Kick off initial sync in background
    background_tasks.add_task(sync_integration, integration_id)

    return {
        "message": "Folders saved. Initial sync started in background.",
        "folder_ids": body.folder_ids,
    }


# ---------------------------------------------------------------------------
# POST /{id}/sync
# ---------------------------------------------------------------------------

@router.post("/{integration_id}/sync")
async def manual_sync(
    integration_id: str,
    background_tasks: BackgroundTasks,
    auth_data: dict = Depends(get_current_user),
):
    """Trigger a manual resync for an integration."""
    org_id = get_user_org(auth_data)
    row = _get_integration_row(integration_id, org_id)

    if row["sync_status"] == "syncing":
        return {"message": "Sync already in progress", "sync_status": "syncing"}

    background_tasks.add_task(sync_integration, integration_id)
    return {"message": "Sync started", "integration_id": integration_id}


# ---------------------------------------------------------------------------
# DELETE /{id}
# ---------------------------------------------------------------------------

@router.delete("/{integration_id}")
async def disconnect_integration(
    integration_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """Disconnect an integration (deletes tokens; synced documents remain)."""
    org_id = get_user_org(auth_data)
    _get_integration_row(integration_id, org_id)  # verifies ownership

    supabase_admin.table("integrations").delete().eq("id", integration_id).execute()
    logger.info(f"Integration {integration_id} disconnected by org {org_id}")

    return {"message": "Integration disconnected", "integration_id": integration_id}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_integration_row(integration_id: str, org_id: str) -> dict:
    """Fetch an integration row and assert org ownership. Raises 404 if missing."""
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


def _maybe_persist_tokens(integration_id: str, old_row: dict, new_row: dict) -> None:
    """If the connector refreshed its access token, write the new values back."""
    if new_row.get("access_token") != old_row.get("access_token"):
        supabase_admin.table("integrations").update({
            "access_token": new_row.get("access_token"),
            "refresh_token": new_row.get("refresh_token"),
            "expires_at": new_row.get("expires_at"),
        }).eq("id", integration_id).execute()
