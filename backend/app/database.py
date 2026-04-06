"""Supabase client initialization and database utilities."""

import logging
from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anon client
# Used for auth operations that need to respect Row Level Security.
# JWT tokens from end users are passed to this client to enforce RLS.
# ---------------------------------------------------------------------------
supabase: Client = create_client(settings.supabase_url, settings.supabase_key)

# ---------------------------------------------------------------------------
# Service role client
# Used for all backend/admin operations that must bypass RLS.
# NEVER expose this client or its key to end users.
# ---------------------------------------------------------------------------
supabase_admin: Client = create_client(
    settings.supabase_url, settings.supabase_service_key
)

logger.info("Supabase clients initialised")


def get_client() -> Client:
    """Return the anon Supabase client (respects RLS)."""
    return supabase


def get_admin_client() -> Client:
    """Return the service role Supabase client (bypasses RLS)."""
    return supabase_admin
