-- =============================================================================
-- Verida Compliance Platform — Seed Data
-- =============================================================================
-- Seeds all 17 NDIS Core Module Practice Standards.
-- Run this after all migrations have been applied.
-- Safe to re-run — uses INSERT ... ON CONFLICT DO NOTHING.
-- =============================================================================

INSERT INTO ndis_standards
    (standard_number, category, title, description, quality_indicators, is_active)
VALUES

-- =============================================================================
-- CATEGORY: governance (Standards 1.1 – 1.4)
-- =============================================================================

(
    '1.1',
    'governance',
    'Rights and Responsibilities',
    'Participants are aware of their rights and are supported to exercise them. Participants are free from abuse, neglect, exploitation and violence.',
    ARRAY[
        'Participants are provided with information about their rights',
        'Participants are supported to understand and exercise their rights',
        'Mechanisms exist for participants to raise concerns without retribution',
        'Participants are protected from abuse, neglect, and exploitation',
        'A rights-based approach is embedded in service delivery'
    ],
    TRUE
),

(
    '1.2',
    'governance',
    'Governance and Operational Management',
    'Effective governance and management systems are in place to ensure quality and safety in service delivery and to drive continuous improvement.',
    ARRAY[
        'A documented governance framework exists',
        'Roles and responsibilities are clearly defined',
        'Financial management systems are sound and transparent',
        'Regular reporting to governing body occurs',
        'Performance against key metrics is monitored'
    ],
    TRUE
),

(
    '1.3',
    'governance',
    'Risk Management',
    'Risks to participants, workers, and the organisation are identified, assessed and managed. A risk management framework is maintained and applied.',
    ARRAY[
        'A risk management policy and framework exists',
        'Risks are systematically identified and assessed',
        'Risk controls are implemented and monitored',
        'Risks are regularly reviewed and updated',
        'Staff are trained in risk management procedures'
    ],
    TRUE
),

(
    '1.4',
    'governance',
    'Quality Management',
    'A quality management system is in place to support continuous improvement in service delivery and organisational performance.',
    ARRAY[
        'A quality management framework is documented',
        'Quality indicators are defined and monitored',
        'Internal audits are conducted regularly',
        'Outcomes data is collected and analysed',
        'Improvements are implemented based on quality data'
    ],
    TRUE
),

-- =============================================================================
-- CATEGORY: operational_management (Standards 2.1 – 2.6)
-- =============================================================================

(
    '2.1',
    'operational_management',
    'Incident Management',
    'Incidents are identified, recorded, reported, and reviewed. Actions are taken to reduce the likelihood of incidents occurring and to improve the quality of supports.',
    ARRAY[
        'An incident management policy and procedure exists',
        'All incidents are recorded in a register',
        'Reportable incidents are notified to NDIS Commission within required timeframes',
        'Root cause analysis is conducted for serious incidents',
        'Incident trends are reviewed and used to improve practice'
    ],
    TRUE
),

(
    '2.2',
    'operational_management',
    'Feedback and Complaints Management',
    'An accessible and effective complaint management system is in place. Complaints are valued as an opportunity for improvement.',
    ARRAY[
        'A complaints management policy and procedure is documented',
        'Participants are informed of their right to complain',
        'Complaints are acknowledged and resolved in a timely manner',
        'Complaints data is analysed for improvement opportunities',
        'Anonymous feedback mechanisms are available'
    ],
    TRUE
),

(
    '2.3',
    'operational_management',
    'Human Resource Management',
    'Workers are appropriately qualified, experienced and skilled to deliver safe and quality supports. Ongoing learning and development is supported.',
    ARRAY[
        'Worker screening checks are completed for all applicable workers',
        'Position descriptions clearly define required qualifications',
        'Induction processes cover NDIS Code of Conduct',
        'Regular supervision and performance reviews occur',
        'Training records are maintained and current'
    ],
    TRUE
),

(
    '2.4',
    'operational_management',
    'Participant Money Management',
    'The financial interests of participants are protected. Any management of participant money is conducted with integrity and transparency.',
    ARRAY[
        'A participant money management policy exists',
        'Participant funds are kept separate from organisational funds',
        'Detailed records of all financial transactions are maintained',
        'Regular statements are provided to participants',
        'Audits of participant funds are conducted'
    ],
    TRUE
),

(
    '2.5',
    'operational_management',
    'Records Management',
    'Participant records and organisational records are managed in a way that ensures accuracy, completeness, accessibility and security.',
    ARRAY[
        'A records management policy is documented',
        'Records are stored securely and access is controlled',
        'Retention and disposal schedules are followed',
        'Participant records are accurate and up to date',
        'Privacy and confidentiality of records is maintained'
    ],
    TRUE
),

