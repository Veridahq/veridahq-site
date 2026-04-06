-- =============================================================================
-- Verida Compliance Platform — Migration 003: Performance Indexes
-- =============================================================================
-- Creates indexes to optimise common query patterns:
--   - Organisation-scoped queries (most common access pattern)
--   - Status/type filtering for documents and jobs
--   - Composite indexes for dashboard aggregation queries
-- =============================================================================

-- =============================================================================
-- profiles indexes
-- =============================================================================

-- Look up profiles by organisation (used in member listings and admin checks)
CREATE INDEX IF NOT EXISTS idx_profiles_organization_id
    ON profiles(organization_id);

-- Look up profiles by email (used in auth flows and user lookup)
CREATE INDEX IF NOT EXISTS idx_profiles_email
    ON profiles(email);

-- =============================================================================
-- organizations indexes
-- =============================================================================

-- Look up organisations by NDIS registration number (admin lookups)
CREATE INDEX IF NOT EXISTS idx_organizations_ndis_registration_number
    ON organizations(ndis_registration_number)
    WHERE ndis_registration_number IS NOT NULL;

-- Filter organisations by plan tier (billing/feature flag queries)
CREATE INDEX IF NOT EXISTS idx_organizations_plan_tier
    ON organizations(plan_tier);

-- =============================================================================
-- documents indexes
-- =============================================================================

-- Primary org-scoped document lookup
CREATE INDEX IF NOT EXISTS idx_documents_organization_id
    ON documents(organization_id);

-- Filter documents by processing status (e.g., find pending/failed docs)
CREATE INDEX IF NOT EXISTS idx_documents_processing_status
    ON documents(processing_status);

-- Filter documents by type (e.g., list all incident registers)
CREATE INDEX IF NOT EXISTS idx_documents_document_type
    ON documents(document_type)
    WHERE document_type IS NOT NULL;

-- Composite index for paginated org document listing sorted by date
CREATE INDEX IF NOT EXISTS idx_documents_organization_created_at
    ON documents(organization_id, created_at DESC);

-- =============================================================================
-- compliance_scores indexes
-- =============================================================================

-- Primary org-scoped scores lookup
CREATE INDEX IF NOT EXISTS idx_compliance_scores_organization_id
    ON compliance_scores(organization_id);

-- Look up scores for a specific standard
CREATE INDEX IF NOT EXISTS idx_compliance_scores_standard_id
    ON compliance_scores(standard_id);

-- Composite index for org+standard queries (most common compliance fetch pattern)
CREATE INDEX IF NOT EXISTS idx_compliance_scores_org_standard
    ON compliance_scores(organization_id, standard_id);

-- Look up scores associated with a specific document
CREATE INDEX IF NOT EXISTS idx_compliance_scores_document_id
    ON compliance_scores(document_id)
    WHERE document_id IS NOT NULL;

-- Filter by status for dashboard aggregations
CREATE INDEX IF NOT EXISTS idx_compliance_scores_status
    ON compliance_scores(organization_id, status);

-- =============================================================================
-- gap_analysis indexes
-- =============================================================================

-- Primary org-scoped gaps lookup
CREATE INDEX IF NOT EXISTS idx_gap_analysis_organization_id
    ON gap_analysis(organization_id);

-- Filter gaps by risk level
CREATE INDEX IF NOT EXISTS idx_gap_analysis_risk_level
    ON gap_analysis(risk_level);

-- Filter gaps by resolved state (most views show unresolved gaps)
CREATE INDEX IF NOT EXISTS idx_gap_analysis_resolved
    ON gap_analysis(resolved);

-- Composite index for the gaps dashboard view: org + resolved + risk level
CREATE INDEX IF NOT EXISTS idx_gap_analysis_org_resolved_risk
    ON gap_analysis(organization_id, resolved, risk_level);

-- Look up gaps by standard
CREATE INDEX IF NOT EXISTS idx_gap_analysis_standard_id
    ON gap_analysis(standard_id);

-- =============================================================================
-- analysis_jobs indexes
-- =============================================================================

-- Primary org-scoped jobs lookup
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_organization_id
    ON analysis_jobs(organization_id);

-- Filter jobs by status (e.g., find all queued/processing jobs)
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status
    ON analysis_jobs(status);

-- Look up jobs associated with a specific document
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_document_id
    ON analysis_jobs(document_id)
    WHERE document_id IS NOT NULL;

-- Composite index for org + status queries (common in job polling)
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_org_status
    ON analysis_jobs(organization_id, status);
