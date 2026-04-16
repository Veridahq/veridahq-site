-- Migration 007: Fix client_compliance_checks status constraint
--
-- The original constraint only allowed: passed, failed, warning, not_applicable.
-- The application code inserts status='processing' as the initial state when a
-- check is triggered, which violated the constraint and caused a 500 on every
-- compliance check trigger.
--
-- This migration drops the old constraint and replaces it with one that also
-- allows 'processing' as a valid status value.

ALTER TABLE client_compliance_checks
    DROP CONSTRAINT IF EXISTS client_compliance_checks_status_check;

ALTER TABLE client_compliance_checks
    ADD CONSTRAINT client_compliance_checks_status_check
    CHECK (status IN ('processing', 'passed', 'failed', 'warning', 'not_applicable'));
