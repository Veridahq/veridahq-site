"""
Compliance analysis service using Claude AI.

Provides two core AI operations:
1. classify_document()     — identifies the type of document (Call #1)
2. analyze_compliance_against_standard() — scores a document against a single
                             NDIS Practice Standard (Call #2 per standard)

Also provides run_full_scan_async() which orchestrates a full organisation-wide
compliance re-scan as a FastAPI BackgroundTask.
"""

import logging
import json
import asyncio
from datetime import datetime
from typing import Optional

import anthropic

from app.config import settings
from app.database import supabase_admin

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Anthropic client factory
# ---------------------------------------------------------------------------

def get_anthropic_client() -> anthropic.Anthropic:
    """Instantiate and return the Anthropic API client."""
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ---------------------------------------------------------------------------
# Helper: strip markdown code fences from JSON responses
# ---------------------------------------------------------------------------

def _clean_json_response(text: str) -> str:
    """Remove markdown code block wrappers that the model sometimes adds."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove opening fence (may include language tag e.g. ```json)
        lines = lines[1:]
        # Remove closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# ---------------------------------------------------------------------------
# Call #1: Document classification
# ---------------------------------------------------------------------------

async def classify_document(text: str, filename: str) -> dict:
    """
    Classify a document into one of the NDIS compliance document types.

    Uses the first ~3000 characters of the document plus the filename.

    Args:
        text: Extracted text content of the document.
        filename: Original filename (used as a classification hint).

    Returns:
        dict with keys:
            - document_type (str): one of the DocumentTypeEnum values
            - confidence (float): 0.0–1.0
            - reasoning (str): brief explanation
    """
    client = get_anthropic_client()

    document_types = [
        "privacy_policy",
        "incident_register",
        "staff_training_log",
        "service_agreement",
        "consent_form",
        "risk_management_plan",
        "complaints_register",
        "quality_improvement_plan",
        "worker_screening_check",
        "first_aid_certificate",
        "ndis_module_training",
        "participant_support_plan",
        "medication_management_plan",
        "behaviour_support_plan",
        "emergency_evacuation_plan",
        "unknown",
    ]

    prompt = f"""You are an expert NDIS compliance document classifier for Australian disability service providers.

Classify the document below into exactly one of the provided document types.

FILENAME: {filename}

DOCUMENT CONTENT (first 3000 characters):
{text[:3000] if text else "(no text extracted)"}

VALID DOCUMENT TYPES:
{chr(10).join(f"  - {dt}" for dt in document_types)}

Respond with a JSON object ONLY — no explanation outside the JSON:
{{
  "document_type": "<exact type from the list above>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<one sentence explanation of your classification>"
}}"""

    try:
        message = client.messages.create(
            model=settings.claude_model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text
        cleaned = _clean_json_response(raw)
        result = json.loads(cleaned)

        # Validate the returned type is in our allowed list
        if result.get("document_type") not in document_types:
            result["document_type"] = "unknown"

        logger.info(
            f"Document classified as '{result['document_type']}' "
            f"(confidence: {result.get('confidence', 0):.2f}) — {filename}"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error in document classification: {e}\nRaw response: {raw if 'raw' in dir() else 'N/A'}")
        return {
            "document_type": "unknown",
            "confidence": 0.0,
            "reasoning": f"Classification failed — JSON parse error: {e}",
        }
    except Exception as e:
        logger.error(f"Document classification API error: {e}")
        return {
            "document_type": "unknown",
            "confidence": 0.0,
            "reasoning": f"Classification failed: {e}",
        }


# ---------------------------------------------------------------------------
# Call #2: Compliance analysis against a single standard
# ---------------------------------------------------------------------------

async def analyze_compliance_against_standard(text: str, standard: dict) -> dict:
    """
    Analyse a document against a single NDIS Practice Standard.

    Args:
        text: Extracted document text (up to ~8000 chars is passed).
        standard: Full standard record from ndis_standards table.

    Returns:
        dict with keys:
            - score (int): 0–100
            - status (str): compliant | needs_attention | non_compliant | not_assessed
            - evidence_found (list[str]): specific evidence phrases from the document
            - gaps (list[str]): specific missing elements
            - remediation_action (str | None): recommended fix if non-compliant
            - risk_level (str | None): critical | high | medium | low (if non-compliant)
            - analysis_notes (str): professional summary
            - confidence (float): 0.0–1.0 AI confidence
    """
    client = get_anthropic_client()

    indicators_text = "\n".join(
        f"  {i+1}. {qi}" for i, qi in enumerate(standard.get("quality_indicators", []))
    )

    prompt = f"""You are a senior NDIS compliance auditor reviewing documents for Australian disability service providers.

Analyse the document against the NDIS Practice Standard below.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STANDARD {standard['standard_number']}: {standard['title']}
Category: {standard.get('category', '').replace('_', ' ').title()}

