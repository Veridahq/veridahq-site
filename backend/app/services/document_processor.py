"""
Document processing pipeline.

Orchestrates the full document analysis workflow as a FastAPI BackgroundTask:

  Step 1 — Mark job and document as "processing"
  Step 2 — Extract text from the uploaded file (PDF / DOCX / TXT)
  Step 3 — Classify document type with Claude (API call #1)
  Step 4 — Persist extracted text and classification result
  Step 5 — Analyse document against all 17 NDIS standards (API call #2 per standard)
  Step 6 — Persist compliance scores and gap records
  Step 7 — Mark document and job as "completed"
  Step 8 — Refresh the dashboard materialized view
"""

import logging
import asyncio
from datetime import datetime

from app.database import supabase_admin
from app.services.text_extractor import extract_text, truncate_text
from app.services.compliance_analyzer import (
    classify_document,
    analyze_compliance_against_standard,
    _fail_job,
)

logger = logging.getLogger(__name__)

# Maximum characters stored in the database for extracted text
MAX_STORED_TEXT_CHARS = 100_000


async def process_document_async(
    doc_id: str,
    org_id: str,
    job_id: str,
    content: bytes,
    original_filename: str,
    suffix: str,
) -> None:
    """
    Full document processing pipeline (called as a FastAPI BackgroundTask).

    Args:
        doc_id: UUID of the document record
        org_id: UUID of the owning organisation
        job_id: UUID of the analysis_jobs record to update
        content: Raw file bytes
        original_filename: User-supplied filename (used for classification hint)
        suffix: File extension e.g. '.pdf'
    """
    logger.info(f"[Job {job_id}] Processing document {doc_id} ({original_filename})")

    try:
        # ----------------------------------------------------------------
        # Step 1: Mark job and document as processing
        # ----------------------------------------------------------------
        supabase_admin.table("analysis_jobs").update({
            "status": "processing",
            "started_at": datetime.utcnow().isoformat(),
            "progress": 10,
        }).eq("id", job_id).execute()

        supabase_admin.table("documents").update({
            "processing_status": "processing",
        }).eq("id", doc_id).execute()

        # ----------------------------------------------------------------
        # Step 2: Extract text
        # ----------------------------------------------------------------
        logger.info(f"[Job {job_id}] Extracting text from '{original_filename}'")
        extracted_text = extract_text(content, suffix)

        if not extracted_text:
            logger.warning(f"[Job {job_id}] No text extracted from '{original_filename}'")
        else:
            logger.info(f"[Job {job_id}] Extracted {len(extracted_text)} chars")

        _update_job_progress(job_id, 25)

        # ----------------------------------------------------------------
        # Step 3: Classify document type (Claude API call #1)
        # ----------------------------------------------------------------
        logger.info(f"[Job {job_id}] Classifying document type")
        text_for_classification = truncate_text(extracted_text, max_chars=3000) if extracted_text else ""
        classification = await classify_document(text_for_classification, original_filename)

        document_type = classification.get("document_type", "unknown")
        classification_confidence = float(classification.get("confidence", 0.0))
        classification_reasoning = classification.get("reasoning", "")

        logger.info(
            f"[Job {job_id}] Classified as '{document_type}' "
            f"(confidence {classification_confidence:.2f})"
        )

        _update_job_progress(job_id, 40)

        # ----------------------------------------------------------------
        # Step 4: Persist extracted text and classification
        # ----------------------------------------------------------------
        stored_text = extracted_text[:MAX_STORED_TEXT_CHARS] if extracted_text else None

        supabase_admin.table("documents").update({
            "extracted_text": stored_text,
            "document_type": document_type,
            "metadata": {
                "classification_confidence": classification_confidence,
                "classification_reasoning": classification_reasoning,
                "text_length": len(extracted_text) if extracted_text else 0,
                "text_truncated_in_db": bool(
                    extracted_text and len(extracted_text) > MAX_STORED_TEXT_CHARS
                ),
            },
        }).eq("id", doc_id).execute()

        _update_job_progress(job_id, 45)

        # ----------------------------------------------------------------
        # Step 5 & 6: Compliance analysis (Claude API call #2 per standard)
        # ----------------------------------------------------------------
        if extracted_text:
            standards_response = (
                supabase_admin.table("ndis_standards")
                .select("*")
                .eq("is_active", True)
                .execute()
            )
            standards = standards_response.data or []
            total_standards = len(standards)

            if not standards:
                logger.warning(f"[Job {job_id}] No active NDIS standards found — skipping analysis")
            else:
                logger.info(f"[Job {job_id}] Analysing against {total_standards} standards")
                text_for_analysis = truncate_text(extracted_text, max_chars=8000)

                for idx, standard in enumerate(standards):
                    std_id = standard["id"]

                    analysis = await analyze_compliance_against_standard(
                        text_for_analysis, standard
                    )

                    # Upsert compliance score
                    score_record = {
                        "organization_id": org_id,
                        "document_id": doc_id,
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

                    # Create gap record if warranted
                    status = analysis.get("status")
                    gaps = analysis.get("gaps") or []
                    if status in ("non_compliant", "needs_attention") and gaps:
                        risk_level = analysis.get("risk_level") or (
                            "critical" if status == "non_compliant" else "medium"
                        )
                        gap_description = "; ".join(gaps[:3])
                        remediation = (
                            analysis.get("remediation_action")
                            or "Review and address the compliance gaps identified for this standard"
                        )

                        # Check we haven't already created a gap for this doc+standard
                        existing_gap = (
                            supabase_admin.table("gap_analysis")
                            .select("id")
                            .eq("organization_id", org_id)
                            .eq("standard_id", std_id)
                            .eq("document_id", doc_id)
                            .execute()
                        )

                        if not existing_gap.data:
                            supabase_admin.table("gap_analysis").insert({
                                "organization_id": org_id,
                                "standard_id": std_id,
                                "document_id": doc_id,
                                "risk_level": risk_level,
                                "gap_description": gap_description,
                                "remediation_action": remediation,
                            }).execute()

                    # Progress: analysis phase spans 45% → 90%
                    progress = 45 + int(((idx + 1) / total_standards) * 45)
                    _update_job_progress(job_id, progress)

                    # Rate-limit friendly pause between API calls
                    await asyncio.sleep(0.3)

        else:
            logger.info(f"[Job {job_id}] No text to analyse — skipping compliance step")
            _update_job_progress(job_id, 90)

        # ----------------------------------------------------------------
        # Step 7: Mark document as completed
        # ----------------------------------------------------------------
        supabase_admin.table("documents").update({
            "processing_status": "completed",
        }).eq("id", doc_id).execute()

        # ----------------------------------------------------------------
        # Step 8: Refresh dashboard materialized view
        # ----------------------------------------------------------------
        try:
            supabase_admin.rpc("refresh_dashboard_summary").execute()
            logger.debug(f"[Job {job_id}] Dashboard view refreshed")
        except Exception as e:
            logger.warning(f"[Job {job_id}] Could not refresh dashboard view: {e}")

        # Mark job complete
        supabase_admin.table("analysis_jobs").update({
            "status": "completed",
            "progress": 100,
            "completed_at": datetime.utcnow().isoformat(),
            "result": {
                "document_type": document_type,
                "text_extracted": bool(extracted_text),
                "text_length": len(extracted_text) if extracted_text else 0,
                "classification_confidence": classification_confidence,
            },
        }).eq("id", job_id).execute()

        logger.info(f"[Job {job_id}] Document {doc_id} processing complete")

    except Exception as e:
        logger.error(
            f"[Job {job_id}] Document processing failed for {doc_id}: {e}",
            exc_info=True,
        )

        # Mark document as failed
        try:
            supabase_admin.table("documents").update({
                "processing_status": "failed",
                "processing_error": str(e),
            }).eq("id", doc_id).execute()
        except Exception as db_e:
            logger.error(f"[Job {job_id}] Could not update document failure state: {db_e}")

        # Mark job as failed
        _fail_job(job_id, str(e))


def _update_job_progress(job_id: str, progress: int) -> None:
    """Helper to update job progress without raising exceptions."""
    try:
        supabase_admin.table("analysis_jobs").update(
            {"progress": progress}
        ).eq("id", job_id).execute()
    except Exception as e:
        logger.warning(f"Could not update progress for job {job_id}: {e}")
