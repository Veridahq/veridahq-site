-- =============================================================================
-- Migration 007: External storage integrations (SharePoint/OneDrive/Drive/etc)
--
-- Changes:
--   1. New `integrations` table — stores OAuth connections per organisation
--      (access/refresh tokens, selected root folders, sync status).
--   2. Add source tracking columns to `documents` so we can tell manual uploads
--      apart from files ingested via an integration, and link back to the
--      external source for dedup and deep-linking.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. integrations table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS integrations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL CHECK (provider IN ('microsoft', 'google', 'dropbox', 'box')),
    account_email   TEXT,
    account_name    TEXT,

    -- OAuth tokens (plaintext for MVP — TODO: encrypt at rest with pgcrypto or KMS)
    access_token    TEXT,
    refresh_token   TEXT,
    expires_at      TIMESTAMPTZ,
    scope           TEXT,

    -- Provider-specific root drive identifier (e.g. OneDrive drive id)
    drive_id        TEXT,

    -- User-selected folders to include in the sync — array of
    -- { id, name, path } objects returned by the connector's list_folders.
    root_folders    JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Sync state
    sync_status     TEXT NOT NULL DEFAULT 'idle'
                    CHECK (sync_status IN ('idle', 'syncing', 'error')),
    last_sync_at    TIMESTAMPTZ,
    last_error      TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_integrations_org_provider
    ON integrations (organization_id, provider);

CREATE INDEX IF NOT EXISTS idx_integrations_sync_status
    ON integrations (sync_status)
    WHERE sync_status <> 'idle';

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_integrations_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS integrations_updated_at ON integrations;
CREATE TRIGGER integrations_updated_at
    BEFORE UPDATE ON integrations
    FOR EACH ROW
    EXECUTE FUNCTION update_integrations_timestamp();


-- -----------------------------------------------------------------------------
-- 2. Row-level security — match the rest of the multi-tenant tables
-- -----------------------------------------------------------------------------
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view integrations in their org" ON integrations;
CREATE POLICY "Users can view integrations in their org"
    ON integrations FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

DROP POLICY IF EXISTS "Admins can manage integrations in their org" ON integrations;
CREATE POLICY "Admins can manage integrations in their org"
    ON integrations FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM profiles
            WHERE id = auth.uid()
              AND role IN ('owner', 'admin')
        )
    );


-- -----------------------------------------------------------------------------
-- 3. Document source tracking
-- -----------------------------------------------------------------------------
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS source              TEXT NOT NULL DEFAULT 'upload',
    ADD COLUMN IF NOT EXISTS external_provider   TEXT,
    ADD COLUMN IF NOT EXISTS external_id         TEXT,
    ADD COLUMN IF NOT EXISTS external_url        TEXT,
    ADD COLUMN IF NOT EXISTS integration_id      UUID REFERENCES integrations(id) ON DELETE SET NULL;

COMMENT ON COLUMN documents.source IS
    'Where this document came from: "upload" (manual) or "integration" (ingested via a connected provider).';

COMMENT ON COLUMN documents.external_provider IS
    'Provider key when source=integration: microsoft | google | dropbox | box';

COMMENT ON COLUMN documents.external_id IS
    'Stable provider-side file identifier, used for dedup on re-sync.';

COMMENT ON COLUMN documents.external_url IS
    'Deep link back to the file in the source provider UI.';

-- Index for dedup lookups during sync
CREATE INDEX IF NOT EXISTS idx_documents_external
    ON documents (external_provider, external_id)
    WHERE external_id IS NOT NULL;

-- Index for "show me all synced docs" queries
CREATE INDEX IF NOT EXISTS idx_documents_source
    ON documents (organization_id, source);
