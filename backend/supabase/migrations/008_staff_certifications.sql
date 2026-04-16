-- Migration 008: Staff certifications tracking
-- Tracks three mandatory NDIS certifications per staff member:
--   worker_screening  — NDIS Worker Screening Check (5-year validity, state-issued)
--   first_aid         — First Aid / CPR Certificate (typically 3 years)
--   ndis_orientation  — NDIS Worker Orientation Module (once-off)

CREATE TABLE IF NOT EXISTS staff_certifications (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id       UUID        NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    organization_id  UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    cert_type        TEXT        NOT NULL CHECK (cert_type IN ('worker_screening', 'first_aid', 'ndis_orientation')),
    issued_date      DATE,
    expiry_date      DATE,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (profile_id, cert_type)
);

CREATE INDEX IF NOT EXISTS idx_staff_certs_profile   ON staff_certifications (profile_id);
CREATE INDEX IF NOT EXISTS idx_staff_certs_org       ON staff_certifications (organization_id);
CREATE INDEX IF NOT EXISTS idx_staff_certs_expiry    ON staff_certifications (expiry_date) WHERE expiry_date IS NOT NULL;

-- updated_at trigger (reuse the same pattern as other tables)
CREATE OR REPLACE FUNCTION update_staff_certifications_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_staff_certifications_updated_at ON staff_certifications;
CREATE TRIGGER trg_staff_certifications_updated_at
    BEFORE UPDATE ON staff_certifications
    FOR EACH ROW EXECUTE FUNCTION update_staff_certifications_updated_at();

-- RLS
ALTER TABLE staff_certifications ENABLE ROW LEVEL SECURITY;

-- Any org member can read their org's certs
CREATE POLICY "org_members_select_certs"
    ON staff_certifications FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

-- Only owners and admins can insert/update/delete
CREATE POLICY "org_admins_write_certs"
    ON staff_certifications FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM profiles
            WHERE id = auth.uid() AND role IN ('owner', 'admin')
        )
    );
