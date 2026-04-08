"""
Client-level compliance analysis service using Claude AI.

Provides AI-powered validation for:
1. Document completeness (required docs present)
2. Document currency (review cycles met)
3. Form completeness (mandatory fields filled)
4. Cross-document validation (consistency checks)
5. Comprehensive check (all of above orchestrated)
"""

import logging
import json
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

import anthropic

from app.config import settings
from app.database import supabase_admin

logger = logging.getLogger(__name__)


def get_anthropic_client() -> anthropic.Anthropic:
    """Instantiate and return the Anthropic API client."""
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _clean_json_response(text: str) -> str:
    """Remove markdown code block wrappers that the model sometimes adds."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# =============================================================================
# Check 1: Document Completeness
# =============================================================================

async def check_document_completeness(
    client_id: str,
    org_id: str,
    client_data: dict,
) -> dict:
    """
    Check if all required documents are present for a client.

    Returns:
        dict with keys:
            - status: 'passed' | 'failed' | 'warning'
            - score: int 0-100
            - findings: list of findings
    """
    client = get_anthropic_client()

    # Fetch required documents for this client's circumstances
    req_response = supabase_admin.table("document_requirements").select("*").eq(
        "organization_id", org_id
    ).execute()
    org_reqs = {r["document_type"]: r for r in (req_response.data or [])}

    # Fetch global defaults
    global_req_response = supabase_admin.table("document_requirements").select("*").is_(
        "organization_id", "null"
    ).execute()
    global_reqs = {r["document_type"]: r for r in (global_req_response.data or [])}

    # Merge with org overrides
    all_reqs = {**global_reqs, **org_reqs}
    mandatory_reqs = {k: v for k, v in all_reqs.items() if v.get("is_mandatory")}

    # Fetch client's documents
    docs_response = supabase_admin.table("client_documents").select(
        "document_type, is_current"
    ).eq("client_id", client_id).eq("status", "active").execute()
    client_docs = {d["document_type"] for d in (docs_response.data or []) if d.get("is_current")}

    # Identify missing
    missing_docs = set(mandatory_reqs.keys()) - client_docs
    findings = []

    if missing_docs:
        for doc_type in missing_docs:
            findings.append({
                "finding_type": "missing_document",
                "document_type": doc_type,
                "severity": "critical" if mandatory_reqs[doc_type].get("is_mandatory") else "medium",
                "message": f"Required document '{doc_type}' is missing or not current",
            })

    # Score: percentage of required documents present
    if mandatory_reqs:
        score = int(((len(mandatory_reqs) - len(missing_docs)) / len(mandatory_reqs)) * 100)
    else:
        score = 100

    status = "passed" if not missing_docs else ("failed" if len(missing_docs) > 2 else "warning")

    logger.info(f"Document completeness check for client {client_id}: score={score}, missing={len(missing_docs)}")

    return {
        "status": status,
        "score": score,
        "findings": findings,
        "check_type": "document_completeness",
    }


# =============================================================================
# Check 2: Document Currency
# =============================================================================

async def check_document_currency(client_id: str) -> dict:
    """
    Check if client documents are current (within review cycles).

    Returns:
        dict with status, score, and findings about overdue reviews.
    """
    # Fetch all documents linked to this client
    docs_response = supabase_admin.table("client_documents").select("*").eq(
        "client_id", client_id
    ).eq("status", "active").execute()
    docs = docs_response.data or []

    findings = []
    overdue_count = 0
    due_soon_count = 0

    today = datetime.now().date()

    for doc in docs:
        if not doc.get("is_required"):
            continue

        review_due = doc.get("review_due_date")
        if not review_due:
            continue

        from datetime import datetime as dt
        due_date = dt.fromisoformat(review_due).date() if isinstance(review_due, str) else review_due
        days_overdue = (today - due_date).days

        if days_overdue > 0:
            overdue_count += 1
            findings.append({
                "finding_type": "document_overdue",
                "document_type": doc.get("document_type"),
                "severity": "critical" if days_overdue > 90 else ("high" if days_overdue > 30 else "medium"),
                "message": f"Review overdue by {days_overdue} days",
                "due_date": str(review_due),
                "days_overdue": days_overdue,
            })
        elif days_overdue > -30:
            due_soon_count += 1
            findings.append({
                "finding_type": "document_due_soon",
                "document_type": doc.get("document_type"),
                "severity": "low",
                "message": f"Review due in {abs(days_overdue)} days",
                "due_date": str(review_due),
                "days_until_due": abs(days_overdue),
            })

    # Score based on currency
    total_required = len([d for d in docs if d.get("is_required")])
    if total_required == 0:
        score = 100
    else:
        current_count = total_required - overdue_count
        score = int((current_count / total_required) * 100)

    status = "passed" if overdue_count == 0 else ("failed" if overdue_count > 1 else "warning")

    logger.info(f"Document currency check for client {client_id}: score={score}, overdue={overdue_count}")

    return {
        "status": status,
        "score": score,
        "findings": findings,
        "check_type": "document_currency",
    }


# =============================================================================
# Check 3: Form Completeness (AI-assisted)
# =============================================================================

async def check_form_completeness(
    client_id: str,
    org_id: str,
) -> dict:
    """
    Use Claude to assess whether mandatory fields in client documents are filled.

    Fetches key documents for the client and asks Claude to validate field presence.
    """
    client = get_anthropic_client()

    # Fetch client profile
    client_response = supabase_admin.table("clients").select("*").eq("id", client_id).single().execute()
    if not client_response.data:
        return {
            "status": "not_applicable",
            "score": 0,
            "findings": [{"finding_type": "client_not_found", "severity": "critical", "message": "Client not found"}],
            "check_type": "form_completeness",
        }

    client_data = client_response.data

    # Fetch recent documents with extracted text
    docs_response = supabase_admin.table("client_documents").select(
        "document_id, document_type, is_required"
    ).eq("client_id", client_id).eq("status", "active").limit(5).execute()
    doc_links = docs_response.data or []

    if not doc_links:
        return {
            "status": "not_applicable",
            "score": 0,
            "findings": [{"finding_type": "no_documents", "severity": "medium", "message": "No documents available for completeness check"}],
            "check_type": "form_completeness",
        }

    # Fetch document text
    doc_ids = [d["document_id"] for d in doc_links]
    full_docs_response = supabase_admin.table("documents").select(
        "id, extracted_text, document_type"
    ).in_("id", doc_ids).eq("processing_status", "completed").execute()
    full_docs = full_docs_response.data or []

    if not full_docs:
        return {
            "status": "warning",
            "score": 50,
            "findings": [{"finding_type": "no_text_extracted", "severity": "medium", "message": "Documents lack extracted text for analysis"}],
            "check_type": "form_completeness",
        }

    # Build document summary for Claude
    doc_summary = "\n\n".join([
        f"## {d.get('document_type', 'Unknown')} Document\n{(d.get('extracted_text') or '')[:2000]}"
        for d in full_docs
    ])

    prompt = f"""You are an NDIS compliance auditor reviewing participant documents for completeness.