(
    '2.6',
    'operational_management',
    'Emergency and Disaster Management',
    'Plans are in place to ensure continuity of supports for participants during emergencies and disasters. Workers know their roles in an emergency.',
    ARRAY[
        'An emergency management plan is documented',
        'Individual emergency evacuation plans exist for participants',
        'Emergency drills are conducted regularly',
        'Workers are trained in emergency procedures',
        'Business continuity arrangements are documented'
    ],
    TRUE
),

-- =============================================================================
-- CATEGORY: provision_of_supports (Standards 3.1 – 3.6)
-- =============================================================================

(
    '3.1',
    'provision_of_supports',
    'Person-Centred Supports',
    'Supports are delivered in a person-centred way that reflects the participant''s individual goals, strengths, preferences and needs.',
    ARRAY[
        'Supports are tailored to individual participant goals and preferences',
        'Participants have choice and control over their supports',
        'Participant strengths and abilities are recognised and built upon',
        'Cultural, religious and linguistic needs are respected',
        'Families and carers are included as directed by the participant'
    ],
    TRUE
),

(
    '3.2',
    'provision_of_supports',
    'Access to Supports',
    'Participants have access to the supports they need. Transition into services is planned and participants are welcomed and oriented.',
    ARRAY[
        'Intake and access processes are clearly documented',
        'Eligibility and access criteria are applied consistently',
        'Participants are provided with information to make informed choices',
        'Referral pathways exist for services not provided',
        'Waitlist management is fair and transparent'
    ],
    TRUE
),

(
    '3.3',
    'provision_of_supports',
    'Support Planning',
    'Each participant has a support plan that reflects their individual goals and needs. Support plans are developed collaboratively with participants.',
    ARRAY[
        'Support plans are developed with participant involvement',
        'Support plans address identified goals and needs',
        'Support plans are reviewed regularly or when circumstances change',
        'Support plans are approved by the participant',
        'Risks identified in support plans are managed'
    ],
    TRUE
),

(
    '3.4',
    'provision_of_supports',
    'Responsive Support Provision',
    'Supports are delivered safely and competently by qualified workers. Supports respond to participant needs and changes in circumstances.',
    ARRAY[
        'Workers have the skills and knowledge to deliver supports safely',
        'Support delivery is monitored for quality and safety',
        'Changes to participant needs are identified and responded to promptly',
        'Medication management protocols are followed where applicable',
        'Support hours and activities are accurately recorded'
    ],
    TRUE
),

(
    '3.5',
    'provision_of_supports',
    'Service Agreements',
    'Participants are provided with a service agreement that clearly sets out the supports to be provided and the terms and conditions of service delivery.',
    ARRAY[
        'Service agreements are in place for all participants',
        'Service agreements are written in plain language',
        'Participants understand and agree to service agreement terms',
        'Service agreements are reviewed and updated as required',
        'Participant rights and responsibilities are included in agreements'
    ],
    TRUE
),

(
    '3.6',
    'provision_of_supports',
    'Transition to and from Provider',
    'Transitions to and from the provider are planned and managed to ensure continuity of supports and minimise disruption to participants.',
    ARRAY[
        'Transition planning begins well in advance of the transition date',
        'Participants are involved in transition planning',
        'Relevant information is shared with incoming providers (with consent)',
        'Continuity of critical supports is maintained during transition',
        'Exit interviews or feedback is sought from participants'
    ],
    TRUE
),

-- =============================================================================
-- CATEGORY: support_provision_environment (Standard 4.1)
-- =============================================================================

(
    '4.1',
    'support_provision_environment',
    'Support Provision Environment',
    'The environments in which supports are provided are safe, accessible, and appropriate to participant needs. Facilities and equipment are maintained.',
    ARRAY[
        'Premises are safe, clean and accessible for participants',
        'Regular safety inspections of facilities are conducted',
        'Equipment is fit for purpose and maintained',
        'First aid equipment and trained staff are available',
        'Environmental risks are identified and managed'
    ],
    TRUE
)

ON CONFLICT (standard_number) DO NOTHING;

-- Verify all 17 standards were inserted
DO $$
DECLARE
    standard_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO standard_count FROM ndis_standards WHERE is_active = TRUE;
    IF standard_count < 17 THEN
        RAISE WARNING 'Expected 17 active NDIS standards, found %', standard_count;
    ELSE
        RAISE NOTICE 'Successfully seeded % NDIS Practice Standards', standard_count;
    END IF;
END;
$$;
