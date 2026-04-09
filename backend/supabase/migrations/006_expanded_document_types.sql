-- =============================================================================
-- Migration 006: Expanded document types + registration module awareness
--
-- Changes:
--   1. Add registration_modules JSONB column to organizations
--   2. Add module column to document_requirements
--   3. Drop overly-restrictive CHECK constraints on document_type columns
--      (now validated at the application layer — too many types for SQL enum)
--   4. Seed expanded document_requirements covering all NDIS audit modules
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Registration modules on organizations
-- -----------------------------------------------------------------------------

ALTER TABLE organizations
    ADD COLUMN IF NOT EXISTS registration_modules JSONB NOT NULL DEFAULT '["core"]'::jsonb;

COMMENT ON COLUMN organizations.registration_modules IS
    'Array of registration module identifiers this org is certified for. '
    'Possible values: "core", "module_1", "module_2", "module_2a". '
    'Used to filter which document requirements apply to this org.';


-- -----------------------------------------------------------------------------
-- 2. Module column on document_requirements
-- -----------------------------------------------------------------------------

ALTER TABLE document_requirements
    ADD COLUMN IF NOT EXISTS module TEXT NOT NULL DEFAULT 'core';

COMMENT ON COLUMN document_requirements.module IS
    'Which NDIS registration module this requirement belongs to: '
    'core | module_1 | module_2 | module_2a';


-- -----------------------------------------------------------------------------
-- 3. Drop overly-restrictive CHECK constraints on document_type
--    (we now have 150+ types — validating at the application layer)
-- -----------------------------------------------------------------------------

-- document_requirements.document_type
DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'document_requirements'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%document_type%';
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE document_requirements DROP CONSTRAINT %I', constraint_name);
    END IF;
END;
$$;

-- client_documents.document_type
DO $$
DECLARE
    constraint_name TEXT;
BEGIN
    SELECT conname INTO constraint_name
    FROM pg_constraint
    WHERE conrelid = 'client_documents'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%document_type%';
    IF constraint_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE client_documents DROP CONSTRAINT %I', constraint_name);
    END IF;
END;
$$;


-- -----------------------------------------------------------------------------
-- 4. Expanded document_requirements seed data
--
-- Columns populated:
--   organization_id       NULL = global default (applies to all orgs)
--   document_type         snake_case type identifier
--   module                core | module_1 | module_2 | module_2a
--   is_mandatory          TRUE = required for audit, FALSE = recommended
--   requires_signature    whether a signature is needed on the document
--   review_frequency_days how often the document must be reviewed
--   description           plain-English description for UI display
-- -----------------------------------------------------------------------------

INSERT INTO document_requirements (
    organization_id,
    document_type,
    module,
    is_mandatory,
    requires_signature,
    review_frequency_days,
    description
) VALUES

-- ============================================================
-- CORE MODULE — Governance
-- ============================================================
(NULL, 'business_continuity_plan',          'core', TRUE,  FALSE, 365,
 'Plan detailing how the organisation will maintain critical services during disruptions or emergencies.'),
(NULL, 'strategic_operational_plan',        'core', TRUE,  FALSE, 365,
 'High-level strategic and operational goals with measurable outcomes for the organisation.'),
(NULL, 'conflict_of_interest_register',     'core', TRUE,  FALSE, 365,
 'Register of declared conflicts of interest for directors, key personnel, and workers.'),
(NULL, 'continuous_improvement_plan',       'core', TRUE,  FALSE, 365,
 'Documented plan for improving service quality, safety, and participant outcomes over time.'),
(NULL, 'continuous_improvement_register',   'core', TRUE,  FALSE, 90,
 'Ongoing register of improvement actions, owners, status, and completion dates.'),
(NULL, 'internal_audit_schedule',           'core', TRUE,  FALSE, 365,
 'Annual schedule of internal audits against NDIS Practice Standards and organisational policies.'),
(NULL, 'organisational_chart',              'core', FALSE, FALSE, 365,
 'Current chart showing organisational structure, reporting lines, and key roles.'),
(NULL, 'quality_improvement_plan',          'core', TRUE,  FALSE, 365,
 'Formal quality management plan aligned to the NDIS Practice Standards quality management framework.'),
(NULL, 'swot_analysis',                     'core', FALSE, FALSE, 365,
 'Periodic strengths, weaknesses, opportunities, and threats analysis to inform strategic planning.'),

