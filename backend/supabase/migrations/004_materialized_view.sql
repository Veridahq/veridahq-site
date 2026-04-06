-- =============================================================================
-- Verida Compliance Platform — Migration 004: Dashboard Materialized View
-- =============================================================================
-- Creates a materialized view that pre-aggregates dashboard statistics per
-- organisation. This avoids expensive multi-table joins on every dashboard
-- page load. The view is refreshed after each compliance scan completes.
-- =============================================================================

-- =============================================================================
-- MATERIALIZED VIEW: dashboard_summary
-- Aggregates organisation-level compliance statistics for the dashboard.
-- =============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_summary AS
SELECT
    o.id                                                            AS organization_id,
    o.name                                                          AS organization_name,
    o.plan_tier,
    o.audit_date,

    -- Document counts
    COUNT(DISTINCT d.id)                                            AS total_documents,

    -- Overall compliance score (average of all scored standards)
    ROUND(AVG(cs.score), 2)                                         AS overall_compliance_score,

    -- Standards by compliance status
    COUNT(DISTINCT CASE WHEN cs.status = 'compliant'
        THEN cs.standard_id END)                                    AS compliant_standards,
    COUNT(DISTINCT CASE WHEN cs.status = 'needs_attention'
        THEN cs.standard_id END)                                    AS needs_attention_standards,
    COUNT(DISTINCT CASE WHEN cs.status = 'non_compliant'
        THEN cs.standard_id END)                                    AS non_compliant_standards,
    -- Not assessed = total active standards minus those with any score
    (
        SELECT COUNT(*) FROM ndis_standards WHERE is_active = TRUE
    ) - COUNT(DISTINCT cs.standard_id)                              AS not_assessed_standards,

    -- Gap counts by risk level (unresolved only)
    COUNT(DISTINCT CASE WHEN ga.resolved = FALSE
        AND ga.risk_level = 'critical' THEN ga.id END)              AS critical_gaps,
    COUNT(DISTINCT CASE WHEN ga.resolved = FALSE
        AND ga.risk_level = 'high' THEN ga.id END)                  AS high_gaps,
    COUNT(DISTINCT CASE WHEN ga.resolved = FALSE
        AND ga.risk_level = 'medium' THEN ga.id END)                AS medium_gaps,
    COUNT(DISTINCT CASE WHEN ga.resolved = FALSE
        AND ga.risk_level = 'low' THEN ga.id END)                   AS low_gaps,

    -- Documents awaiting processing
    COUNT(DISTINCT CASE WHEN d.processing_status = 'pending'
        THEN d.id END)                                              AS pending_documents,

    -- Timestamp of last refresh
    NOW()                                                           AS last_refreshed

FROM organizations o
LEFT JOIN documents d
    ON d.organization_id = o.id
LEFT JOIN compliance_scores cs
    ON cs.organization_id = o.id
LEFT JOIN gap_analysis ga
    ON ga.organization_id = o.id
GROUP BY
    o.id,
    o.name,
    o.plan_tier,
    o.audit_date;

-- Unique index required for CONCURRENT refresh (non-blocking production refresh)
CREATE UNIQUE INDEX IF NOT EXISTS dashboard_summary_org_id_idx
    ON dashboard_summary(organization_id);

-- =============================================================================
-- FUNCTION: refresh_dashboard_summary
-- Called by the backend after each compliance scan completes.
-- Uses CONCURRENTLY to avoid locking reads during refresh.
-- =============================================================================
CREATE OR REPLACE FUNCTION refresh_dashboard_summary()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_summary;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================
-- GRANT: allow authenticated users to read the materialized view
-- =============================================================================
GRANT SELECT ON dashboard_summary TO authenticated;
GRANT SELECT ON dashboard_summary TO anon;

-- =============================================================================
-- NOTE: The service role can call refresh_dashboard_summary() via supabase.rpc()
-- Initial population: run SELECT refresh_dashboard_summary(); after seeding data.
-- =============================================================================
