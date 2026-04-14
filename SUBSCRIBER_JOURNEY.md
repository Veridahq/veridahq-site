# Verida — Subscriber Journey Audit
**Audited:** 2026-04-14  
**Auditor:** Claude (subscriber-journey-complete branch)  
**Scope:** Full end-to-end journey from landing page to long-term customer

---

## Stage 1 — Discovery (veridahq.com)

### What the user is trying to do
Understand what Verida does, decide whether it fits their NDIS provider business, and either sign up or find contact info.

### What they CAN do today
- Read marketing copy, features, how-it-works, pricing (three tiers: Essentials $49, Growth $149, Scale $349), FAQ, and testimonials.
- Toggle monthly/annual pricing.
- Click "Sign Up Free" → opens pilot signup modal.
- Click "Sign In" → opens login modal.
- Open a "Forgot password" flow from the login modal.
- Subscribe to newsletter (stored locally only—no API call, no list management).
- Try demo mode.

### What's missing or broken
- **Hero metric ("Average Compliance Score — Sunrise Support Services")** shows a live-counter animation to 94%. The associated company name makes it look like a customer case study; without written consent from a real customer this is problematic.
- **Social proof avatars** (SS, CA, PS, +5) and **testimonials** reference invented companies (Sunrise Support Services, Community Advocates, Peak Services). Until these are real or clearly labelled as examples, they're legally risky.
- **Newsletter form** stores email in localStorage only — no server, no CRM, no actual subscription.
- **Footer links** for Privacy Policy, Terms of Service, Security, and the four "Company" links point to `#privacy`, `#terms`, etc. — dead anchors with no destination pages.
- **"Join 100+ NDIS providers"** CTA claim has no basis and should not be displayed until earned.
- The landing page is missing an explicit ABN / legal entity footer line (required for Australian B2B SaaS credibility).

### What a provider would reasonably expect
- Real privacy policy and terms of service pages (required before sign-up agreement).
- Genuine social proof or clearly labelled example scenarios.
- Contact info beyond an email address (phone or form for enterprise queries).

---

## Stage 2 — Signup

### What they CAN do today
- Fill the pilot modal (org name, full name, email, password, participant count, terms checkbox) and submit.
- Receive a verification email (Supabase sends this; it redirects to `/verify-email.html`).
- The backend correctly creates an auth user, an organisation, and a profile in one transaction.
- Backend validates participant count is not exposed yet — it's captured in the form but silently discarded (`select` element is never sent to the API).

### What's missing or broken
- **BUG (P0): `verify-email.html` stores the session token under `'authToken'` but `app.js` reads `'accessToken'`.** After clicking the verification link the user lands on verify-email.html, which parses the token, calls `/api/auth/me`, then does `localStorage.setItem('authToken', token)`. When they're redirected to `app.html` 2 seconds later, `app.js` line 131 checks `localStorage.getItem('accessToken')` — finds nothing — and renders the login screen. The user must then log in manually. The signup → verify → dashboard flow is broken.
- **Participant count** from the signup form is never sent to the API, so `plan_tier` is always `'essentials'` for new orgs regardless of what the user selected.
- No **"welcome" email** is sent after sign-up (just the Supabase verification email which is unbranded unless Resend is configured).
- The app.html sign-up view (accessible from "Don't have an account?") requires a minimum 6-character password, but the landing page modal enforces 8 characters. Inconsistency.

### What a provider would expect
- Smooth email verification → instant dashboard access, no second login required.
- Their chosen plan tier saved from the very first interaction.
- A branded welcome email explaining what to do next.

---

## Stage 3 — First-run Onboarding (empty dashboard)

### What they CAN do today
- See the full compliance dashboard immediately after login.
- If they have no documents yet, the modules grid shows "No compliance data yet. Upload a document to start your compliance analysis."
- Documents tab shows "No documents yet. Upload your first document to begin compliance scanning."
- Clients tab shows "No clients yet. Add your first client to start managing their NDIS compliance."