-- ============================================================
-- CORE MODULE — Business / Risk Forms
-- ============================================================
(NULL, 'emergency_management_plan',         'core', TRUE,  FALSE, 365,
 'Comprehensive plan for managing emergencies and disasters affecting service delivery.'),
(NULL, 'emergency_evacuation_plan',         'core', TRUE,  FALSE, 365,
 'Site-specific evacuation procedures including assembly points, roles, and participant-specific requirements.'),
(NULL, 'risk_assessment',                   'core', TRUE,  FALSE, 365,
 'Systematic assessment of risks to participants, workers, and the organisation.'),
(NULL, 'risk_management_plan',              'core', TRUE,  FALSE, 365,
 'Organisation-wide plan for identifying, assessing, treating, and monitoring risks.'),
(NULL, 'risk_register',                     'core', TRUE,  FALSE, 90,
 'Live register of identified risks with likelihood, consequence, controls, and risk owners.'),
(NULL, 'workplace_inspection_checklist',    'core', TRUE,  FALSE, 90,
 'Regular checklist inspection of work environments for WHS hazards and compliance.'),
(NULL, 'whs_inspection_checklist',          'core', TRUE,  FALSE, 90,
 'Work Health and Safety inspection checklist for all service delivery locations.'),
(NULL, 'meeting_minutes',                   'core', FALSE, FALSE, NULL,
 'Formal minutes of governance, management, and team meetings.'),

-- ============================================================
-- CORE MODULE — Incident Management
-- ============================================================
(NULL, 'incident_report',                   'core', TRUE,  FALSE, NULL,
 'Individual report documenting a specific incident, near miss, or adverse event.'),
(NULL, 'incident_register',                 'core', TRUE,  FALSE, 90,
 'Organisation-wide register of all incidents with dates, types, outcomes, and status.'),
(NULL, 'incident_investigation_form',       'core', TRUE,  FALSE, NULL,
 'Structured investigation form used when an incident requires root cause analysis.'),
(NULL, 'reportable_incident_24hr',          'core', TRUE,  TRUE,  NULL,
 'Initial 24-hour notification form for NDIS reportable incidents as required by the NDIS Commission.'),
(NULL, 'reportable_incident_5day',          'core', TRUE,  TRUE,  NULL,
 'Five-day follow-up report for NDIS reportable incidents submitted to the NDIS Commission.'),

-- ============================================================
-- CORE MODULE — Complaints & Feedback
-- ============================================================
(NULL, 'complaint_form',                    'core', TRUE,  FALSE, NULL,
 'Standard form for participants, families, or workers to lodge a complaint.'),
(NULL, 'complaint_form_easy_english',       'core', TRUE,  FALSE, NULL,
 'Easy English version of the complaint form for participants with communication needs.'),
(NULL, 'complaints_register',               'core', TRUE,  FALSE, 90,
 'Register of all complaints received, with date, nature, action taken, and resolution.'),
(NULL, 'complaints_process_checklist',      'core', TRUE,  FALSE, 365,
 'Checklist confirming each step of the complaints handling process has been followed.'),
(NULL, 'feedback_form',                     'core', FALSE, FALSE, NULL,
 'General feedback form for participants and families to share suggestions or compliments.'),

-- ============================================================
-- CORE MODULE — Participant / Client Forms
-- ============================================================
(NULL, 'consent_form',                      'core', TRUE,  TRUE,  730,
 'Documentation of participant consent for service delivery, sharing information, and specific activities.'),
(NULL, 'consent_form_easy_read',            'core', FALSE, TRUE,  730,
 'Easy Read version of the consent form for participants with intellectual disability.'),
(NULL, 'intake_form',                       'core', TRUE,  FALSE, NULL,
 'Initial intake form collecting participant details, needs, and service preferences.'),
(NULL, 'intake_checklist',                  'core', TRUE,  FALSE, NULL,
 'Checklist ensuring all required intake steps and documents have been completed at onboarding.'),
(NULL, 'referral_form',                     'core', FALSE, FALSE, NULL,
 'Form used to refer a participant to or from another service provider.'),
(NULL, 'service_agreement',                 'core', TRUE,  TRUE,  365,
 'Core NDIS requirement: Agreement between participant and provider detailing supports, costs, and rights.'),
