-- =============================================================================
-- Verida Compliance Platform — Migration 005: Client-Level Compliance
-- =============================================================================
-- Creates tables for client profiles, client-specific document tracking,
-- and client-level compliance checks.
-- =============================================================================

-- =============================================================================
-- TABLE: clients
-- Represents NDIS participant profiles within an organization.
-- =============================================================================
CREATE TABLE IF NOT EXISTS clients (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id             UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Core client info
    first_name                  VARCHAR(255) NOT NULL,
    last_name                   VARCHAR(255) NOT NULL,
    date_of_birth               DATE NOT NULL,
    ndis_participant_number     VARCHAR(50) NOT NULL,

    -- Contact info
    email                       VARCHAR(255),
    phone_number                VARCHAR(20),
    address_line1               VARCHAR(255),
    address_line2               VARCHAR(255),
    suburb                      VARCHAR(100),
    state                       VARCHAR(10),
    postcode                    VARCHAR(10),
    country                     VARCHAR(100),

    -- Plan details
    current_plan_start_date     DATE,
    current_plan_end_date       DATE,
    current_plan_budget_amount  DECIMAL(12, 2),
    funded_support_categories   JSONB DEFAULT '[]',

    -- Status and metadata
    status                      VARCHAR(50) DEFAULT 'active'
                                    CHECK (status IN ('active', 'inactive', 'exited')),
    requires_behaviour_support  BOOLEAN DEFAULT FALSE,
    primary_contact_name        VARCHAR(255),
    primary_contact_relationship VARCHAR(100),
    primary_contact_email       VARCHAR(255),
    primary_contact_phone       VARCHAR(20),

    -- Compliance flags
    is_flagged_for_review       BOOLEAN DEFAULT FALSE,
    review_notes                TEXT,

    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),
    deleted_at                  TIMESTAMPTZ
);

CREATE TRIGGER update_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_clients_organization_id ON clients(organization_id);
CREATE INDEX idx_clients_ndis_participant_number ON clients(ndis_participant_number);
CREATE INDEX idx_clients_status ON clients(status);
CREATE INDEX idx_clients_created_at ON clients(created_at DESC);

-- =============================================================================
-- TABLE: client_documents
-- Links documents to clients with NDIS-specific categorization.
-- =============================================================================
CREATE TABLE IF NOT EXISTS client_documents (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id                   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    organization_id             UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    document_id                 UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Document categorization (NDIS-specific)
    document_type               VARCHAR(100) NOT NULL CHECK (document_type IN (
        'service_agreement',
        'consent_form',
        'individual_support_plan',
        'risk_assessment',
        'progress_notes',
        'incident_report',
        'behaviour_support_plan',
        'goals_plan',
        'financial_statement',
        'funding_agreement',
        'communication_plan',
        'transition_plan',
        'other'
    )),

    -- Document dating
    document_date               DATE,
    document_version            VARCHAR(50),

    -- Review cycle info
    review_due_date             DATE,
    last_reviewed_date          DATE,
    review_cycle_days           INTEGER,

    -- Status
    is_current                  BOOLEAN DEFAULT TRUE,
    is_required                 BOOLEAN DEFAULT FALSE,
    status                      VARCHAR(50) DEFAULT 'active'
                                    CHECK (status IN ('active', 'superseded', 'void')),

    -- Notes
    notes                       TEXT,

    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER update_client_documents_updated_at
    BEFORE UPDATE ON client_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_client_documents_client_id ON client_documents(client_id);
CREATE INDEX idx_client_documents_organization_id ON client_documents(organization_id);
CREATE INDEX idx_client_documents_document_type ON client_documents(document_type);
CREATE INDEX idx_client_documents_is_current ON client_documents(is_current);
CREATE INDEX idx_client_documents_review_due_date ON client_documents(review_due_date);
CREATE INDEX idx_client_documents_is_required ON client_documents(is_required);

-- =============================================================================
-- TABLE: client_compliance_checks
-- Results of compliance validations for a client.
-- =============================================================================
CREATE TABLE IF NOT EXISTS client_compliance_checks (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id                   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    organization_id             UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Check type
    check_type                  VARCHAR(100) NOT NULL CHECK (check_type IN (
        'document_completeness',
        'document_currency',
        'form_completeness',
        'cross_document_validation',
        'comprehensive'
    )),

    -- Results
    status                      VARCHAR(50) NOT NULL CHECK (status IN ('passed', 'failed', 'warning', 'not_applicable')),
    overall_score               INTEGER CHECK (overall_score >= 0 AND overall_score <= 100),

    -- Details
    findings                    JSONB DEFAULT '[]',

    -- Analysis metadata
    ai_model_used               VARCHAR(100),
    ai_analysis_tokens_used     INTEGER,

    -- Triggering data
    checked_documents           INTEGER DEFAULT 0,
    created_by                  UUID REFERENCES profiles(id) ON DELETE SET NULL,

    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    executed_at                 TIMESTAMPTZ,
    next_check_scheduled_for    TIMESTAMPTZ
);

CREATE TRIGGER update_client_compliance_checks_updated_at
    BEFORE UPDATE ON client_compliance_checks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_client_compliance_checks_client_id ON client_compliance_checks(client_id);
CREATE INDEX idx_client_compliance_checks_organization_id ON client_compliance_checks(organization_id);
CREATE INDEX idx_client_compliance_checks_check_type ON client_compliance_checks(check_type);
CREATE INDEX idx_client_compliance_checks_status ON client_compliance_checks(status);
CREATE INDEX idx_client_compliance_checks_created_at ON client_compliance_checks(created_at DESC);

-- =============================================================================
-- TABLE: document_requirements
-- Defines which documents are required, review cycles, and validation rules.
-- =============================================================================
CREATE TABLE IF NOT EXISTS document_requirements (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id             UUID REFERENCES organizations(id) ON DELETE CASCADE,

    -- Document type definition
    document_type               VARCHAR(100) NOT NULL CHECK (document_type IN (
        'service_agreement',
        'consent_form',
        'individual_support_plan',
        'risk_assessment',
        'progress_notes',
        'incident_report',
        'behaviour_support_plan',
        'goals_plan',
        'financial_statement',
        'funding_agreement',
        'communication_plan',
        'transition_plan',
        'other'
    )),

    -- Requirement rules
    is_mandatory                BOOLEAN DEFAULT FALSE,
    requires_signature          BOOLEAN DEFAULT FALSE,
    requires_approval           BOOLEAN DEFAULT FALSE,
    review_frequency_days       INTEGER,

    -- Validation rules (JSON array of field names or custom rules)
    mandatory_fields            JSONB DEFAULT '[]',
    validation_rules            JSONB DEFAULT '{}',
    linked_document_types       JSONB DEFAULT '[]',
    retention_period_years      INTEGER,

    description                 TEXT,

    created_at                  TIMESTAMPTZ DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, document_type)
);