### What's missing or broken
- **No guided onboarding checklist** explaining the 3–5 first steps (upload policy docs, set audit date, add clients, add staff). A provider landing on an empty dashboard has no structured path forward.
- **No audit date prompt.** NDIS providers have a scheduled audit date; the platform should immediately ask for it so it can show a countdown and prioritise gaps by urgency. The field exists in the `organizations` table but is never surfaced in setup.
- The **trend chart** renders 13 weeks of interpolated fake data even for brand-new accounts with no history (score ramping from 0 to 0 across 13 weeks is meaningless noise).
- The **Compliance Trend** label says "Last 90 Days" but there is no historical `compliance_score_history` table — the trend is always a monotone curve derived from the single current score.
- Stats on the score card ("Standards Met: 18 of 20", "Critical Gaps: 2", "Documents: 8") show hardcoded placeholder values on first load in demo mode — this bleeds through to real empty accounts during the brief loading window.
- The notification bell (🔔) is a dead icon — clicking it does nothing.

### What a provider would expect
- A clear "Getting started" checklist or step-by-step wizard.
- Prompt to enter their upcoming audit date on first login.
- An honest "Score: Not assessed — upload documents to begin" state instead of a meaningless gauge at 0%.

---

## Stage 4 — Document Upload

### What they CAN do today
- Upload single files (PDF, DOCX, TXT) via drag-and-drop or file picker.
- See documents listed with filename, upload date, processing status badge.
- Open, download, or delete uploaded documents.
- View document details including AI-detected document type and compliance scores per standard.
- Connect SharePoint/OneDrive via OAuth to sync folders automatically (P1 feature already shipped).

### What's missing or broken
- **No bulk upload.** Providers will have 20–100 existing documents. One-at-a-time is a friction wall.
- **No retry on failure.** If processing fails (AI error, parsing error), the card shows "Failed" with no "Retry" button. The user must delete and re-upload.
- **No supported-type hint in the UI.** "PDF, DOCX, TXT" is accepted but not communicated in the upload zone — providers often have XLS registers they'll try to upload.
- **No file size hint.** 50 MB limit exists server-side but is not shown in the UI.
- **Processing state polling** relies on the user manually refreshing the documents list. There's no auto-refresh or WebSocket push — a document in "Processing" state will never auto-update to "Completed" unless the user leaves and comes back.
- **Only three file formats accepted** — DOCX, PDF, TXT. CSV and XLSX registers (staff training logs, incident registers) cannot be uploaded.
- **No source tagging visible.** Documents synced from SharePoint show identically to manual uploads — no integration badge or deep-link back to the source.

### What a provider would expect
- Bulk upload / folder drop.
- Clear file type and size limits before attempting.
- Auto-refresh when a document finishes processing.
- Retry button for failed documents.
- "Synced from SharePoint" badge on integration documents.

---

## Stage 5 — Classification + Scoring

### What they CAN do today
- Each uploaded document is AI-classified into one of 150+ NDIS document types.
- The document detail modal shows: type, file size, upload date, processing status, compliance scores per standard, and any processing error.
- Compliance scores/tab shows overall score, per-standard breakdown, and category averages.

### What's missing or broken
- **No classification override.** If Claude misclassifies a document (e.g., a custom "Safety Plan" is labeled as "unknown"), the user cannot correct it. There's no UI to manually set `document_type`.
- **Compliance scores show as 0–100 but context is missing.** A score of 65 means "needs attention" but the user doesn't know what specifically failed or what evidence was found. The `evidence_found` and `analysis_notes` fields exist in the DB and API response but are not surfaced in the document detail modal.
- **The per-standard scores in the document detail modal** multiply `s.score * 100` (line 1074 in app.js) — but compliance scores are already stored as 0–100 (not 0–1). This means a score of 80 renders as 8000%. **This is a rendering bug.**
- **No "re-scan" button per document** — if a user uploads a new version, they must delete and re-upload.
- The **17 NDIS Practice Standards** aren't labelled — just standard numbers and titles without the context of which Module they belong to.

