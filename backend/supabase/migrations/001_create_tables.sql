-- =============================================================================
-- Verida Compliance Platform — Migration 001: Create Tables
-- =============================================================================
-- Creates the core schema for the NDIS compliance management platform.
-- Run this migration first before any other migrations.
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- TRIGGER FUNCTION: auto-update updated_at on row changes
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- TABLE: organizations
-- Represents an NDIS service provider organisation using Verida.
-- =============================================================================
CREATE TABLE IF NOT EXISTS organizations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL,
    -- Australian Business Number
    abn                     TEXT,
    -- NDIS Commission registration number
    ndis_registration_number TEXT,
    -- Whether the provider is registered with the NDIS Commission
    registration_type       TEXT DEFAULT 'registered'
                                CHECK (registration_type IN ('registered', 'unregistered')),
    -- Subscription tier
    plan_tier               TEXT DEFAULT 'essentials'
                                CHECK (plan_tier IN ('essentials', 'growth', 'scale')),
    address                 TEXT,
    phone                   TEXT,
    email                   TEXT,
    website                 TEXT,
    -- Next scheduled NDIS audit date
    audit_date              DATE,
    -- Type of audit (e.g., 'certification', 'verification', 'mid_term_review')
    audit_type              TEXT,
    -- Arbitrary key-value settings for the organisation
    settings                JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: profiles
-- Extends auth.users with application-specific user data.
-- One profile per Supabase auth user.
-- =============================================================================
CREATE TABLE IF NOT EXISTS profiles (
    id                      UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email                   TEXT NOT NULL,
    full_name               TEXT,
    -- Role within the organisation
    role                    TEXT DEFAULT 'member'
                                CHECK (role IN ('owner', 'admin', 'member')),
    -- Nullable on initial signup; assigned when user creates or joins an org
    organization_id         UUID REFERENCES organizations(id) ON DELETE SET NULL,
    avatar_url              TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: documents
-- Stores uploaded compliance documents and their processing state.
-- =============================================================================
CREATE TABLE IF NOT EXISTS documents (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id         UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    -- The user who uploaded this document
    uploaded_by             UUID REFERENCES profiles(id) ON DELETE SET NULL,
    -- Unique storage filename (includes org_id prefix)
    filename                TEXT NOT NULL,
    -- Original filename as uploaded by the user
    original_filename       TEXT NOT NULL,
    file_size               INTEGER,
    mime_type               TEXT,
    -- Path in Supabase Storage bucket
    storage_path            TEXT NOT NULL,
    -- AI classification result (one of the DocumentTypeEnum values)
    document_type           TEXT,
    -- Full extracted text content for AI analysis
    extracted_text          TEXT,
    -- Processing pipeline state
    processing_status       TEXT DEFAULT 'pending'
                                CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')),
    -- Error message if processing failed
    processing_error        TEXT,
    -- Additional metadata (e.g., classification confidence, page count)
    metadata                JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: ndis_standards
-- Reference data: NDIS Practice Standards and their quality indicators.
-- Seeded once via seed.sql; not modified by users.
-- =============================================================================
CREATE TABLE IF NOT EXISTS ndis_standards (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Hierarchical standard number, e.g. '1.1', '2.3', '4.1'
    standard_number         TEXT NOT NULL UNIQUE,
    -- Top-level grouping of the standard
    category                TEXT NOT NULL
                                CHECK (category IN (
                                    'governance',
                                    'operational_management',
                                    'provision_of_supports',
                                    'support_provision_environment'
                                )),
    title                   TEXT NOT NULL,
    description             TEXT NOT NULL,
    -- Array of measurable quality indicators for this standard
    quality_indicators      TEXT[] DEFAULT '{}',
    -- Soft-delete flag; inactive standards are excluded from analysis
    is_active               BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: compliance_scores
-- Stores AI-generated compliance scores per organisation per standard.
-- Unique on (organization_id, document_id, standard_id) to allow upserts.
-- =============================================================================
CREATE TABLE IF NOT EXISTS compliance_scores (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id         UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    -- The specific document that evidence was found in
    document_id             UUID REFERENCES documents(id) ON DELETE SET NULL,
    standard_id             UUID NOT NULL REFERENCES ndis_standards(id),
    -- Numeric compliance score 0–100
    score                   NUMERIC(5,2) CHECK (score >= 0 AND score <= 100),
    -- Categorical compliance status
    status                  TEXT NOT NULL DEFAULT 'not_assessed'
                                CHECK (status IN (
                                    'compliant',
                                    'needs_attention',
                                    'non_compliant',
                                    'not_assessed'
                                )),
    -- Specific evidence phrases found in the document
    evidence_found          TEXT[] DEFAULT '{}',
    -- AI auditor's summary notes
    analysis_notes          TEXT,
    -- AI confidence in the analysis result (0.0–1.0)
    confidence              NUMERIC(3,2) DEFAULT 0.0,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    -- Prevent duplicate scores for the same document+standard combination
    UNIQUE(organization_id, document_id, standard_id)
);

-- =============================================================================
-- TABLE: gap_analysis
-- Stores identified compliance gaps with remediation guidance.
-- Generated by AI analysis; can be resolved by users.
-- =============================================================================
CREATE TABLE IF NOT EXISTS gap_analysis (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id         UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    standard_id             UUID NOT NULL REFERENCES ndis_standards(id),
    -- Document where the gap was identified (nullable for org-level gaps)
    document_id             UUID REFERENCES documents(id) ON DELETE SET NULL,
    -- Priority level of the gap
    risk_level              TEXT NOT NULL
                                CHECK (risk_level IN ('critical', 'high', 'medium', 'low')),
    -- Description of what is missing or non-compliant
    gap_description         TEXT NOT NULL,
    -- Specific action required to remediate the gap
    remediation_action      TEXT NOT NULL,
    -- Display ordering (lower = higher priority)
    priority_order          INTEGER,
    -- Whether the gap has been actioned and resolved
    resolved                BOOLEAN DEFAULT FALSE,
    resolved_at             TIMESTAMPTZ,
    resolved_by             UUID REFERENCES profiles(id),
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TABLE: analysis_jobs
-- Tracks async background jobs for document processing and compliance scans.
-- =============================================================================
CREATE TABLE IF NOT EXISTS analysis_jobs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id         UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    -- Associated document (null for org-wide scans)
    document_id             UUID REFERENCES documents(id) ON DELETE SET NULL,
    -- Type of analysis being performed
    job_type                TEXT NOT NULL
                                CHECK (job_type IN (
                                    'document_classification',
                                    'compliance_analysis',
                                    'full_scan'
                                )),
    -- Current job state
    status                  TEXT NOT NULL DEFAULT 'queued'
                                CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    -- Completion percentage (0–100)
    progress                INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    -- Error details if job failed
    error_message           TEXT,
    -- JSON result payload from the completed job
    result                  JSONB DEFAULT '{}',
    started_at              TIMESTAMPTZ,
    completed_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TRIGGERS: auto-update updated_at columns
-- =============================================================================
CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_compliance_scores_updated_at
    BEFORE UPDATE ON compliance_scores
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_gap_analysis_updated_at
    BEFORE UPDATE ON gap_analysis
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analysis_jobs_updated_at
    BEFORE UPDATE ON analysis_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
