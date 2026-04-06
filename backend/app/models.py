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
    PRIVACY_POLICY = "privacy_policy"
    INCIDENT_REGISTER = "incident_register"
    STAFF_TRAINING_LOG = "staff_training_log"
    SERVICE_AGREEMENT = "service_agreement"
    CONSENT_FORM = "consent_form"
    RISK_MANAGEMENT_PLAN = "risk_management_plan"
    COMPLAINTS_REGISTER = "complaints_register"
    QUALITY_IMPROVEMENT_PLAN = "quality_improvement_plan"
    WORKER_SCREENING_CHECK = "worker_screening_check"
    FIRST_AID_CERTIFICATE = "first_aid_certificate"
    NDIS_MODULE_TRAINING = "ndis_module_training"
    PARTICIPANT_SUPPORT_PLAN = "participant_support_plan"
    MEDICATION_MANAGEMENT_PLAN = "medication_management_plan"
    BEHAVIOUR_SUPPORT_PLAN = "behaviour_support_plan"
    EMERGENCY_EVACUATION_PLAN = "emergency_evacuation_plan"
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