### What a provider would expect
- Ability to override the AI's document type classification.
- Visible evidence snippets and analysis notes explaining why a score was given.
- A "Re-scan" button per document after upload corrections.
- Standards labelled with their Module (Core / Module 1 / Module 2 / 2A) for NDIS-literate context.

---

## Stage 6 — Client Management

### What they CAN do today
- Add clients with full NDIS participant info (name, DOB, NDIS number, plan dates, behaviour support flag).
- View client cards and a detail view.
- Link uploaded documents to clients with document type, dates, and review due dates.
- Trigger an AI compliance check per client.
- List and filter client documents.
- Soft-delete clients.

### What's missing or broken
- **BUG (P0): `renderComplianceResults()` always renders hardcoded demo data** (4 fake categories: Personal Planning & Budgeting, Plan Implementation, Incident Management, Safeguarding) regardless of whether the user is in demo mode or has real compliance checks. Real client compliance checks from the API are never fetched and displayed in the UI.
- **No Edit Client button/form.** The `PUT /clients/{id}` API endpoint exists but there is no UI to invoke it. Providers need to update plan dates, contact info, and status frequently.
- **Client plan expiry** (`current_plan_end_date`) is displayed as a raw date with no visual warning when expiry is approaching (< 30/60/90 days out). A plan that expires tomorrow looks identical to one with 2 years left.
- **Compliance check results** only show the `check_type`, `status`, and `overall_score` — the full `findings` JSONB array (which contains specific gap descriptions) is never rendered.
- **Behaviour support flag** is the only disability-support indicator; there's no free-text "notes" or "support needs" field visible in the add/edit form even though `review_notes` exists in the schema.
- The `triggerClientComplianceCheck()` sends a POST without a `check_type` field — the backend defaults to... nothing (the model requires `check_type`). This will 422-error in production.

### What a provider would expect
- Edit client capability — plan dates, contact info, status.
- Colour-coded plan expiry warnings (red/amber based on days remaining).
- Real compliance check findings displayed, not demo placeholders.
- A summary of which mandatory documents are missing per client.

---

## Stage 7 — Staff Management

### What they CAN do today
- Add staff members (creates a Supabase auth account, sends a password-reset email).
- View a staff list with name, role, and basic action buttons.
- Edit a staff member's role (member/admin/owner).
- Remove a staff member from the organisation.

### What's missing or broken
- **Staff certification/training tracking shows "Not checked"** for all three columns (Disability Awareness, First Aid, NDIS Standards) for every real staff member, always. There is no data model, API, or UI to record or display certifications. The columns in the table are purely cosmetic.
- **No `staff_certifications` or `worker_certifications` table** exists in any migration. NDIS auditors will ask to see current Worker Screening Checks, First Aid certificates, and NDIS Module training records for all staff. This is one of the most commonly failed audit areas.
- **The initial HTML** of the staff tab contains hardcoded demo rows (Sarah Johnson, Marcus Chen, Emma Rodriguez, David Park, Lisa Thompson) that flash briefly before real data loads. This is confusing.
- **No expiry tracking** — even if certifications were entered, there's no alert when a first aid cert or worker screening check is about to expire.
- **No bulk import** — a provider with 20 staff cannot efficiently add them all.
- **No staff profile page** — clicking "View" on any hardcoded demo row shows a "Staff details coming soon" toast. Real staff members have no detail view either.

### What a provider would expect
- Ability to record Worker Screening Check number + expiry, First Aid cert + expiry, NDIS Orientation Module completion, and any other training.
- Traffic light (green/amber/red) per certification column based on expiry date.
- Email alert (or in-app notification) when a certification is expiring within 30/60 days.

---

## Stage 8 — Compliance Dashboard

### What they CAN do today
- See an overall compliance score gauge, stat counts (standards met, critical gaps, documents).
- See a compliance trend chart (13 weeks).
- See modules grid grouping standards by category.
- See a "Top Compliance Gaps" list with severity badges.
- Click "View Remediation" on a gap.