(NULL, 'service_agreement_easy_read',       'core', FALSE, TRUE,  365,
 'Easy Read version of the service agreement for participants with communication or cognitive needs.'),
(NULL, 'support_plan',                      'core', TRUE,  FALSE, 90,
 'Detailed support plan addressing participant goals, strategies, and scheduled supports.'),
(NULL, 'support_plan_easy_read',            'core', FALSE, FALSE, 90,
 'Easy Read version of the support plan for participants with communication needs.'),
(NULL, 'support_plan_progress_report',      'core', TRUE,  FALSE, 90,
 'Regular progress report against support plan goals and outcomes.'),
(NULL, 'support_plan_review_register',      'core', TRUE,  FALSE, 90,
 'Register tracking scheduled and completed reviews of participant support plans.'),
(NULL, 'participant_support_plan',          'core', TRUE,  FALSE, 90,
 'Comprehensive participant-level plan covering goals, supports, risk, and communication preferences.'),
(NULL, 'schedule_of_supports',              'core', TRUE,  TRUE,  365,
 'Schedule detailing the specific supports, hours, and funding allocated to a participant.'),
(NULL, 'participant_handbook',              'core', TRUE,  FALSE, 365,
 'Participant-facing handbook explaining services, rights, complaints process, and privacy.'),
(NULL, 'welcome_pack_easy_read',            'core', FALSE, FALSE, 365,
 'Easy Read welcome pack for new participants outlining how the service works.'),
(NULL, 'exit_form',                         'core', TRUE,  FALSE, NULL,
 'Form documenting the process and reason when a participant exits the service.'),
(NULL, 'exit_transition_plan',              'core', FALSE, FALSE, NULL,
 'Plan to ensure smooth transition when a participant moves to another provider or exits services.'),
(NULL, 'satisfaction_survey',               'core', FALSE, FALSE, 365,
 'Periodic survey to gather participant and family feedback on service quality and experience.'),
(NULL, 'acknowledgement_form',              'core', FALSE, TRUE,  NULL,
 'Acknowledgement signed by participants or families confirming they have received documents or information.'),
(NULL, 'refusal_to_consent',                'core', FALSE, TRUE,  NULL,
 'Documentation of a participant''s informed decision to refuse a service, support, or activity.'),
(NULL, 'money_handling_consent',            'core', FALSE, TRUE,  365,
 'Consent and process agreement for any worker-assisted handling of participant funds.'),
(NULL, 'personal_emergency_plan',           'core', TRUE,  FALSE, 365,
 'Individual emergency plan detailing how a participant will be supported in an emergency or evacuation.'),
(NULL, 'safe_environment_risk_assessment',  'core', TRUE,  FALSE, 365,
 'Risk assessment of the participant''s home or service environment for safety and hazard identification.'),
(NULL, 'advocate_authority_form',           'core', FALSE, TRUE,  365,
 'Form authorising a nominated advocate or guardian to act on behalf of the participant.'),
(NULL, 'opt_out_audit_form',                'core', FALSE, TRUE,  NULL,
 'Form for participants to opt out of being contacted during an external audit process.'),
(NULL, 'privacy_statement',                 'core', TRUE,  FALSE, 365,
 'Statement provided to participants explaining how their personal information is collected, used, and protected.'),
(NULL, 'privacy_policy',                    'core', TRUE,  FALSE, 365,
 'Organisation-wide privacy and information management policy aligned to Australian privacy legislation.'),
(NULL, 'progress_notes',                    'core', TRUE,  FALSE, 30,
 'Ongoing case notes documenting participant progress, support delivered, and significant events.'),
(NULL, 'client_charter',                    'core', TRUE,  FALSE, 365,
 'Participant-facing document stating their rights and what they can expect from the service.'),

-- ============================================================
-- CORE MODULE — Staff / HR
-- ============================================================
(NULL, 'staff_induction_checklist',         'core', TRUE,  TRUE,  NULL,
 'Checklist confirming completion of all induction activities for new workers.'),
(NULL, 'staff_performance_review',          'core', TRUE,  FALSE, 365,
 'Annual or semi-annual formal performance review documentation for workers.'),
(NULL, 'staff_training_log',                'core', TRUE,  FALSE, 365,
 'Record of training completed by individual workers including dates and competency outcomes.'),