CLIENT INFORMATION:
- Participant Name: {client_data.get('first_name')} {client_data.get('last_name')}
- NDIS Number: {client_data.get('ndis_participant_number')}
- Plan Period: {client_data.get('current_plan_start_date')} to {client_data.get('current_plan_end_date')}

DOCUMENTS AVAILABLE:
{doc_summary}

Assess whether the provided documents contain MANDATORY FIELDS required for NDIS compliance:
1. Participant/support recipient name and identifier
2. Support coordination contact information
3. Authorized goals and objectives
4. Clear support arrangements and responsibilities
5. Frequency and duration of supports
6. Risk mitigation strategies (if applicable)
7. Review and approval dates/signatures

Respond with a JSON object ONLY:
{{
  "overall_status": "<COMPLETE|MOSTLY_COMPLETE|INCOMPLETE|CRITICAL_GAPS>",
  "overall_score": <int 0-100>,
  "fields_analysis": [
    {{
      "field_name": "<mandatory field>",
      "presence": "<present|missing|unclear>",
      "documents_found_in": ["<doc_type>"],
      "severity": "<critical|high|medium|low>"
    }}
  ],
  "summary": "<brief assessment of form completeness>"
}}"""

    try:
        message = client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text
        cleaned = _clean_json_response(raw)
        result = json.loads(cleaned)

        # Normalize status
        status_map = {
            "COMPLETE": "passed",
            "MOSTLY_COMPLETE": "warning",
            "INCOMPLETE": "warning",
            "CRITICAL_GAPS": "failed",
        }
        status = status_map.get(result.get("overall_status", "INCOMPLETE"), "warning")
        score = result.get("overall_score", 50)

        # Convert fields to findings
        findings = []
        for field in result.get("fields_analysis", []):
            if field.get("presence") != "present":
                findings.append({
                    "finding_type": "missing_field",
                    "field_name": field.get("field_name"),
                    "severity": field.get("severity", "medium"),
                    "message": f"Field '{field.get('field_name')}' is {field.get('presence', 'missing')}",
                })

        logger.info(f"Form completeness check for client {client_id}: score={score}, status={status}")

        return {
            "status": status,
            "score": score,
            "findings": findings,
            "check_type": "form_completeness",
        }

    except Exception as e:
        logger.error(f"Form completeness check error for client {client_id}: {e}")
        return {
            "status": "warning",
            "score": 0,
            "findings": [{"finding_type": "analysis_error", "severity": "high", "message": f"Could not complete analysis: {str(e)}"}],
            "check_type": "form_completeness",
        }


# =============================================================================
# Check 4: Cross-Document Validation
# =============================================================================

async def check_cross_document_validation(client_id: str) -> dict:
    """
    Use Claude to check consistency and cross-references across multiple documents.

    E.g., verify goals in support plan match service agreement, dates align, etc.
    """
    client = get_anthropic_client()

    # Fetch multiple document types
    docs_response = supabase_admin.table("client_documents").select(
        "document_id, document_type"
    ).eq("client_id", client_id).eq("status", "active").in_(
        "document_type", ["individual_support_plan", "service_agreement", "goals_plan", "behaviour_support_plan"]
    ).limit(4).execute()
    doc_links = docs_response.data or []

    if len(doc_links) < 2:
        return {
            "status": "not_applicable",
            "score": 100,
            "findings": [],
            "check_type": "cross_document_validation",
        }

    # Fetch document text
    doc_ids = [d["document_id"] for d in doc_links]
    full_docs_response = supabase_admin.table("documents").select(
        "id, extracted_text, document_type"
    ).in_("id", doc_ids).eq("processing_status", "completed").execute()
    full_docs = full_docs_response.data or []

    if len(full_docs) < 2:
        return {
            "status": "warning",
            "score": 50,
            "findings": [{"finding_type": "insufficient_docs", "severity": "medium", "message": "Fewer than 2 documents available for cross-validation"}],
            "check_type": "cross_document_validation",
        }

    # Build document content for Claude
    doc_text = "\n\n---\n\n".join([
        f"### {d.get('document_type', 'Unknown').upper()}\n{(d.get('extracted_text') or '')[:1500]}"
        for d in full_docs
    ])

    prompt = f"""You are an NDIS compliance auditor reviewing multiple participant support documents for consistency.