Description:
{standard['description']}

Quality Indicators to assess:
{indicators_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DOCUMENT CONTENT:
{text[:8000] if text else "(no text provided — mark as not_assessed)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Provide your analysis as a JSON object ONLY (no text outside the JSON):
{{
  "score": <integer 0-100>,
  "status": "<compliant|needs_attention|non_compliant|not_assessed>",
  "evidence_found": [
    "<specific quote or paraphrase from the document that supports compliance>",
    ...
  ],
  "gaps": [
    "<specific quality indicator or requirement NOT addressed in the document>",
    ...
  ],
  "remediation_action": "<specific, actionable recommendation — or null if compliant>",
  "risk_level": "<critical|high|medium|low — required if status is non_compliant or needs_attention, else null>",
  "analysis_notes": "<2-3 sentence professional audit summary>",
  "confidence": <float 0.0-1.0 reflecting your confidence in this assessment>
}}

SCORING GUIDE:
  90–100 : Fully compliant — comprehensive evidence for all indicators
  75–89  : Mostly compliant — minor gaps or missing documentation
  60–74  : Partially compliant — some significant gaps present
  40–59  : Significant compliance issues requiring prompt action
  1–39   : Severely non-compliant — major remediation needed
  0      : No relevant content found — use status: not_assessed

RISK LEVEL GUIDE (when non-compliant or needs_attention):
  critical : Immediate risk to participant safety or NDIS registration
  high     : Significant regulatory risk; likely to fail an audit
  medium   : Moderate gap; should be addressed within 3 months
  low      : Minor gap; low impact on participants or operations"""

    try:
        message = client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text
        cleaned = _clean_json_response(raw)
        result = json.loads(cleaned)

        # Validate and sanitise fields
        valid_statuses = {"compliant", "needs_attention", "non_compliant", "not_assessed"}
        if result.get("status") not in valid_statuses:
            result["status"] = "not_assessed"

        valid_risk_levels = {"critical", "high", "medium", "low", None}
        if result.get("risk_level") not in valid_risk_levels:
            result["risk_level"] = None

        # Ensure score is bounded
        score = result.get("score")
        if score is not None:
            result["score"] = max(0, min(100, int(score)))

        logger.debug(
            f"Standard {standard['standard_number']}: score={result.get('score')}, "
            f"status={result.get('status')}"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(
            f"JSON parse error analysing standard {standard['standard_number']}: {e}\n"
            f"Raw: {raw if 'raw' in dir() else 'N/A'}"
        )
        return _failed_analysis(f"JSON parse error: {e}")
    except Exception as e:
        logger.error(f"Compliance analysis API error for standard {standard['standard_number']}: {e}")
        return _failed_analysis(str(e))


def _failed_analysis(reason: str) -> dict:
    """Return a default 'failed' analysis result."""
    return {
        "score": 0,
        "status": "not_assessed",
        "evidence_found": [],
        "gaps": [],
        "remediation_action": None,
        "risk_level": None,
        "analysis_notes": f"Analysis could not be completed: {reason}",
        "confidence": 0.0,
    }


# ---------------------------------------------------------------------------
# Full organisation scan (BackgroundTask)
# ---------------------------------------------------------------------------

async def run_full_scan_async(org_id: str, doc_ids: list, job_id: str) -> None:
    """
    Run a full compliance scan across multiple documents for an organisation.

    This function is called as a FastAPI BackgroundTask. It:
    1. Fetches all active NDIS standards
    2. For each document, analyses against each standard
    3. Keeps the best-scoring result per standard across all documents
    4. Upserts compliance_scores and inserts gap_analysis records
    5. Refreshes the dashboard materialized view
    6. Marks the job as completed (or failed)

    Args:
        org_id: Organisation UUID
        doc_ids: List of document UUIDs to include in the scan
        job_id: Analysis job UUID for progress tracking
    """
    logger.info(f"[Job {job_id}] Starting full scan for org {org_id} ({len(doc_ids)} docs)")

    try:
        # Mark job as started
        supabase_admin.table("analysis_jobs").update({
            "status": "processing",
            "started_at": datetime.utcnow().isoformat(),
            "progress": 5,
        }).eq("id", job_id).execute()

        # Fetch all active NDIS standards
        standards_response = (
            supabase_admin.table("ndis_standards")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        standards = standards_response.data or []

        if not standards:
            _fail_job(job_id, "No active NDIS standards found in the database")
            return

        # Fetch document text
        docs_response = (
            supabase_admin.table("documents")
            .select("id, extracted_text, original_filename, document_type")
            .in_("id", doc_ids)
            .eq("processing_status", "completed")
            .execute()
        )
        docs = docs_response.data or []

        if not docs:
            _fail_job(job_id, "No completed documents with extracted text found for the provided IDs")
            return

        logger.info(f"[Job {job_id}] Scanning {len(docs)} docs against {len(standards)} standards")

        # best_scores[standard_id] = best analysis result across all docs
        best_scores: dict[str, dict] = {}
        total_work = len(docs) * len(standards)
        work_done = 0

        for doc in docs:
            doc_text = doc.get("extracted_text") or ""
            if not doc_text:
                logger.debug(f"[Job {job_id}] Skipping doc {doc['id']} — no extracted text")
                work_done += len(standards)
                continue

            from app.services.text_extractor import truncate_text
            text_for_analysis = truncate_text(doc_text, max_chars=8000)

            for standard in standards:
                std_id = standard["id"]
                analysis = await analyze_compliance_against_standard(text_for_analysis, standard)

                current_score = analysis.get("score") or 0
                current_best = best_scores.get(std_id)
                current_best_score = (current_best.get("score") or 0) if current_best else 0

                if current_best is None or current_score > current_best_score:
                    best_scores[std_id] = {
                        **analysis,
                        "document_id": doc["id"],
                        "standard_id": std_id,
                    }

                work_done += 1
                progress = 5 + int((work_done / total_work) * 80)
                supabase_admin.table("analysis_jobs").update(
                    {"progress": progress}
                ).eq("id", job_id).execute()

                # Brief pause to avoid API rate limits
                await asyncio.sleep(0.5)

        # Upsert best scores
        logger.info(f"[Job {job_id}] Upserting {len(best_scores)} compliance scores")

        for std_id, analysis in best_scores.items():
            score_record = {
                "organization_id": org_id,
                "document_id": analysis.get("document_id"),
                "standard_id": std_id,
                "score": analysis.get("score"),
                "status": analysis.get("status", "not_assessed"),
                "evidence_found": analysis.get("evidence_found") or [],
                "analysis_notes": analysis.get("analysis_notes"),
                "confidence": analysis.get("confidence", 0.0),
            }

            supabase_admin.table("compliance_scores").upsert(
                score_record,
                on_conflict="organization_id,document_id,standard_id",
            ).execute()

            # Create gap record if non-compliant / needs attention
            status = analysis.get("status")
            gaps = analysis.get("gaps") or []
            if status in ("non_compliant", "needs_attention") and gaps:
                risk_level = analysis.get("risk_level") or (
                    "critical" if status == "non_compliant" else "medium"
                )
                gap_description = "; ".join(gaps[:3])
                remediation = analysis.get("remediation_action") or "Review and address compliance gaps identified by this standard"

                # Avoid duplicating unresolved gaps for the same standard
                existing = (
                    supabase_admin.table("gap_analysis")
                    .select("id")
                    .eq("organization_id", org_id)
                    .eq("standard_id", std_id)
                    .eq("resolved", False)
                    .execute()
                )

                if not existing.data:
                    supabase_admin.table("gap_analysis").insert({
                        "organization_id": org_id,
                        "standard_id": std_id,
                        "document_id": analysis.get("document_id"),
                        "risk_level": risk_level,
                        "gap_description": gap_description,
                        "remediation_action": remediation,
                    }).execute()

        # Mark progress near complete
        supabase_admin.table("analysis_jobs").update({"progress": 95}).eq("id", job_id).execute()

        # Refresh dashboard
        try:
            supabase_admin.rpc("refresh_dashboard_summary").execute()
            logger.info(f"[Job {job_id}] Dashboard materialized view refreshed")
        except Exception as e:
            logger.warning(f"[Job {job_id}] Could not refresh materialized view: {e}")

        # Mark job complete
        supabase_admin.table("analysis_jobs").update({
            "status": "completed",
            "progress": 100,
            "completed_at": datetime.utcnow().isoformat(),
            "result": {
                "standards_analysed": len(best_scores),
                "documents_processed": len(docs),
                "gaps_created": sum(
                    1 for a in best_scores.values()
                    if a.get("status") in ("non_compliant", "needs_attention")
                    and a.get("gaps")
                ),
            },
        }).eq("id", job_id).execute()

        logger.info(f"[Job {job_id}] Full scan completed for org {org_id}")

    except Exception as e:
        logger.error(f"[Job {job_id}] Full scan failed: {e}", exc_info=True)
        _fail_job(job_id, str(e))


def _fail_job(job_id: str, reason: str) -> None:
    """Mark an analysis job as failed with an error message."""
    try:
        supabase_admin.table("analysis_jobs").update({
            "status": "failed",
            "error_message": reason,
            "completed_at": datetime.utcnow().isoformat(),
        }).eq("id", job_id).execute()
    except Exception as e:
        logger.error(f"Failed to mark job {job_id} as failed: {e}")