(NULL, 'individual_training_register',      'core', TRUE,  FALSE, 365,
 'Worker-level register of all mandatory and role-specific training with expiry dates.'),
(NULL, 'training_development_book',         'core', FALSE, FALSE, 365,
 'Organisation-wide training and professional development record for all staff.'),
(NULL, 'supervision_record',                'core', TRUE,  FALSE, 90,
 'Record of regular supervisory meetings between workers and their supervisors.'),
(NULL, 'staff_handbook',                    'core', TRUE,  FALSE, 365,
 'Worker-facing handbook covering policies, procedures, rights, and responsibilities.'),
(NULL, 'personnel_file_setup',              'core', TRUE,  FALSE, NULL,
 'Checklist confirming all required pre-employment documents are on file for a worker.'),
(NULL, 'privacy_confidentiality_agreement', 'core', TRUE,  TRUE,  NULL,
 'Signed agreement by workers to maintain participant and organisational confidentiality.'),
(NULL, 'conflict_of_interest_declaration',  'core', TRUE,  TRUE,  365,
 'Annual declaration by workers of any actual or perceived conflicts of interest.'),
(NULL, 'delegation_of_authority',           'core', FALSE, FALSE, 365,
 'Document specifying which staff have authority to make decisions at each level of the organisation.'),
(NULL, 'worker_screening_check',            'core', TRUE,  FALSE, 1825,
 'NDIS Worker Screening Check clearance record — mandatory for all workers in risk-assessed roles.'),
(NULL, 'first_aid_certificate',             'core', TRUE,  FALSE, 730,
 'Current first aid certification for workers — required to maintain valid certificates on file.'),
(NULL, 'ndis_module_training',              'core', TRUE,  FALSE, 365,
 'NDIS Worker Orientation Module or equivalent mandatory training completion record.'),

-- ============================================================
-- CORE MODULE — Medication Management
-- ============================================================
(NULL, 'medication_administration_chart',   'core', TRUE,  FALSE, 30,
 'Participant-specific medication administration record completed at each dose.'),
(NULL, 'medication_care_plan_consent',      'core', TRUE,  TRUE,  365,
 'Consent and care plan for medication administration support by workers.'),
(NULL, 'medication_incident_report',        'core', TRUE,  FALSE, NULL,
 'Report documenting any medication error, missed dose, or adverse reaction.'),
(NULL, 'medication_management_plan',        'core', TRUE,  FALSE, 365,
 'Organisation-level plan governing how medication administration is managed and overseen.'),
(NULL, 'medication_risk_assessment',        'core', TRUE,  FALSE, 365,
 'Risk assessment covering medication administration risks for a specific participant.'),
(NULL, 'medication_phone_order',            'core', FALSE, FALSE, NULL,
 'Record of verbal or phone medication orders from a prescriber, with follow-up documentation.'),
(NULL, 'prn_medication_record',             'core', FALSE, FALSE, 30,
 'Record of PRN (as-needed) medication administration instances for a participant.'),
(NULL, 'medication_register',               'core', TRUE,  FALSE, 30,
 'Register of all scheduled medications held for participants, including stock levels.'),

-- ============================================================
-- CORE MODULE — Position Descriptions
-- ============================================================
(NULL, 'support_worker_pd',                 'core', TRUE,  FALSE, 365,
 'Position description for support worker roles detailing duties, qualifications, and reporting lines.'),
(NULL, 'team_leader_pd',                    'core', TRUE,  FALSE, 365,
 'Position description for team leader / coordinator roles.'),
(NULL, 'clinical_nurse_pd',                 'core', FALSE, FALSE, 365,
 'Position description for clinical nurse or enrolled nurse roles in high-intensity support settings.'),
(NULL, 'registered_nurse_pd',               'core', FALSE, FALSE, 365,
 'Position description for registered nurse roles.'),
(NULL, 'management_pd',                     'core', TRUE,  FALSE, 365,
 'Position description for management and leadership roles (CEO, Operations Manager, etc.).'),

-- ============================================================
-- MODULE 1 — High Intensity Daily Personal Activities
-- Enteral Feeding
-- ============================================================
(NULL, 'enteral_feeding_care_plan',         'module_1', TRUE,  FALSE, 90,
 'Participant-specific care plan for enteral (tube) feeding, including feeding schedule and monitoring.'),