CREATE TRIGGER update_document_requirements_updated_at
    BEFORE UPDATE ON document_requirements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE INDEX idx_document_requirements_organization_id ON document_requirements(organization_id);
CREATE INDEX idx_document_requirements_document_type ON document_requirements(document_type);

-- =============================================================================
-- RLS POLICIES: clients
-- =============================================================================
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

CREATE POLICY "clients_org_read" ON clients
    FOR SELECT USING (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

CREATE POLICY "clients_org_insert" ON clients
    FOR INSERT WITH CHECK (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

CREATE POLICY "clients_org_update" ON clients
    FOR UPDATE USING (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

CREATE POLICY "clients_org_delete" ON clients
    FOR DELETE USING (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

-- =============================================================================
-- RLS POLICIES: client_documents
-- =============================================================================
ALTER TABLE client_documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "client_documents_org_read" ON client_documents
    FOR SELECT USING (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

CREATE POLICY "client_documents_org_insert" ON client_documents
    FOR INSERT WITH CHECK (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

CREATE POLICY "client_documents_org_update" ON client_documents
    FOR UPDATE USING (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

CREATE POLICY "client_documents_org_delete" ON client_documents
    FOR DELETE USING (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

-- =============================================================================
-- RLS POLICIES: client_compliance_checks
-- =============================================================================
ALTER TABLE client_compliance_checks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "client_compliance_checks_org_read" ON client_compliance_checks
    FOR SELECT USING (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

CREATE POLICY "client_compliance_checks_org_insert" ON client_compliance_checks
    FOR INSERT WITH CHECK (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

CREATE POLICY "client_compliance_checks_org_update" ON client_compliance_checks
    FOR UPDATE USING (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

CREATE POLICY "client_compliance_checks_org_delete" ON client_compliance_checks
    FOR DELETE USING (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

-- =============================================================================
-- RLS POLICIES: document_requirements
-- =============================================================================
ALTER TABLE document_requirements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "document_requirements_read" ON document_requirements
    FOR SELECT USING (
        organization_id IS NULL OR organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

CREATE POLICY "document_requirements_insert" ON document_requirements
    FOR INSERT WITH CHECK (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

CREATE POLICY "document_requirements_update" ON document_requirements
    FOR UPDATE USING (
        organization_id = (
            SELECT organization_id FROM profiles WHERE id = auth.uid()
        )
    );

-- =============================================================================
-- SEED: Default Document Requirements (NDIS Standards)
-- =============================================================================
INSERT INTO document_requirements (
    organization_id,
    document_type,
    is_mandatory,
    requires_signature,
    review_frequency_days,
    description
) VALUES
    (NULL, 'service_agreement', TRUE, TRUE, 365, 'Core NDIS requirement: Agreement between participant and provider outlining support to be provided'),
    (NULL, 'consent_form', TRUE, TRUE, 730, 'Documentation of participant consent for service delivery and support arrangements'),
    (NULL, 'individual_support_plan', TRUE, FALSE, 90, 'Detailed plan addressing participant goals, objectives, and support strategies'),
    (NULL, 'risk_assessment', TRUE, FALSE, 365, 'Assessment of risks to participant wellbeing and mitigation strategies'),
    (NULL, 'behaviour_support_plan', FALSE, FALSE, 365, 'Required for participants requiring behaviour support services'),
    (NULL, 'progress_notes', FALSE, FALSE, 30, 'Ongoing documentation of participant progress and support delivery'),
    (NULL, 'incident_report', FALSE, FALSE, NULL, 'Documentation of any incidents, accidents, or concerning events'),
    (NULL, 'funding_agreement', FALSE, TRUE, 365, 'Agreement on payment and funding arrangements'),
    (NULL, 'communication_plan', FALSE, FALSE, 180, 'Plan for how participant preferences for communication will be respected'),
    (NULL, 'financial_statement', FALSE, FALSE, 365, 'If managing participant funds, quarterly financial statements required'),
    (NULL, 'goals_plan', FALSE, FALSE, 365, 'Formal documentation of participant goals and progress tracking')
ON CONFLICT DO NOTHING;
