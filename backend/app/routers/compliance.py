"""Compliance analysis routes."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks

from app.database import supabase_admin
from app.models import (
    OverallComplianceResponse,
    ComplianceStatusEnum,
    GapListResponse,
    GapResponse,
    GapResolveRequest,
    ComplianceScanRequest,
    ComplianceScanResponse,
    NDISStandardListResponse,
    NDISStandardResponse,
)
from app.routers.auth import get_current_user
from app.routers.documents import get_user_org
from app.services.compliance_analyzer import run_full_scan_async

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: map numeric score to traffic light colour
# ---------------------------------------------------------------------------
def score_to_traffic_light(score: Optional[float]) -> str:
    """Convert a numeric compliance score (0-100) to a traffic light colour string."""
    if score is None:
        return "grey"
    if score >= 80:
        return "green"
    if score >= 60:
        return "amber"
    return "red"


# ---------------------------------------------------------------------------
# GET /standards
# ---------------------------------------------------------------------------
@router.get("/standards", response_model=NDISStandardListResponse)
async def get_standards(
    category: Optional[str] = Query(
        None,
        description="Filter by category: governance, operational_management, provision_of_supports, support_provision_environment",
    ),
    auth_data: dict = Depends(get_current_user),
):
    """
    Retrieve all active NDIS Practice Standards.

    Optionally filtered by category. Standards are sorted by standard_number.
    """
    query = (
        supabase_admin.table("ndis_standards")
        .select("*")
        .eq("is_active", True)
        .order("standard_number")
    )

    if category:
        query = query.eq("category", category)

    response = query.execute()
    standards = response.data or []

    return NDISStandardListResponse(
        standards=[NDISStandardResponse(**s) for s in standards],
        total=len(standards),
    )


# ---------------------------------------------------------------------------
# GET /scores
# ---------------------------------------------------------------------------
@router.get("/scores", response_model=OverallComplianceResponse)
async def get_compliance_scores(
    auth_data: dict = Depends(get_current_user),
):
    """
    Get the overall compliance score and per-standard breakdown for the organisation.

    Returns:
    - overall_score: average across all scored standards
    - traffic_light: green / amber / red / grey
    - Per-standard scores with evidence and notes
    - Breakdown by NDIS standard category
    """
    org_id = get_user_org(auth_data)

    # Fetch all active NDIS standards
    standards_response = (
        supabase_admin.table("ndis_standards")
        .select("*")
        .eq("is_active", True)
        .execute()
    )
    standards = {s["id"]: s for s in (standards_response.data or [])}

    # Fetch compliance scores joined with standard metadata
    scores_response = (
        supabase_admin.table("compliance_scores")
        .select("*, ndis_standards(standard_number, title, category)")
        .eq("organization_id", org_id)
        .execute()
    )
    scores_data = scores_response.data or []

    # Calculate overall score (average of all scored standards)
    scored = [s for s in scores_data if s.get("score") is not None]
    overall_score = round(sum(s["score"] for s in scored) / len(scored), 2) if scored else 0.0

    # Count by status
    status_counts = {
        "compliant": 0,
        "needs_attention": 0,
        "non_compliant": 0,
        "not_assessed": 0,
    }
    for s in scores_data:
        key = s.get("status", "not_assessed")
        if key in status_counts:
            status_counts[key] += 1

    # Standards with no score record are "not assessed"
    assessed_standard_ids = {s["standard_id"] for s in scores_data}
    not_assessed_count = len(standards) - len(assessed_standard_ids) + status_counts["not_assessed"]

    # Group scores by NDIS category for category-level breakdown
    scores_by_category: dict = {}
    for score in scores_data:
        std = score.get("ndis_standards") or {}
        category = std.get("category", "unknown")
        if category not in scores_by_category:
            scores_by_category[category] = {"raw_scores": [], "count": 0, "average": None}
        if score.get("score") is not None:
            scores_by_category[category]["raw_scores"].append(score["score"])
        scores_by_category[category]["count"] += 1

    # Compute category averages and clean up temp key
    for cat, data in scores_by_category.items():
        raw = data.pop("raw_scores")
        scores_by_category[cat]["average"] = round(sum(raw) / len(raw), 2) if raw else None

    # Determine overall compliance status
    if overall_score >= 80:
        overall_status = ComplianceStatusEnum.COMPLIANT
    elif overall_score >= 60:
        overall_status = ComplianceStatusEnum.NEEDS_ATTENTION
    else:
        overall_status = ComplianceStatusEnum.NON_COMPLIANT

    # Build scores list with standard metadata inline
    scores_list = []
    for s in scores_data:
        std = s.get("ndis_standards") or {}
        scores_list.append({
            "id": s["id"],
            "organization_id": s["organization_id"],
            "document_id": s.get("document_id"),
            "standard_id": s["standard_id"],
            "standard_number": std.get("standard_number"),
            "standard_title": std.get("title"),
            "standard_category": std.get("category"),
            "score": s.get("score"),
            "status": s.get("status", "not_assessed"),
            "evidence_found": s.get("evidence_found") or [],
            "analysis_notes": s.get("analysis_notes"),
            "confidence": s.get("confidence"),
            "created_at": s.get("created_at"),
        })

    return OverallComplianceResponse(
        overall_score=overall_score,
        status=overall_status,
        traffic_light=score_to_traffic_light(overall_score),
        total_standards=len(standards),
        compliant_count=status_counts["compliant"],
        needs_attention_count=status_counts["needs_attention"],
        non_compliant_count=status_counts["non_compliant"],
        not_assessed_count=not_assessed_count,
        scores_by_category=scores_by_category,
        scores=scores_list,
    )


# ---------------------------------------------------------------------------
# GET /gaps
# ---------------------------------------------------------------------------
@router.get("/gaps", response_model=GapListResponse)
async def get_gaps(
    risk_level: Optional[str] = Query(None, description="Filter: critical, high, medium, low"),
    resolved: Optional[bool] = Query(False, description="Show resolved gaps (default: unresolved only)"),
    auth_data: dict = Depends(get_current_user),
):
    """
    Get compliance gaps for the organisation, sorted by risk priority.

    By default returns only unresolved gaps. Pass resolved=true to see resolved gaps.
    """
    org_id = get_user_org(auth_data)

    query = (
        supabase_admin.table("gap_analysis")
        .select("*, ndis_standards(standard_number, title)")
        .eq("organization_id", org_id)
    )

    if resolved is not None:
        query = query.eq("resolved", resolved)
    if risk_level:
        query = query.eq("risk_level", risk_level)

    query = query.order("priority_order", nulls_last=True)
    response = query.execute()
    gaps_data = response.data or []

    # Secondary sort by risk level priority
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    gaps_data.sort(key=lambda g: risk_order.get(g.get("risk_level", "low"), 3))

    gaps = []
    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for g in gaps_data:
        std = g.get("ndis_standards") or {}
        rl = g.get("risk_level", "low")
        if rl in risk_counts:
            risk_counts[rl] += 1

        gaps.append(
            GapResponse(
                id=g["id"],
                organization_id=g["organization_id"],
                standard_id=g["standard_id"],
                standard_number=std.get("standard_number"),
                standard_title=std.get("title"),
                document_id=g.get("document_id"),
                risk_level=rl,
                gap_description=g["gap_description"],
                remediation_action=g["remediation_action"],
                priority_order=g.get("priority_order"),
                resolved=g.get("resolved", False),
                resolved_at=g.get("resolved_at"),
                created_at=g["created_at"],
            )
        )

    return GapListResponse(
        gaps=gaps,
        total=len(gaps),
        critical_count=risk_counts["critical"],
        high_count=risk_counts["high"],
        medium_count=risk_counts["medium"],
        low_count=risk_counts["low"],
    )


# ---------------------------------------------------------------------------
# PATCH /gaps/{gap_id}/resolve
# ---------------------------------------------------------------------------
@router.patch("/gaps/{gap_id}/resolve")
async def resolve_gap(
    gap_id: str,
    request: GapResolveRequest,
    auth_data: dict = Depends(get_current_user),
):
    """
    Mark a compliance gap as resolved or re-open it.

    Records the resolver's user ID and resolution timestamp.
    """
    org_id = get_user_org(auth_data)
    user_id = auth_data["user"].id

    update_data: dict = {
        "resolved": request.resolved,
        "resolved_at": None,
        "resolved_by": None,
    }

    if request.resolved:
        update_data["resolved_at"] = datetime.utcnow().isoformat()
        update_data["resolved_by"] = user_id

    response = (
        supabase_admin.table("gap_analysis")
        .update(update_data)
        .eq("id", gap_id)
        .eq("organization_id", org_id)
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Gap not found")

    action = "resolved" if request.resolved else "re-opened"
    logger.info(f"Gap {gap_id} {action} by user {user_id}")

    return {
        "message": f"Gap has been marked as {action}",
        "gap_id": gap_id,
        "resolved": request.resolved,
    }


# ---------------------------------------------------------------------------
# POST /scan
# ---------------------------------------------------------------------------
@router.post("/scan", response_model=ComplianceScanResponse)
async def trigger_scan(
    request: ComplianceScanRequest,
    background_tasks: BackgroundTasks,
    auth_data: dict = Depends(get_current_user),
):
    """
    Trigger a full compliance re-scan for the organisation.

    Optionally specify document_ids to scan a subset. If omitted, all
    completed documents are included.

    Returns immediately with a job ID for polling.
    """
    org_id = get_user_org(auth_data)

    # Determine which documents to scan
    query = (
        supabase_admin.table("documents")
        .select("id")
        .eq("organization_id", org_id)
        .eq("processing_status", "completed")
    )

    if request.document_ids:
        query = query.in_("id", request.document_ids)

    docs_response = query.execute()
    doc_ids = [d["id"] for d in (docs_response.data or [])]

    if not doc_ids:
        raise HTTPException(
            status_code=400,
            detail="No processed documents available for scanning. "
                   "Upload and process at least one document first.",
        )

    # Create a scan job record
    job_response = supabase_admin.table("analysis_jobs").insert({
        "organization_id": org_id,
        "job_type": "full_scan",
        "status": "queued",
        "progress": 0,
    }).execute()

    job_id = job_response.data[0]["id"] if job_response.data else "unknown"

    # Enqueue background scan
    background_tasks.add_task(
        run_full_scan_async,
        org_id=org_id,
        doc_ids=doc_ids,
        job_id=job_id,
    )

    logger.info(f"Full scan queued: job {job_id} for org {org_id}, {len(doc_ids)} documents")

    return ComplianceScanResponse(
        job_id=job_id,
        message=f"Full compliance scan has been queued for {len(doc_ids)} document(s).",
        documents_queued=len(doc_ids),
    )


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------
@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    auth_data: dict = Depends(get_current_user),
):
    """
    Get the current status and progress of an analysis job.

    Use this endpoint to poll a job returned from /upload or /scan.
    """
    org_id = get_user_org(auth_data)

    response = (
        supabase_admin.table("analysis_jobs")
        .select("*")
        .eq("id", job_id)
        .eq("organization_id", org_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Job not found")

    return response.data


# ---------------------------------------------------------------------------
# GET /jobs
# ---------------------------------------------------------------------------
@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status: queued, processing, completed, failed"),
    limit: int = Query(20, ge=1, le=100),
    auth_data: dict = Depends(get_current_user),
):
    """List recent analysis jobs for the organisation."""
    org_id = get_user_org(auth_data)

    query = (
        supabase_admin.table("analysis_jobs")
        .select("*")
        .eq("organization_id", org_id)
        .order("created_at", desc=True)
        .limit(limit)
    )

    if status:
        query = query.eq("status", status)

    response = query.execute()

    return {
        "jobs": response.data or [],
        "total": len(response.data or []),
    }