(NULL, 'enteral_feeding_consent',           'module_1', TRUE,  TRUE,  365,
 'Informed consent for enteral feeding support provided by workers.'),
(NULL, 'enteral_feeding_assessment',        'module_1', TRUE,  FALSE, 90,
 'Clinical assessment of the participant''s enteral feeding needs and competency requirements.'),
(NULL, 'enteral_feeding_competency',        'module_1', TRUE,  FALSE, 365,
 'Worker competency assessment for providing enteral feeding support.'),
(NULL, 'fluid_balance_chart',               'module_1', FALSE, FALSE, 30,
 'Daily chart recording fluid intake and output for participants requiring fluid management.'),
(NULL, 'stoma_care_plan',                   'module_1', FALSE, FALSE, 90,
 'Care plan for participants with a stoma, covering care procedures and products used.'),
(NULL, 'weight_chart',                      'module_1', FALSE, FALSE, 30,
 'Regular weight monitoring chart for participants at risk of malnutrition or weight loss.'),

-- ============================================================
-- MODULE 1 — Wound Management
-- ============================================================
(NULL, 'wound_assessment',                  'module_1', TRUE,  FALSE, 30,
 'Clinical wound assessment documenting wound type, size, stage, and treatment plan.'),
(NULL, 'wound_management_care_plan',        'module_1', TRUE,  FALSE, 30,
 'Care plan for ongoing wound management including dressing schedule and clinician instructions.'),
(NULL, 'wound_management_consent',          'module_1', TRUE,  TRUE,  365,
 'Consent for wound management support delivered by workers under a clinical plan.'),
(NULL, 'wound_progress_report',             'module_1', TRUE,  FALSE, 30,
 'Progress report documenting wound healing, changes in wound status, and treatment modifications.'),

-- ============================================================
-- MODULE 1 — Catheter Management
-- ============================================================
(NULL, 'catheter_care_plan',                'module_1', TRUE,  FALSE, 90,
 'Care plan for urinary or suprapubic catheter management including care procedures and monitoring.'),
(NULL, 'catheter_consent',                  'module_1', TRUE,  TRUE,  365,
 'Informed consent for catheter care support by workers under a clinical plan.'),
(NULL, 'catheter_competency',               'module_1', TRUE,  FALSE, 365,
 'Worker competency assessment for providing catheter management support.'),

-- ============================================================
-- MODULE 1 — Subcutaneous Injections
-- ============================================================
(NULL, 'subcutaneous_care_plan',            'module_1', TRUE,  FALSE, 90,
 'Care plan for subcutaneous medication administration including drug, dose, and site rotation.'),
(NULL, 'subcutaneous_consent',              'module_1', TRUE,  TRUE,  365,
 'Consent for subcutaneous injection support administered by workers.'),
(NULL, 'subcutaneous_medication_sheet',     'module_1', TRUE,  FALSE, 30,
 'Administration record for subcutaneous medications, completed at each injection.'),
(NULL, 'subcutaneous_assessment',           'module_1', TRUE,  FALSE, 90,
 'Clinical assessment of the participant''s subcutaneous injection needs and injection sites.'),

-- ============================================================
-- MODULE 1 — Tracheostomy Management
-- ============================================================
(NULL, 'tracheostomy_care_plan',            'module_1', TRUE,  FALSE, 90,
 'Care plan for tracheostomy management including suctioning, dressing changes, and emergency procedures.'),
(NULL, 'tracheostomy_consent',              'module_1', TRUE,  TRUE,  365,
 'Consent for tracheostomy care support delivered by workers under clinical supervision.'),
(NULL, 'tracheostomy_competency',           'module_1', TRUE,  FALSE, 365,
 'Worker competency assessment for tracheostomy care and emergency management.'),

-- ============================================================
-- MODULE 1 — Ventilator Management
-- ============================================================
(NULL, 'ventilator_care_plan',              'module_1', TRUE,  FALSE, 90,
 'Care plan for participants requiring ventilator support, including alarm responses and circuit management.'),
(NULL, 'ventilator_consent',                'module_1', TRUE,  TRUE,  365,
 'Consent for ventilator management support by trained workers.'),
(NULL, 'ventilator_competency',             'module_1', TRUE,  FALSE, 365,
 'Worker competency assessment for managing and troubleshooting ventilator equipment.'),

