"""Authentication routes using Supabase Auth."""

import logging
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional

from app.database import supabase, supabase_admin
from app.config import settings
from app.services.email import send_password_reset_email
from app.models import (
    SignUpRequest,
    SignInRequest,
    TokenResponse,
    ProfileResponse,
    PasswordResetRequest,
    PasswordUpdateRequest,
    RefreshTokenRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency: extract and verify the current user from Bearer token
# ---------------------------------------------------------------------------
def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """
    Extract and verify the current user from a Bearer token.

    Returns a dict with keys:
        - user: the Supabase User object
        - token: the raw access token string
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header. Expected: Bearer <token>",
        )

    token = authorization.split(" ", 1)[1]

    try:
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return {"user": user_response.user, "token": token}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ---------------------------------------------------------------------------
# POST /signup
# ---------------------------------------------------------------------------
@router.post("/signup", response_model=dict, status_code=201)
async def sign_up(request: SignUpRequest):
    """
    Register a new user account.

    Optionally creates a new organisation and assigns the user as owner.
    Returns a message instructing the user to verify their email.
    """
    try:
        # Create the auth user in Supabase
        auth_response = supabase.auth.sign_up({
            "email": request.email,
            "password": request.password,
            "options": {
                "data": {"full_name": request.full_name},
                "email_redirect_to": "https://veridahq.com/verify-email.html",
            },
        })

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Failed to create account")

        user_id = auth_response.user.id

        # Always create an organisation — use provided name or derive one from the user's full name
        org_name = request.organization_name or f"{request.full_name}'s Organisation"
        org_response = supabase_admin.table("organizations").insert({
            "name": org_name,
            "plan_tier": "essentials",
        }).execute()

        organization_id = None
        if org_response.data:
            organization_id = org_response.data[0]["id"]
            logger.info(f"Created organisation '{org_name}' ({organization_id})")

        # Create the user profile
        supabase_admin.table("profiles").insert({
            "id": user_id,
            "email": request.email,
            "full_name": request.full_name,
            "role": "owner",
            "organization_id": organization_id,
        }).execute()

        logger.info(f"New user registered: {request.email} ({user_id})")

        return {
            "message": "Account created successfully. You can sign in immediately.",
            "user_id": user_id,
            "email": request.email,
            "organization_id": organization_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sign up error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# POST /signin
# ---------------------------------------------------------------------------
@router.post("/signin", response_model=TokenResponse)
async def sign_in(request: SignInRequest):
    """
    Sign in with email and password.

    Returns JWT access and refresh tokens along with the user profile.
    """
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password,
        })

        if not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        session = auth_response.session
        user = auth_response.user

        # Fetch full profile data
        profile_response = supabase_admin.table("profiles").select("*").eq("id", user.id).single().execute()
        profile = profile_response.data or {}

        logger.info(f"User signed in: {user.email}")

        return TokenResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            token_type="bearer",
            expires_in=session.expires_in or 3600,
            user={
                "id": user.id,
                "email": user.email,
                "full_name": profile.get("full_name"),
                "role": profile.get("role", "member"),
                "organization_id": profile.get("organization_id"),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sign in error: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")


# ---------------------------------------------------------------------------
# POST /signout
# ---------------------------------------------------------------------------
@router.post("/signout")
async def sign_out(auth_data: dict = Depends(get_current_user)):
    """Sign out the current user and invalidate the session."""
    try:
        supabase.auth.sign_out()
        logger.info(f"User signed out: {auth_data['user'].email}")
        return {"message": "Signed out successfully"}
    except Exception as e:
        logger.warning(f"Sign out error (non-critical): {e}")
        # Always return success — client should discard tokens regardless
        return {"message": "Signed out"}


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------
@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh an expired access token using the refresh token.

    Returns new access and refresh tokens.
    """
    try:
        auth_response = supabase.auth.refresh_session(request.refresh_token)

        if not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

        session = auth_response.session
        user = auth_response.user

        profile_response = supabase_admin.table("profiles").select("*").eq("id", user.id).single().execute()
        profile = profile_response.data or {}

        return TokenResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            token_type="bearer",
            expires_in=session.expires_in or 3600,
            user={
                "id": user.id,
                "email": user.email,
                "full_name": profile.get("full_name"),
                "role": profile.get("role", "member"),
                "organization_id": profile.get("organization_id"),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(status_code=401, detail="Failed to refresh token")


# ---------------------------------------------------------------------------
# POST /reset-password
# ---------------------------------------------------------------------------
@router.post("/reset-password")
async def reset_password(request: PasswordResetRequest):
    """
    Send a Verida-branded password reset email.

    Uses the Supabase admin generate_link API to obtain a verified magic
    link, then sends a custom HTML email via Resend so the message
    appears to come from Verida, not Supabase.

    Always returns success to prevent email enumeration attacks.
    """
    REDIRECT = "https://veridahq.com/reset-password.html"

    try:
        # Generate the Supabase recovery magic link server-side.
        # This gives us the exact URL to embed in our own email.
        link_response = supabase_admin.auth.admin.generate_link({
            "type": "recovery",
            "email": request.email,
            "options": {"redirect_to": REDIRECT},
        })

        action_link = link_response.properties.action_link

        # Send our own branded email with that link.
        sent = await send_password_reset_email(request.email, action_link)

        if not sent:
            # Fallback: let Supabase send its default email so the user
            # is not left completely without a reset path.
            logger.warning("Resend unavailable — falling back to Supabase email")
            supabase.auth.reset_password_email(
                request.email,
                options={"redirect_to": REDIRECT},
            )

    except Exception as e:
        logger.error(f"Password reset error: {e}")
        # Intentionally swallowed — always return the same response

    return {"message": "If that email address is registered, a password reset link has been sent."}


# ---------------------------------------------------------------------------
# GET /client-config  (public — returns only safe, non-secret values)
# ---------------------------------------------------------------------------
@router.get("/client-config")
async def client_config():
    """
    Return the public Supabase URL and anon key for frontend PKCE flows.
    The anon key is intentionally public (enforced by Supabase RLS).
    """
    return {
        "supabase_url": settings.supabase_url,
        "supabase_anon_key": settings.supabase_key,
    }


# ---------------------------------------------------------------------------
# POST /update-password
# ---------------------------------------------------------------------------
@router.post("/update-password")
async def update_password(
    request: PasswordUpdateRequest,
    auth_data: dict = Depends(get_current_user),
):
    """
    Update the password for the currently authenticated user.

    Requires a valid access token (typically obtained after clicking a reset link).
    """
    try:
        user_id = auth_data["user"].id
        supabase_admin.auth.admin.update_user_by_id(user_id, {"password": request.password})
        logger.info(f"Password updated for user: {auth_data['user'].email}")
        return {"message": "Password updated successfully"}
    except Exception as e:
        logger.error(f"Password update error: {e}")
        raise HTTPException(status_code=400, detail="Failed to update password")


# ---------------------------------------------------------------------------
# PATCH /profile — update name (and optionally password)
# ---------------------------------------------------------------------------
@router.patch("/profile")
async def update_profile(
    request: dict,
    auth_data: dict = Depends(get_current_user),
):
    """Update the current user's full_name and/or password."""
    from pydantic import BaseModel
    user = auth_data["user"]

    full_name = request.get("full_name")
    password = request.get("password")

    if full_name:
        supabase_admin.table("profiles").update({"full_name": full_name}).eq("id", user.id).execute()

    if password:
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        supabase_admin.auth.admin.update_user_by_id(user.id, {"password": password})

    return {"message": "Profile updated successfully"}


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------
@router.get("/me", response_model=dict)
async def get_me(auth_data: dict = Depends(get_current_user)):
    """
    Get the current user's profile including their organisation.

    Returns profile data and the associated organisation object.
    """
    user = auth_data["user"]

    profile_response = supabase_admin.table("profiles").select(
        "*, organizations(*)"
    ).eq("id", user.id).single().execute()

    if not profile_response.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = profile_response.data

    return {
        "id": user.id,
        "email": user.email,
        "full_name": profile.get("full_name"),
        "role": profile.get("role"),
        "organization_id": profile.get("organization_id"),
        "organization": profile.get("organizations"),
        "avatar_url": profile.get("avatar_url"),
        "created_at": profile.get("created_at"),
    }
