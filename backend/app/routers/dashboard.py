"""Dashboard summary routes."""

import logging
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Depends

from app.database import supabase_admin
from app.models import DashboardResponse
from app.routers.auth import get_current_user
from app.routers.documents import get_user_org

logger = logging.getLogger(__name__)
router = APIRouter()

# Total number of NDIS Core Module standards (used in fallback calculation)
TOTAL_NDIS_STANDARDS = 17


def _score_to_traffic_light(score: float | None) -> str:
    """Convert a numeric compliance score to a traffic light colour string."""
    if score is None:
        return "grey"
    if score >= 80:
        return "green"
    if score >= 60:
        return "amber"
    return "red"


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------
@router.get("/", response_model=DashboardResponse)
async def get_dashboard(auth_data: dict = Depends(get_current_user)):
    """
    Get a comprehensive dashboard summary for the current organisation.

    Attempts to read from the pre-computed materialized view for performance.
    Falls back to live aggregation queries if the view has not been populated.
    """
    org_id = get_user_org(auth_data)

    # ---- Attempt 1: Read from materialized view ----
    mv_response = (
        supabase_admin.table("dashboard_summary")
        .select("*")
        .eq("organization_id", org_id)
        .single()
        .execute()
    )

    if mv_response.data:
        data = mv_response.data

        # Calculate days until audit
        days_until_audit = None
        raw_audit_date = data.get("audit_date")
        if raw_audit_date:
            try:
                audit_date_obj = date.fromisoformat(raw_audit_date)
                days_until_audit = (audit_date_obj - date.today()).days
            except (ValueError, TypeError):
                pass

        overall_score = data.get("overall_compliance_score")
        if overall_score is not None:
            overall_score = float(overall_score)

        return DashboardResponse(
            organization_id=data["organization_id"],
            organization_name=data["organization_name"],
            plan_tier=data["plan_tier"],
            audit_date=date.fromisoformat(raw_audit_date) if raw_audit_date else None,
            days_until_audit=days_until_audit,
            total_documents=data.get("total_documents") or 0,
            overall_compliance_score=overall_score,
            traffic_light=_score_to_traffic_light(overall_score),
            compliant_standards=data.get("compliant_standards") or 0,
            needs_attention_standards=data.get("needs_attention_standards") or 0,
            non_compliant_standards=data.get("non_compliant_standards") or 0,
            not_assessed_standards=data.get("not_assessed_standards") or 0,
            critical_gaps=data.get("critical_gaps") or 0,
            high_gaps=data.get("high_gaps") or 0,
            medium_gaps=data.get("medium_gaps") or 0,
            low_gaps=data.get("low_gaps") or 0,
            pending_documents=data.get("pending_documents") or 0,
            last_refreshed=(
                datetime.fromisoformat(data["last_refreshed"])
                if data.get("last_refreshed")
                else None
            ),
        )

    # ---- Attempt 2: Live aggregation fallback ----
    logger.info(f"Materialized view miss for org {org_id}, computing live dashboard")

    org_response = (
        supabase_admin.table("organizations")
        .select("*")
        .eq("id", org_id)
        .single()
        .execute()
    )

    if not org_response.data:
        raise HTTPException(status_code=404, detail="Organisation not found")

    org = org_response.data

    # Documents
    docs_response = (
        supabase_admin.table("documents")
        .select("id, processing_status", count="exact")
        .eq("organization_id", org_id)
        .execute()
    )
    total_docs = docs_response.count or 0
    docs_data = docs_response.data or []
    pending_docs = sum(1 for d in docs_data if d["processing_status"] == "pending")

    # Compliance scores
    scores_response = (
        supabase_admin.table("compliance_scores")
        .select("score, status")
        .eq("organization_id", org_id)
        .execute()
    )
    scores_data = scores_response.data or []
    scored = [s for s in scores_data if s.get("score") is not None]
    overall_score = round(sum(s["score"] for s in scored) / len(scored), 2) if scored else None

    # Gaps (unresolved only)
    gaps_response = (
        supabase_admin.table("gap_analysis")
        .select("risk_level")
        .eq("organization_id", org_id)
        .eq("resolved", False)
        .execute()
    )
    gaps_data = gaps_response.data or []

    # Audit date and countdown
    raw_audit_date = org.get("audit_date")
    audit_date = date.fromisoformat(raw_audit_date) if raw_audit_date else None
    days_until_audit = (audit_date - date.today()).days if audit_date else None

    return DashboardResponse(
        organization_id=org_id,
        organization_name=org["name"],
        plan_tier=org.get("plan_tier", "essentials"),
        audit_date=audit_date,
        days_until_audit=days_until_audit,
        total_documents=total_docs,
        overall_compliance_score=overall_score,
        traffic_light=_score_to_traffic_light(overall_score),
        compliant_standards=sum(1 for s in scores_data if s["status"] == "compliant"),
        needs_attention_standards=sum(1 for s in scores_data if s["status"] == "needs_attention"),
        non_compliant_standards=sum(1 for s in scores_data if s["status"] == "non_compliant"),
        not_assessed_standards=TOTAL_NDIS_STANDARDS - len(scores_data),
        critical_gaps=sum(1 for g in gaps_data if g["risk_level"] == "critical"),
        high_gaps=sum(1 for g in gaps_data if g["risk_level"] == "high"),
        medium_gaps=sum(1 for g in gaps_data if g["risk_level"] == "medium"),
        low_gaps=sum(1 for g in gaps_data if g["risk_level"] == "low"),
        pending_documents=pending_docs,
        last_refreshed=None,
    )


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------
@router.post("/refresh")
async def refresh_dashboard(auth_data: dict = Depends(get_current_user)):
    """
    Manually trigger a refresh of the dashboard materialized view.

    This is called automatically after compliance scans complete.
    Can also be triggered manually by any authenticated user.
    """
    try:
        supabase_admin.rpc("refresh_dashboard_summary").execute()
        logger.info(f"Dashboard materialized view refreshed by user {auth_data['user'].id}")
        return {"message": "Dashboard refreshed successfully"}
    except Exception as e:
        logger.warning(f"Could not refresh materialized view: {e}")
        return {"message": "Dashboard will update automatically after the next scan completes"}