-- ============================================================
-- MODULE 1 — Complex Bowel Management
-- ============================================================
(NULL, 'complex_bowel_care_plan',           'module_1', TRUE,  FALSE, 90,
 'Care plan for complex bowel management including bowel programs, digital stimulation, or manual evacuation.'),
(NULL, 'complex_bowel_consent',             'module_1', TRUE,  TRUE,  365,
 'Consent for complex bowel management procedures carried out by workers.'),
(NULL, 'complex_bowel_competency',          'module_1', TRUE,  FALSE, 365,
 'Worker competency assessment for delivering complex bowel management support.'),

-- ============================================================
-- MODULE 1 — Severe Dysphagia
-- ============================================================
(NULL, 'dysphagia_care_plan',               'module_1', TRUE,  FALSE, 90,
 'Care plan for participants with severe dysphagia, including texture/fluid requirements and mealtime strategies.'),
(NULL, 'dysphagia_consent',                 'module_1', TRUE,  TRUE,  365,
 'Consent for dysphagia mealtime support, including modified textures, provided by workers.'),
(NULL, 'dysphagia_assessment',              'module_1', TRUE,  FALSE, 90,
 'Clinical dysphagia assessment (typically by a speech pathologist) informing the care plan.'),

-- ============================================================
-- MODULE 1 — Epilepsy / Seizure Management
-- ============================================================
(NULL, 'epilepsy_seizure_management_plan',  'module_1', TRUE,  FALSE, 365,
 'Participant-specific seizure management plan including seizure types, triggers, first aid, and emergency actions.'),
(NULL, 'epilepsy_consent',                  'module_1', TRUE,  TRUE,  365,
 'Consent for seizure management support and administration of rescue medication by workers.'),
(NULL, 'epilepsy_competency',               'module_1', TRUE,  FALSE, 365,
 'Worker competency assessment for seizure recognition, management, and emergency response.'),

-- ============================================================
-- MODULE 2 / 2A — Implementing Behaviour Support /
--                 Specialist Behaviour Support
-- ============================================================
(NULL, 'behaviour_support_plan',                    'module_2', TRUE,  FALSE, 365,
 'Comprehensive behaviour support plan developed by a behaviour support practitioner for a participant.'),
(NULL, 'interim_behaviour_support_plan',             'module_2', FALSE, FALSE, 90,
 'Interim BSP in place while a comprehensive behaviour support plan is being developed.'),
(NULL, 'reviewed_bsp_register',                     'module_2', TRUE,  FALSE, 90,
 'Register recording scheduled and completed reviews of behaviour support plans.'),
(NULL, 'restrictive_practices_monthly_report',       'module_2', TRUE,  FALSE, 30,
 'Monthly report to the NDIS Commission on use of any regulated restrictive practices.'),
(NULL, 'legal_restraints_competency',                'module_2', TRUE,  FALSE, 365,
 'Worker competency assessment in the lawful use of regulated restrictive practices.'),
(NULL, 'clinical_supervision_record',                'module_2', TRUE,  FALSE, 90,
 'Record of clinical supervision sessions for behaviour support practitioners.'),
(NULL, 'reportable_incident_24hr_bsp',               'module_2', TRUE,  TRUE,  NULL,
 '24-hour reportable incident notification specific to behaviour support and restrictive practice incidents.'),
(NULL, 'reportable_incident_5day_bsp',               'module_2', TRUE,  TRUE,  NULL,
 'Five-day follow-up report for behaviour support–related reportable incidents.'),
(NULL, 'staff_training_needs_assessment',            'module_2', TRUE,  FALSE, 365,
 'Assessment of individual worker training needs related to behaviour support competencies.'),
(NULL, 'ongoing_professional_development_plan',      'module_2a', TRUE, FALSE, 365,
 'Documented professional development plan for specialist behaviour support practitioners.')

ON CONFLICT (organization_id, document_type) DO UPDATE
    SET
        module                = EXCLUDED.module,
        is_mandatory          = EXCLUDED.is_mandatory,
        requires_signature    = EXCLUDED.requires_signature,
        review_frequency_days = EXCLUDED.review_frequency_days,
        description           = EXCLUDED.description;


-- -----------------------------------------------------------------------------
-- 5. Index for fast module-filtered queries
-- -----------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_doc_requirements_module
    ON document_requirements (module);