DOCUMENTS:
{doc_text}

Check for the following cross-document validations:
1. Goals/objectives consistency across documents
2. Support arrangements alignment (frequency, duration, provider roles)
3. Timeline/date consistency (plan period, review dates, duration)
4. Participant needs and support provided match
5. Risk mitigation strategies mentioned in multiple places
6. Funding/budget references align with support arrangements

Respond with a JSON object ONLY:
{{
  "overall_consistency": "<FULLY_CONSISTENT|MOSTLY_CONSISTENT|INCONSISTENCIES|CONFLICTS>",
  "overall_score": <int 0-100>,
  "validations": [
    {{
      "validation_area": "<area being checked>",
      "status": "<consistent|inconsistent|missing>",
      "severity": "<critical|high|medium|low>",
      "finding": "<description of result>"
    }}
  ],
  "summary": "<brief cross-document assessment>"
}}"""

    try:
        message = client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text
        cleaned = _clean_json_response(raw)
        result = json.loads(cleaned)

        # Normalize status
        status_map = {
            "FULLY_CONSISTENT": "passed",
            "MOSTLY_CONSISTENT": "warning",
            "INCONSISTENCIES": "warning",
            "CONFLICTS": "failed",
        }
        status = status_map.get(result.get("overall_consistency", "INCONSISTENCIES"), "warning")
        score = result.get("overall_score", 50)

        # Convert to findings
        findings = []
        for val in result.get("validations", []):
            if val.get("status") != "consistent":
                findings.append({
                    "finding_type": "validation_" + val.get("status", "unknown"),
                    "validation_area": val.get("validation_area"),
                    "severity": val.get("severity", "medium"),
                    "message": val.get("finding"),
                })

        logger.info(f"Cross-document validation for client {client_id}: score={score}, status={status}")

        return {
            "status": status,
            "score": score,
            "findings": findings,
            "check_type": "cross_document_validation",
        }

    except Exception as e:
        logger.error(f"Cross-document validation error for client {client_id}: {e}")
        return {
            "status": "warning",
            "score": 50,
            "findings": [{"finding_type": "analysis_error", "severity": "high", "message": f"Could not complete validation: {str(e)}"}],
            "check_type": "cross_document_validation",
        }


# =============================================================================
# Orchestrator: Comprehensive Check
# =============================================================================

async def run_comprehensive_client_check(
    client_id: str,
    org_id: str,
    created_by_user_id: Optional[str] = None,
) -> dict:
    """
    Run all checks and aggregate results into a comprehensive compliance assessment.

    Returns a dict ready for insertion into client_compliance_checks table.
    """
    logger.info(f"Starting comprehensive compliance check for client {client_id}")

    # Fetch client data
    client_response = supabase_admin.table("clients").select("*").eq("id", client_id).single().execute()
    if not client_response.data:
        raise ValueError(f"Client {client_id} not found")

    client_data = client_response.data

    # Run all checks in parallel
    completeness = await check_document_completeness(client_id, org_id, client_data)
    currency = await check_document_currency(client_id)
    form_completeness = await check_form_completeness(client_id, org_id)
    cross_validation = await check_cross_document_validation(client_id)

    # Aggregate
    all_checks = [completeness, currency, form_completeness, cross_validation]
    all_findings = []
    for check in all_checks:
        all_findings.extend(check.get("findings", []))

    # Calculate overall score (average of non-zero scores)
    scores = [c.get("score", 0) for c in all_checks if c.get("score")]
    overall_score = int(sum(scores) / len(scores)) if scores else 0

    # Determine overall status
    failed_count = sum(1 for c in all_checks if c.get("status") == "failed")
    warning_count = sum(1 for c in all_checks if c.get("status") == "warning")

    if failed_count > 0:
        overall_status = "failed"
    elif warning_count > 0:
        overall_status = "warning"
    else:
        overall_status = "passed"

    logger.info(f"Comprehensive check for client {client_id}: score={overall_score}, status={overall_status}, findings={len(all_findings)}")

    return {
        "client_id": client_id,
        "organization_id": org_id,
        "check_type": "comprehensive",
        "status": overall_status,
        "overall_score": overall_score,
        "findings": all_findings,
        "ai_model_used": settings.claude_model,
        "ai_analysis_tokens_used": 0,  # Would need to track from actual API calls
        "checked_documents": 0,
        "created_by": created_by_user_id,
        "executed_at": datetime.utcnow().isoformat(),
    }