### What's missing or broken
- **Gap remediation detail shows "coming soon"** — `viewGapRemediation()` always calls `showToast('Remediation details coming soon.', 'info')` even for real gaps with real `remediation_action` text in the database.
- **Compliance trend is fabricated.** There is no `compliance_score_history` table. The chart generates a monotone ramp from a fraction of the current score. This is misleading — a provider may falsely believe their score was improving for the past 13 weeks.
- **Audit date countdown** (`days_until_audit`) is returned by the dashboard API but is never displayed in the UI. Providers urgently need "58 days until your NDIS audit" as a persistent nudge.
- **No per-standard drilldown** — clicking a module card does nothing. There's no way to see which specific documents are evidencing a standard.
- **The gauge chart** uses a half-doughnut (circumference: 180) which looks odd at 0% and doesn't clearly communicate the scale.
- The `stat-detail` div under "Standards Met" hardcodes "of 20" — this should come from `total_standards` in the API response.

### What a provider would expect
- Full remediation steps for each gap (already stored in DB — just not shown).
- Real compliance trend history (requires a history table — migration needed).
- Days until audit prominently displayed.
- Per-standard drilldown showing which documents cover each standard.

---

## Stage 9 — Reports / Exports

### What they CAN do today
- See a "Reports" tab with three hardcoded demo cards (Monthly Compliance Summary, Audit Readiness Assessment, Gap Analysis Report).
- Click "Download PDF" → "coming soon" toast.
- Click "Generate Report" → "Check your email in a few moments" toast (no email is actually sent).

### What's missing or broken
- **Reports are 100% hardcoded demo content.** None of the three cards reflect the user's actual data. A real user's compliance score is 0%, their gaps are real, but the reports show "94% compliant, 18 of 20 standards met".
- **No PDF generation** endpoint or library exists in the backend.
- **No Excel/CSV export** of the gap analysis for use in internal quality meetings.
- **`generateReport()` promises to send an email** but there is no email template, no backend endpoint, and no scheduled job to generate or deliver anything.
- For an NDIS audit, the provider needs: (a) an Audit Readiness Report, (b) a Gap Analysis Report, (c) a Document Register. None of these exist.

### What a provider would expect
- A printable/downloadable Compliance Summary showing their actual score, standard-by-standard breakdown, and unresolved gaps.
- An exportable document register (doc name, type, upload date, classification, compliance status).
- A Gap Analysis export (gap description, risk level, standard, remediation action, resolved status).
- Reports dated and branded with their organisation name.

---

## Stage 10 — Renewals + Notifications

### What they CAN do today
- Nothing. The notification bell (🔔) is a static icon — clicking it does nothing.

### What's missing or broken
- **No in-app notification system.** No data model, no API, no UI.
- **No email alerts for expiring documents** — `review_due_date` exists on `client_documents` and `review_frequency_days` on `document_requirements`, but no background job queries these.
- **No expiry alerts for staff certifications** — no certification table exists.
- **No NDIS plan renewal alerts** — `current_plan_end_date` on `clients` is never checked against today's date to generate a warning.
- **No dashboard "expiring soon" widget** showing the 5 most urgently expiring items.
- This is arguably the highest-value feature for a compliance SaaS — the whole point is to prevent things from slipping.

### What a provider would expect
- An in-app notifications panel listing upcoming renewals, overdue reviews, and recently identified gaps.
- Email digest (weekly or on-event) for things expiring within 30 days.
- A "Renewals" or "Upcoming" section on the dashboard.

---

## Stage 11 — Settings + Admin

### What they CAN do today
- See org name, current plan, and number of participants (all disabled/read-only).
- Toggle notification checkboxes (state is not persisted — checkboxes reset on page reload).
- See billing plan info (hardcoded "Growth / $149/month").
- See "Connected Storage" (SharePoint/OneDrive integration — fully functional).
- Click "Manage Billing" → "coming soon" toast.
- Click "Download Your Data" → "coming soon" toast.
- Click "Delete Account" → toast saying to contact support.

