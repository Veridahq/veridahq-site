-- =============================================================================
-- Verida Compliance Platform — Migration 007: External Integrations
-- =============================================================================
-- Adds:
--   integrations   — OAuth token store for cloud-storage connectors
--   documents cols — source, external_provider, external_id, external_url, integration_id
-- =============================================================================

-- =============================================================================
-- TABLE: integrations
-- =============================================================================
CREATE TABLE IF NOT EXISTS integrations (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider         TEXT        NOT NULL,   -- 'microsoft' | 'google' | 'dropbox' | 'box'
    -- TODO: encrypt access_token and refresh_token at rest before GA
    access_token     TEXT,
    refresh_token    TEXT,
    expires_at       TIMESTAMPTZ,
    account_email    TEXT,
    root_folders     JSONB       NOT NULL DEFAULT '[]'::jsonb,
    sync_status      TEXT        NOT NULL DEFAULT 'idle',  -- 'idle' | 'syncing' | 'error'
    last_sync_at     TIMESTAMPTZ,
    last_error       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One active integration per provider per org
CREATE UNIQUE INDEX IF NOT EXISTS integrations_org_provider_uidx
    ON integrations (organization_id, provider);

-- =============================================================================
-- ADD COLUMNS TO: documents
-- =============================================================================
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS source            TEXT NOT NULL DEFAULT 'upload',
    ADD COLUMN IF NOT EXISTS external_provider TEXT,
    ADD COLUMN IF NOT EXISTS external_id       TEXT,
    ADD COLUMN IF NOT EXISTS external_url      TEXT,
    ADD COLUMN IF NOT EXISTS integration_id    UUID REFERENCES integrations(id) ON DELETE SET NULL;

-- Fast dedup lookup during sync
CREATE INDEX IF NOT EXISTS documents_external_idx
    ON documents (external_provider, external_id)
    WHERE external_provider IS NOT NULL;

-- =============================================================================
-- RLS: integrations
-- =============================================================================
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;

-- Any org member can read their org's integrations
CREATE POLICY "integrations_select_org"
    ON integrations FOR SELECT
    USING (organization_id = get_user_org_id());

-- Backend (service role) inserts via upsert — also allow org members
CREATE POLICY "integrations_insert_org"
    ON integrations FOR INSERT
    WITH CHECK (organization_id = get_user_org_id());

-- Org admins/owners can update (token refresh, sync status)
CREATE POLICY "integrations_update_org"
    ON integrations FOR UPDATE
    USING (organization_id = get_user_org_id());

-- Org admins/owners can disconnect
CREATE POLICY "integrations_delete_org"
    ON integrations FOR DELETE
    USING (
        organization_id = get_user_org_id()
        AND get_user_role() IN ('owner', 'admin')
    );

-- =============================================================================
-- updated_at trigger for integrations
-- =============================================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'integrations_set_updated_at'
          AND tgrelid = 'integrations'::regclass
    ) THEN
        CREATE TRIGGER integrations_set_updated_at
            BEFORE UPDATE ON integrations
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at();
    END IF;
END;
$$;
