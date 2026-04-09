"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
import uuid


# =============================================================================
# Enums
# =============================================================================

class DocumentTypeEnum(str, Enum):
    # ---- CORE MODULE — Governance ----
    BUSINESS_CONTINUITY_PLAN = "business_continuity_plan"
    STRATEGIC_OPERATIONAL_PLAN = "strategic_operational_plan"
    CONFLICT_OF_INTEREST_REGISTER = "conflict_of_interest_register"
    CONTINUOUS_IMPROVEMENT_PLAN = "continuous_improvement_plan"
    CONTINUOUS_IMPROVEMENT_REGISTER = "continuous_improvement_register"
    INTERNAL_AUDIT_SCHEDULE = "internal_audit_schedule"
    ORGANISATIONAL_CHART = "organisational_chart"
    QUALITY_IMPROVEMENT_PLAN = "quality_improvement_plan"
    SWOT_ANALYSIS = "swot_analysis"

    # ---- CORE MODULE — Business / Risk Forms ----
    EMERGENCY_MANAGEMENT_PLAN = "emergency_management_plan"
    EMERGENCY_EVACUATION_PLAN = "emergency_evacuation_plan"
    RISK_ASSESSMENT = "risk_assessment"
    RISK_MANAGEMENT_PLAN = "risk_management_plan"
    RISK_REGISTER = "risk_register"
    WORKPLACE_INSPECTION_CHECKLIST = "workplace_inspection_checklist"
    WHS_INSPECTION_CHECKLIST = "whs_inspection_checklist"
    MEETING_MINUTES = "meeting_minutes"

    # ---- CORE MODULE — Incident Management ----
    INCIDENT_REPORT = "incident_report"
    INCIDENT_REGISTER = "incident_register"
    INCIDENT_INVESTIGATION_FORM = "incident_investigation_form"
    REPORTABLE_INCIDENT_24HR = "reportable_incident_24hr"
    REPORTABLE_INCIDENT_5DAY = "reportable_incident_5day"

    # ---- CORE MODULE — Complaints & Feedback ----
    COMPLAINT_FORM = "complaint_form"
    COMPLAINT_FORM_EASY_ENGLISH = "complaint_form_easy_english"
    COMPLAINTS_REGISTER = "complaints_register"
    COMPLAINTS_PROCESS_CHECKLIST = "complaints_process_checklist"
    FEEDBACK_FORM = "feedback_form"

    # ---- CORE MODULE — Participant / Client Forms ----
    CONSENT_FORM = "consent_form"
    CONSENT_FORM_EASY_READ = "consent_form_easy_read"
    INTAKE_FORM = "intake_form"
    INTAKE_CHECKLIST = "intake_checklist"
    REFERRAL_FORM = "referral_form"
    SERVICE_AGREEMENT = "service_agreement"
    SERVICE_AGREEMENT_EASY_READ = "service_agreement_easy_read"
    SUPPORT_PLAN = "support_plan"
    SUPPORT_PLAN_EASY_READ = "support_plan_easy_read"
    SUPPORT_PLAN_PROGRESS_REPORT = "support_plan_progress_report"
    SUPPORT_PLAN_REVIEW_REGISTER = "support_plan_review_register"
    PARTICIPANT_SUPPORT_PLAN = "participant_support_plan"
    SCHEDULE_OF_SUPPORTS = "schedule_of_supports"
    PARTICIPANT_HANDBOOK = "participant_handbook"
    WELCOME_PACK_EASY_READ = "welcome_pack_easy_read"
    EXIT_FORM = "exit_form"
    EXIT_TRANSITION_PLAN = "exit_transition_plan"
    SATISFACTION_SURVEY = "satisfaction_survey"
    ACKNOWLEDGEMENT_FORM = "acknowledgement_form"
    REFUSAL_TO_CONSENT = "refusal_to_consent"
    MONEY_HANDLING_CONSENT = "money_handling_consent"
    PERSONAL_EMERGENCY_PLAN = "personal_emergency_plan"
    SAFE_ENVIRONMENT_RISK_ASSESSMENT = "safe_environment_risk_assessment"
    ADVOCATE_AUTHORITY_FORM = "advocate_authority_form"
    OPT_OUT_AUDIT_FORM = "opt_out_audit_form"
    PRIVACY_STATEMENT = "privacy_statement"
    PRIVACY_POLICY = "privacy_policy"
    PROGRESS_NOTES = "progress_notes"
    CLIENT_CHARTER = "client_charter"

    # ---- CORE MODULE — Staff / HR ----
    STAFF_INDUCTION_CHECKLIST = "staff_induction_checklist"
    STAFF_PERFORMANCE_REVIEW = "staff_performance_review"
    STAFF_TRAINING_LOG = "staff_training_log"
    INDIVIDUAL_TRAINING_REGISTER = "individual_training_register"
    TRAINING_DEVELOPMENT_BOOK = "training_development_book"
    SUPERVISION_RECORD = "supervision_record"
    STAFF_HANDBOOK = "staff_handbook"
    PERSONNEL_FILE_SETUP = "personnel_file_setup"
    PRIVACY_CONFIDENTIALITY_AGREEMENT = "privacy_confidentiality_agreement"
    CONFLICT_OF_INTEREST_DECLARATION = "conflict_of_interest_declaration"
    DELEGATION_OF_AUTHORITY = "delegation_of_authority"
    WORKER_SCREENING_CHECK = "worker_screening_check"
    FIRST_AID_CERTIFICATE = "first_aid_certificate"
    NDIS_MODULE_TRAINING = "ndis_module_training"

    # ---- CORE MODULE — Medication Management ----
    MEDICATION_ADMINISTRATION_CHART = "medication_administration_chart"
    MEDICATION_CARE_PLAN_CONSENT = "medication_care_plan_consent"
    MEDICATION_INCIDENT_REPORT = "medication_incident_report"
    MEDICATION_MANAGEMENT_PLAN = "medication_management_plan"
    MEDICATION_RISK_ASSESSMENT = "medication_risk_assessment"
    MEDICATION_PHONE_ORDER = "medication_phone_order"
    PRN_MEDICATION_RECORD = "prn_medication_record"
    MEDICATION_REGISTER = "medication_register"

    # ---- CORE MODULE — Position Descriptions ----
    SUPPORT_WORKER_PD = "support_worker_pd"
    TEAM_LEADER_PD = "team_leader_pd"
    CLINICAL_NURSE_PD = "clinical_nurse_pd"
    REGISTERED_NURSE_PD = "registered_nurse_pd"
    MANAGEMENT_PD = "management_pd"

    # ---- MODULE 1 — Enteral Feeding ----
    ENTERAL_FEEDING_CARE_PLAN = "enteral_feeding_care_plan"
    ENTERAL_FEEDING_CONSENT = "enteral_feeding_consent"
    ENTERAL_FEEDING_ASSESSMENT = "enteral_feeding_assessment"
    ENTERAL_FEEDING_COMPETENCY = "enteral_feeding_competency"
    FLUID_BALANCE_CHART = "fluid_balance_chart"
    STOMA_CARE_PLAN = "stoma_care_plan"
    WEIGHT_CHART = "weight_chart"

    # ---- MODULE 1 — Wound Management ----
    WOUND_ASSESSMENT = "wound_assessment"
    WOUND_MANAGEMENT_CARE_PLAN = "wound_management_care_plan"
    WOUND_MANAGEMENT_CONSENT = "wound_management_consent"
    WOUND_PROGRESS_REPORT = "wound_progress_report"

    # ---- MODULE 1 — Catheter Management ----
    CATHETER_CARE_PLAN = "catheter_care_plan"
    CATHETER_CONSENT = "catheter_consent"
    CATHETER_COMPETENCY = "catheter_competency"

    # ---- MODULE 1 — Subcutaneous Injections ----
    SUBCUTANEOUS_CARE_PLAN = "subcutaneous_care_plan"
    SUBCUTANEOUS_CONSENT = "subcutaneous_consent"
    SUBCUTANEOUS_MEDICATION_SHEET = "subcutaneous_medication_sheet"
    SUBCUTANEOUS_ASSESSMENT = "subcutaneous_assessment"

    # ---- MODULE 1 — Tracheostomy ----
    TRACHEOSTOMY_CARE_PLAN = "tracheostomy_care_plan"
    TRACHEOSTOMY_CONSENT = "tracheostomy_consent"
    TRACHEOSTOMY_COMPETENCY = "tracheostomy_competency"

    # ---- MODULE 1 — Ventilator ----
    VENTILATOR_CARE_PLAN = "ventilator_care_plan"
    VENTILATOR_CONSENT = "ventilator_consent"
    VENTILATOR_COMPETENCY = "ventilator_competency"

    # ---- MODULE 1 — Complex Bowel ----
    COMPLEX_BOWEL_CARE_PLAN = "complex_bowel_care_plan"
    COMPLEX_BOWEL_CONSENT = "complex_bowel_consent"
    COMPLEX_BOWEL_COMPETENCY = "complex_bowel_competency"

    # ---- MODULE 1 — Dysphagia ----
    DYSPHAGIA_CARE_PLAN = "dysphagia_care_plan"
    DYSPHAGIA_CONSENT = "dysphagia_consent"
    DYSPHAGIA_ASSESSMENT = "dysphagia_assessment"

    # ---- MODULE 1 — Epilepsy ----
    EPILEPSY_SEIZURE_MANAGEMENT_PLAN = "epilepsy_seizure_management_plan"
    EPILEPSY_CONSENT = "epilepsy_consent"
    EPILEPSY_COMPETENCY = "epilepsy_competency"

    # ---- MODULE 2 / 2A — Behaviour Support ----
    BEHAVIOUR_SUPPORT_PLAN = "behaviour_support_plan"
    INTERIM_BEHAVIOUR_SUPPORT_PLAN = "interim_behaviour_support_plan"
    REVIEWED_BSP_REGISTER = "reviewed_bsp_register"
    RESTRICTIVE_PRACTICES_MONTHLY_REPORT = "restrictive_practices_monthly_report"
    LEGAL_RESTRAINTS_COMPETENCY = "legal_restraints_competency"
    CLINICAL_SUPERVISION_RECORD = "clinical_supervision_record"
    REPORTABLE_INCIDENT_24HR_BSP = "reportable_incident_24hr_bsp"
    REPORTABLE_INCIDENT_5DAY_BSP = "reportable_incident_5day_bsp"
    STAFF_TRAINING_NEEDS_ASSESSMENT = "staff_training_needs_assessment"
    ONGOING_PROFESSIONAL_DEVELOPMENT_PLAN = "ongoing_professional_development_plan"

    UNKNOWN = "unknown"