### What's missing or broken
- **Org settings form is entirely disabled** — every input has `disabled` attribute. No fields can be edited, and no save endpoint is called. Providers need to update: org name, ABN, NDIS registration number, address, audit date, registration modules.
- **Notification preferences are not persisted** — checkboxes have no associated save action. Changes are lost on reload.
- **No user profile editing** — there's no way to change your own name or email in-app.
- **Billing section shows hardcoded plan** — no integration with actual subscription state.
- **`loadIntegrations()` is never called** when the Settings tab is opened (it's only called after returning from OAuth). The Connected Storage section will always show a blank panel until the user goes through the OAuth flow.
- The settings tab has no "Team Members" section within settings itself — staff management is a separate tab (which is fine) but org settings should show member count and invite link.
- **Audit date** can only be set by a developer via SQL — there is no UI for it even though it's in the schema and drives the dashboard countdown.

### What a provider would expect
- An editable org profile: name, ABN, NDIS registration, address, audit date, registration modules.
- Saved notification preferences.
- A way to edit their own name and potentially email.
- Visible billing/plan status linked to reality.

---

## Stage 12 — Billing

### What they CAN do today
- See a hardcoded billing section showing "Growth / $149/month / Renewal Date: May 1, 2024".
- Click "Manage Billing" → toast.

### What's missing or broken
- **No payment infrastructure at all.** No Stripe, no webhook, no subscription record in the DB. The `plan_tier` column on `organizations` exists but is set at signup and never changes.
- **No plan upgrade/downgrade flow.**
- **No invoice history.**
- **No seat limits enforced** — the pricing page says "no per-seat fees" but document storage limits (1GB / 5GB / unlimited) are not enforced.
- **Trial period** (3 months free) is mentioned on the landing page but is not tracked or enforced anywhere.
- **This is a full user decision (pricing, Stripe setup, invoice template design).** Flag for Afe.

### What a provider would expect
- Transparent current plan + renewal date.
- Ability to upgrade/downgrade.
- Download invoices for accounting purposes.
- Clear notice if approaching plan limits.

---

## Stage 13 — Help / Support

### What they CAN do today
- Email hello@veridahq.com (footer link).
- Read the FAQ on the landing page.

### What's missing or broken
- **No in-app help.** No tooltips, no "?" buttons, no contextual guidance anywhere in the dashboard.
- **No knowledge base or documentation site.**
- **No support chat widget** (Intercom, Crisp, etc.).
- **No tutorial or video walkthrough.**
- The FAQ answers reference features that are coming soon ("API integrations", "mock audit") — managing expectations is important.

### What a provider would expect
- Contextual help tooltips for complex compliance terminology (e.g., what does "Standard 1.4 — Governance and Operational Management" mean in practice?).
- A "Contact Support" button inside the app (not just an email in the footer).
- A short guided tour on first login.

---

## Stage 14 — Account Lifecycle

### What they CAN do today
- Reset their password via a branded email (fully functional via Resend).
- Sign out.
- Email verification on signup (functional, but see token-key bug in Stage 2).

### What's missing or broken
- **Data export is "coming soon"** — NDIS providers have data portability obligations under the Privacy Act; this should not be left as a toast.
- **Account deletion** redirects to "contact support" — no self-serve flow.
- **No profile editing** — users cannot change their display name or email.
- **No "leave organisation"** flow for staff members who change jobs.
- **Session expiry handling** — when the JWT expires (1 hour), the user gets silently redirected to the login page with no message explaining why. Token refresh logic is implemented server-side but the client never calls `/auth/refresh` before expiry.

---

## Gap Inventory & Prioritisation

### P0 — Ship-Blockers (subscriber literally cannot do the job without these)

| # | Gap | Location | Why it blocks |
|---|-----|----------|---------------|
| P0-1 | **`verify-email.html` stores `'authToken'` but `app.js` reads `'accessToken'`** | `verify-email.html:103`, `app.js:131` | After email verification the user is sent to the login screen instead of the dashboard. Breaks the core signup flow. |
| P0-2 | **`renderComplianceResults()` always shows hardcoded demo data** | `app.js:1499` | Real client compliance check results are never displayed. A provider sees fake data for their real clients. |
| P0-3 | **Org settings form is fully disabled** | `app.html:496–509` | No way to set ABN, NDIS registration number, or audit date — all critical for NDIS compliance context. |
| P0-4 | **`loadIntegrations()` never called on Settings tab open** | `app.js:412–427` | Connected Storage section renders blank unless user just returned from OAuth flow. |
| P0-5 | **Gap remediation always shows "coming soon"** | `app.js:1168` | The core compliance value prop — "here's what to fix" — is a dead button. `remediation_action` is in the DB but never shown. |
| P0-6 | **Compliance score percentage bug** — multiplies score×100 in document detail | `app.js:1074` | Score of 80 displays as 8000%. |
| P0-7 | **`triggerClientComplianceCheck()` sends no `check_type`** | `app.js:1687` | POST to `/clients/{id}/compliance-check` will 422-error (required field missing). |
| P0-8 | **Reports tab is 100% hardcoded demo** | `app.html:423–483`, `app.js:2150` | No real data, no export, no generation. Providers need audit-ready reports. |

### P1 — Obvious Misses (any provider would expect this; absence looks amateur)

| # | Gap | Location |
|---|-----|----------|
| P1-1 | First-run onboarding: no checklist or "what to do first" guidance on empty dashboard | `app.js:855` |
| P1-2 | Audit date countdown not shown on dashboard (field exists, API returns it, UI ignores it) | `app.js:870` |
| P1-3 | Notification bell does nothing — no expiry alert system at all | `app.html:184` |
| P1-4 | Staff certification tracking — no DB table, no API, columns always "Not checked" | all of `staff.py`, `app.js:1764` |
| P1-5 | No Edit Client UI (PUT endpoint exists, no button/form to invoke it) | `app.js:1330` |
| P1-6 | Client plan expiry: no colour-coded warning when plan end date is near | `app.js:1232` |
| P1-7 | Compliance trend chart uses fabricated data — no history table | `app.js:882` |
| P1-8 | Notification preferences not persisted (checkbox values lost on reload) | `app.html:512` |
| P1-9 | Evidence snippets and analysis notes not shown in document detail modal | `app.js:1045` |
| P1-10 | No document type classification override | `app.js:844` |

### P2 — Polish (improves retention; absence is tolerable at launch)

| # | Gap |
|---|-----|
| P2-1 | Auto-refresh document list when processing completes (polling or push) |
| P2-2 | Bulk document upload |
| P2-3 | Retry button for failed documents |
| P2-4 | Per-standard drilldown on compliance dashboard |
| P2-5 | Staff bulk import |
| P2-6 | File type/size hints in upload zone |
| P2-7 | "Synced from SharePoint" badge on integration documents |
| P2-8 | Knowledge base / in-app help tooltips |
| P2-9 | JWT refresh before silent expiry |
| P2-10 | Session "why was I logged out" message |
| P2-11 | Self-serve account deletion |
| P2-12 | Data export (Privacy Act compliance) |

### Deferred (flag for Afe — require non-technical decisions)

| Item | Why deferred |
|------|-------------|
| **Billing / Stripe integration** | Requires pricing confirmation, Stripe account, invoice design, refund policy, trial period enforcement logic |
| **Email notification digests** | Requires choosing ESP configuration, email template design, unsubscribe flow, and a scheduled background job (Celery/cron) — infrastructure decision |
| **Privacy Policy + Terms of Service** | Legal document — needs a lawyer or standard NDIS SaaS template reviewed by Afe |
| **Compliance trend history table** | Requires a new migration + background job to snapshot scores periodically — architectural decision on snapshot cadence |
| **Real testimonials / social proof** | Requires customer permission or removal |
| **"Join 100+ providers" claim** | Remove or replace with honest language until earned |
| **Welcome email after signup** | Requires Resend template design and copy approval |

---

*This document was generated as part of the `claude/subscriber-journey-complete` branch. Each P0 and P1 (except deferred items) is addressed by commits on this branch.*
