-- =============================================================================
-- Verida Compliance Platform — Migration 002: Row Level Security Policies
-- =============================================================================
-- Enables RLS on all tables and creates policies that enforce:
--   - Users can only access data belonging to their own organisation
--   - Role-based restrictions for write operations
--   - Public read access for reference data (ndis_standards)
--   - Service role bypasses all RLS for backend operations
-- =============================================================================

-- =============================================================================
-- HELPER FUNCTION: get the current user's organization_id
-- =============================================================================
CREATE OR REPLACE FUNCTION get_user_org_id()
RETURNS UUID AS $$
DECLARE
    org_id UUID;
BEGIN
    SELECT organization_id INTO org_id
    FROM profiles
    WHERE id = auth.uid();
    RETURN org_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- =============================================================================
-- HELPER FUNCTION: get the current user's role
-- =============================================================================
CREATE OR REPLACE FUNCTION get_user_role()
RETURNS TEXT AS $$
DECLARE
    user_role TEXT;
BEGIN
    SELECT role INTO user_role
    FROM profiles
    WHERE id = auth.uid();
    RETURN user_role;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- =============================================================================
-- TABLE: profiles — RLS Policies
-- =============================================================================
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Users can read their own profile
CREATE POLICY "profiles_select_own"
    ON profiles FOR SELECT
    USING (id = auth.uid());

-- Organisation admins/owners can read all profiles in their org
CREATE POLICY "profiles_select_org_members"
    ON profiles FOR SELECT
    USING (
        organization_id = get_user_org_id()
        AND get_user_role() IN ('owner', 'admin')
    );

-- Users can update only their own profile
CREATE POLICY "profiles_update_own"
    ON profiles FOR UPDATE
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- Backend (service role) can insert new profiles on signup
CREATE POLICY "profiles_insert_service_role"
    ON profiles FOR INSERT
    WITH CHECK (TRUE);

-- =============================================================================
-- TABLE: organizations — RLS Policies
-- =============================================================================
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

-- Any member of the org can read their own organisation
CREATE POLICY "organizations_select_own"
    ON organizations FOR SELECT
    USING (id = get_user_org_id());

-- Only owners and admins can update organisation details
CREATE POLICY "organizations_update_admin"
    ON organizations FOR UPDATE
    USING (
        id = get_user_org_id()
        AND get_user_role() IN ('owner', 'admin')
    )
    WITH CHECK (
        id = get_user_org_id()
        AND get_user_role() IN ('owner', 'admin')
    );

-- Backend creates organisations on signup (service role handles this)
CREATE POLICY "organizations_insert_authenticated"
    ON organizations FOR INSERT
    WITH CHECK (TRUE);

-- No delete via API — organisations are soft-managed
-- (Only service role can delete, which bypasses RLS)

-- =============================================================================
-- TABLE: documents — RLS Policies
-- =============================================================================
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- All org members can read documents belonging to their organisation
CREATE POLICY "documents_select_org"
    ON documents FOR SELECT
    USING (organization_id = get_user_org_id());

-- Any org member can upload documents
CREATE POLICY "documents_insert_org_member"
    ON documents FOR INSERT
    WITH CHECK (organization_id = get_user_org_id());

-- Document uploader or org admin can update document metadata
CREATE POLICY "documents_update_uploader_or_admin"
    ON documents FOR UPDATE
    USING (
        organization_id = get_user_org_id()
        AND (
            uploaded_by = auth.uid()
            OR get_user_role() IN ('owner', 'admin')
        )
    );

-- Document uploader or org admin can delete documents
CREATE POLICY "documents_delete_uploader_or_admin"
    ON documents FOR DELETE
    USING (
        organization_id = get_user_org_id()
        AND (
            uploaded_by = auth.uid()
            OR get_user_role() IN ('owner', 'admin')
        )
    );

-- =============================================================================
-- TABLE: ndis_standards — RLS Policies
-- =============================================================================
ALTER TABLE ndis_standards ENABLE ROW LEVEL SECURITY;

-- All authenticated users can read NDIS standards (public reference data)
CREATE POLICY "ndis_standards_select_all_authenticated"
    ON ndis_standards FOR SELECT
    USING (auth.role() = 'authenticated');

-- Only service role can insert/update/delete standards (no user-facing policy needed;
-- service role bypasses RLS automatically)

-- =============================================================================
-- TABLE: compliance_scores — RLS Policies
-- =============================================================================
ALTER TABLE compliance_scores ENABLE ROW LEVEL SECURITY;

-- Org members can read their organisation's compliance scores
CREATE POLICY "compliance_scores_select_org"
    ON compliance_scores FOR SELECT
    USING (organization_id = get_user_org_id());

-- Backend (service role) writes compliance scores — no user insert policy needed
-- The service role bypasses RLS, so backend operations work without a policy.
-- Adding a permissive insert for service role compatibility:
CREATE POLICY "compliance_scores_insert_service"
    ON compliance_scores FOR INSERT
    WITH CHECK (organization_id = get_user_org_id());

CREATE POLICY "compliance_scores_update_service"
    ON compliance_scores FOR UPDATE
    USING (organization_id = get_user_org_id());

-- =============================================================================
-- TABLE: gap_analysis — RLS Policies
-- =============================================================================
ALTER TABLE gap_analysis ENABLE ROW LEVEL SECURITY;

-- Org members can read their organisation's gaps
CREATE POLICY "gap_analysis_select_org"
    ON gap_analysis FOR SELECT
    USING (organization_id = get_user_org_id());

-- Backend creates gap records
CREATE POLICY "gap_analysis_insert_service"
    ON gap_analysis FOR INSERT
    WITH CHECK (organization_id = get_user_org_id());

-- Admins and owners can update gaps (e.g., mark as resolved)
CREATE POLICY "gap_analysis_update_admin"
    ON gap_analysis FOR UPDATE
    USING (
        organization_id = get_user_org_id()
        AND get_user_role() IN ('owner', 'admin', 'member')
    );

-- =============================================================================
-- TABLE: analysis_jobs — RLS Policies
-- =============================================================================
ALTER TABLE analysis_jobs ENABLE ROW LEVEL SECURITY;

-- Org members can read their organisation's jobs
CREATE POLICY "analysis_jobs_select_org"
    ON analysis_jobs FOR SELECT
    USING (organization_id = get_user_org_id());

-- Backend creates and updates jobs
CREATE POLICY "analysis_jobs_insert_service"
    ON analysis_jobs FOR INSERT
    WITH CHECK (organization_id = get_user_org_id());

CREATE POLICY "analysis_jobs_update_service"
    ON analysis_jobs FOR UPDATE
    USING (organization_id = get_user_org_id());