class ComplianceStatusEnum(str, Enum):
    COMPLIANT = "compliant"
    NEEDS_ATTENTION = "needs_attention"
    NON_COMPLIANT = "non_compliant"
    NOT_ASSESSED = "not_assessed"


class RiskLevelEnum(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ProcessingStatusEnum(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobTypeEnum(str, Enum):
    DOCUMENT_CLASSIFICATION = "document_classification"
    COMPLIANCE_ANALYSIS = "compliance_analysis"
    FULL_SCAN = "full_scan"


class PlanTierEnum(str, Enum):
    ESSENTIALS = "essentials"
    GROWTH = "growth"
    SCALE = "scale"


class UserRoleEnum(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class StandardCategoryEnum(str, Enum):
    GOVERNANCE = "governance"
    OPERATIONAL_MANAGEMENT = "operational_management"
    PROVISION_OF_SUPPORTS = "provision_of_supports"
    SUPPORT_PROVISION_ENVIRONMENT = "support_provision_environment"


# =============================================================================
# Auth Models
# =============================================================================

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: str = Field(..., min_length=1)
    organization_name: Optional[str] = Field(
        None,
        description="If provided, a new organisation will be created and the user assigned as owner"
    )


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordUpdateRequest(BaseModel):
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# =============================================================================
# Profile Models
# =============================================================================

class ProfileResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: UserRoleEnum
    organization_id: Optional[str]
    avatar_url: Optional[str]
    created_at: datetime


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


# =============================================================================
# Organization Models
# =============================================================================

class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1)
    abn: Optional[str] = Field(None, description="Australian Business Number")
    ndis_registration_number: Optional[str] = None
    registration_type: str = Field("registered", pattern="^(registered|unregistered)$")
    plan_tier: PlanTierEnum = PlanTierEnum.ESSENTIALS
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    website: Optional[str] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    abn: Optional[str] = None
    ndis_registration_number: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    audit_date: Optional[date] = None
    audit_type: Optional[str] = None


class OrganizationResponse(BaseModel):
    id: str
    name: str
    abn: Optional[str]
    ndis_registration_number: Optional[str]
    registration_type: str
    plan_tier: PlanTierEnum
    address: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    website: Optional[str]
    audit_date: Optional[date]
    audit_type: Optional[str]
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Document Models
# =============================================================================

class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    original_filename: str
    document_type: Optional[DocumentTypeEnum]
    file_size: int
    processing_status: ProcessingStatusEnum
    job_id: str
    message: str


class DocumentResponse(BaseModel):
    id: str
    organization_id: str
    filename: str
    original_filename: str
    file_size: Optional[int]
    mime_type: Optional[str]
    document_type: Optional[str]
    processing_status: ProcessingStatusEnum
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    storage_path: str
    extracted_text: Optional[str]
    processing_error: Optional[str]
    metadata: Dict[str, Any]


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
    page: int
    per_page: int


# =============================================================================
# NDIS Standard Models
# =============================================================================

class NDISStandardResponse(BaseModel):
    id: str
    standard_number: str
    category: StandardCategoryEnum
    title: str
    description: str
    quality_indicators: List[str]
    is_active: bool


class NDISStandardListResponse(BaseModel):
    standards: List[NDISStandardResponse]
    total: int


# =============================================================================
# Compliance Models
# =============================================================================

class ComplianceScoreResponse(BaseModel):
    id: str
    organization_id: str
    document_id: Optional[str]
    standard_id: str
    standard_number: Optional[str]
    standard_title: Optional[str]
    standard_category: Optional[str]
    score: Optional[float]
    status: ComplianceStatusEnum
    evidence_found: List[str]
    analysis_notes: Optional[str]
    confidence: Optional[float]
    created_at: datetime


class OverallComplianceResponse(BaseModel):
    overall_score: float
    status: ComplianceStatusEnum
    traffic_light: str  # "green", "amber", "red", "grey"
    total_standards: int
    compliant_count: int
    needs_attention_count: int
    non_compliant_count: int
    not_assessed_count: int
    scores_by_category: Dict[str, Dict[str, Any]]
    scores: List[Any]  # List of ComplianceScoreResponse dicts


class ComplianceScanRequest(BaseModel):
    document_ids: Optional[List[str]] = Field(
        None,
        description="Specific document IDs to scan. If omitted, all processed documents are scanned."
    )


class ComplianceScanResponse(BaseModel):
    job_id: str
    message: str
    documents_queued: int


# =============================================================================
# Gap Analysis Models
# =============================================================================

class GapResponse(BaseModel):
    id: str
    organization_id: str
    standard_id: str
    standard_number: Optional[str]
    standard_title: Optional[str]
    document_id: Optional[str]
    risk_level: RiskLevelEnum
    gap_description: str
    remediation_action: str
    priority_order: Optional[int]
    resolved: bool
    resolved_at: Optional[datetime]
    created_at: datetime


class GapListResponse(BaseModel):
    gaps: List[GapResponse]
    total: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int


class GapResolveRequest(BaseModel):
    resolved: bool
    notes: Optional[str] = None


# =============================================================================
# Analysis Job Models
# =============================================================================

class AnalysisJobResponse(BaseModel):
    id: str
    organization_id: str
    document_id: Optional[str]
    job_type: JobTypeEnum
    status: str
    progress: int
    error_message: Optional[str]
    result: Dict[str, Any]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime


# =============================================================================
# Dashboard Models
# =============================================================================

class DashboardResponse(BaseModel):
    organization_id: str
    organization_name: str
    plan_tier: str
    audit_date: Optional[date]
    days_until_audit: Optional[int]
    total_documents: int
    overall_compliance_score: Optional[float]
    traffic_light: str  # "green", "amber", "red", "grey"
    compliant_standards: int
    needs_attention_standards: int
    non_compliant_standards: int
    not_assessed_standards: int
    critical_gaps: int
    high_gaps: int
    medium_gaps: int
    low_gaps: int
    pending_documents: int
    last_refreshed: Optional[datetime]


# =============================================================================
# Error & Utility Models
# =============================================================================

class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None


class HealthCheckResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime


# =============================================================================
# Client Models
# =============================================================================

class ClientCreate(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    date_of_birth: date
    ndis_participant_number: str
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    suburb: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    country: Optional[str] = None
    current_plan_start_date: Optional[date] = None
    current_plan_end_date: Optional[date] = None
    current_plan_budget_amount: Optional[float] = None
    funded_support_categories: Optional[List[str]] = Field(default_factory=list)
    requires_behaviour_support: bool = False
    primary_contact_name: Optional[str] = None
    primary_contact_relationship: Optional[str] = None
    primary_contact_email: Optional[EmailStr] = None
    primary_contact_phone: Optional[str] = None


class ClientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    suburb: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    country: Optional[str] = None
    current_plan_start_date: Optional[date] = None
    current_plan_end_date: Optional[date] = None
    current_plan_budget_amount: Optional[float] = None
    funded_support_categories: Optional[List[str]] = None
    requires_behaviour_support: Optional[bool] = None
    primary_contact_name: Optional[str] = None
    primary_contact_relationship: Optional[str] = None
    primary_contact_email: Optional[EmailStr] = None
    primary_contact_phone: Optional[str] = None
    is_flagged_for_review: Optional[bool] = None
    review_notes: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive|exited)$")


class ClientResponse(BaseModel):
    id: str
    organization_id: str
    first_name: str
    last_name: str
    date_of_birth: date
    ndis_participant_number: str
    email: Optional[str]
    phone_number: Optional[str]
    address_line1: Optional[str]
    address_line2: Optional[str]
    suburb: Optional[str]
    state: Optional[str]
    postcode: Optional[str]
    country: Optional[str]
    current_plan_start_date: Optional[date]
    current_plan_end_date: Optional[date]
    current_plan_budget_amount: Optional[float]
    funded_support_categories: List[str]
    status: str
    requires_behaviour_support: bool
    primary_contact_name: Optional[str]
    primary_contact_relationship: Optional[str]
    primary_contact_email: Optional[str]
    primary_contact_phone: Optional[str]
    is_flagged_for_review: bool
    review_notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class ClientListResponse(BaseModel):
    clients: List[ClientResponse]
    total: int
    page: int
    per_page: int


# =============================================================================
# Client Documents Models
# =============================================================================

class ClientDocumentCreate(BaseModel):
    document_id: str
    document_type: str = Field(..., min_length=1, description="NDIS document type — must be a valid DocumentTypeEnum value or a legacy client-document category")
    document_date: Optional[date] = None
    document_version: Optional[str] = None
    review_due_date: Optional[date] = None
    is_required: bool = False
    notes: Optional[str] = None

    @validator("document_type")
    def validate_document_type(cls, v: str) -> str:
        # Accept any valid DocumentTypeEnum value
        valid = {e.value for e in DocumentTypeEnum}
        # Also accept legacy client-document categories from the original schema
        legacy = {
            "individual_support_plan", "goals_plan", "financial_statement",
            "funding_agreement", "communication_plan", "transition_plan", "other",
        }
        if v not in valid and v not in legacy:
            raise ValueError(
                f"'{v}' is not a recognised document type. "
                "Use a valid NDIS document type or one of the legacy categories."
            )
        return v


class ClientDocumentResponse(BaseModel):
    id: str
    client_id: str
    document_id: str
    document_type: str
    document_date: Optional[date]
    document_version: Optional[str]
    review_due_date: Optional[date]
    last_reviewed_date: Optional[date]
    review_cycle_days: Optional[int]
    is_current: bool
    is_required: bool
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class ClientDocumentListResponse(BaseModel):
    documents: List[ClientDocumentResponse]
    total: int


# =============================================================================
# Client Compliance Check Models
# =============================================================================

class ClientComplianceCheckTrigger(BaseModel):
    check_type: str = Field(..., pattern="^(document_completeness|document_currency|form_completeness|cross_document_validation|comprehensive)$")


class ClientComplianceFinding(BaseModel):
    finding_type: str
    severity: str = Field(..., pattern="^(critical|high|medium|low)$")
    message: str
    document_type: Optional[str] = None
    field_name: Optional[str] = None
    due_date: Optional[date] = None
    days_overdue: Optional[int] = None
    days_until_due: Optional[int] = None


class ClientComplianceCheckResponse(BaseModel):
    id: str
    client_id: str
    organization_id: str
    check_type: str
    status: str
    overall_score: Optional[int]
    findings: List[Dict[str, Any]]
    ai_model_used: Optional[str]
    ai_analysis_tokens_used: Optional[int]
    checked_documents: int
    created_by: Optional[str]
    created_at: datetime
    executed_at: Optional[datetime]
    next_check_scheduled_for: Optional[datetime]


class ClientComplianceCheckListResponse(BaseModel):
    checks: List[ClientComplianceCheckResponse]
    total: int
