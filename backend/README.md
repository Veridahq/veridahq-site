# Verida Compliance API

Production FastAPI backend for the Verida NDIS compliance management platform. Powered by Supabase for data storage/auth and Claude AI for intelligent document analysis.

---

## Overview

Verida helps Australian NDIS service providers manage compliance against the NDIS Practice Standards. Upload your compliance documents (policies, registers, plans) and the AI automatically:

1. Classifies the document type
2. Analyses it against all 17 NDIS Core Module Practice Standards
3. Scores each standard (0–100) and assigns a status: compliant / needs_attention / non_compliant
4. Identifies specific gaps and generates remediation recommendations
5. Aggregates results into a live dashboard with traffic light indicators

---

## Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) project (free tier works)
- An [Anthropic](https://console.anthropic.com) API key with access to Claude
- pip or uv for package management

---

## Local Setup

### 1. Clone and enter the backend directory

```bash
git clone <repo-url>
cd backend
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your Supabase URL, keys, and Anthropic API key (see Environment Variables table below).

### 5. Run the development server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/health

---

## Supabase Setup

### 1. Create a new Supabase project

Go to https://supabase.com/dashboard and create a new project.

### 2. Run migrations (in order)

In the Supabase SQL Editor, run each migration file in sequence:

```
supabase/migrations/001_create_tables.sql
supabase/migrations/002_rls_policies.sql
supabase/migrations/003_indexes.sql
supabase/migrations/004_materialized_view.sql
```

### 3. Seed the NDIS standards

```
supabase/seed.sql
```

This inserts all 17 NDIS Core Module Practice Standards.

### 4. Create Storage bucket

In the Supabase Dashboard:
- Go to Storage
- Create a new bucket named `documents`
- Set it to **private** (access via service role only)

### 5. Enable Email Auth

In Authentication → Providers → Email:
- Enable "Email" provider
- Configure your SMTP settings for production (or use Supabase's built-in email for dev)

### 6. Copy your API keys

In Settings → API:
- Copy the `anon` public key to `SUPABASE_KEY`
- Copy the `service_role` secret key to `SUPABASE_SERVICE_KEY`
- Copy the Project URL to `SUPABASE_URL`

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase anon (public) key |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key (never expose publicly) |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `CLAUDE_MODEL` | No | Claude model ID (default: `claude-opus-4-6`) |
| `DEBUG` | No | Enable debug logging (default: `false`) |
| `APP_NAME` | No | API display name |
| `APP_VERSION` | No | API version string |
| `STORAGE_BUCKET` | No | Supabase Storage bucket name (default: `documents`) |
| `MAX_FILE_SIZE_MB` | No | Maximum upload size in MB (default: `50`) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

---

## API Endpoints Reference

### Authentication (`/api/auth`)

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/signup` | Register new user (+ optionally create org) |
| POST | `/api/auth/signin` | Sign in, receive JWT tokens |
| POST | `/api/auth/signout` | Invalidate session |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/reset-password` | Send password reset email |
| POST | `/api/auth/update-password` | Update password (requires auth) |
| GET | `/api/auth/me` | Get current user profile + organisation |

### Organisations (`/api/organizations`)

| Method | Path | Description |
|---|---|---|
| POST | `/api/organizations/` | Create a new organisation |
| GET | `/api/organizations/{id}` | Get organisation details |
| PUT | `/api/organizations/{id}` | Update organisation (admin+) |
| GET | `/api/organizations/{id}/members` | List organisation members |
| PATCH | `/api/organizations/{id}/members/{user_id}/role` | Update member role (owner only) |

### Documents (`/api/documents`)

| Method | Path | Description |
|---|---|---|
| POST | `/api/documents/upload` | Upload a document (PDF/DOCX/TXT) |
| GET | `/api/documents/` | List documents (paginated, filterable) |
| GET | `/api/documents/{id}` | Get document details + extracted text |
| DELETE | `/api/documents/{id}` | Delete document + storage file |
| GET | `/api/documents/{id}/jobs` | List analysis jobs for a document |

### Compliance (`/api/compliance`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/compliance/standards` | List all NDIS Practice Standards |
| GET | `/api/compliance/scores` | Overall compliance scores breakdown |
| GET | `/api/compliance/gaps` | List compliance gaps (filterable) |
| PATCH | `/api/compliance/gaps/{id}/resolve` | Mark a gap as resolved |
| POST | `/api/compliance/scan` | Trigger a full compliance re-scan |
| GET | `/api/compliance/jobs/{id}` | Get analysis job status |
| GET | `/api/compliance/jobs` | List recent analysis jobs |

### Dashboard (`/api/dashboard`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/dashboard/` | Get dashboard summary statistics |
| POST | `/api/dashboard/refresh` | Refresh materialized view |

### System

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (returns 200 when running) |
| GET | `/` | API info |

---

## Document Processing Pipeline

```
User uploads file (PDF / DOCX / TXT)
         |
         v
POST /api/documents/upload
  [1] Validate file type and size
  [2] Upload raw file to Supabase Storage
  [3] Create documents record (status: pending)
  [4] Create analysis_jobs record (status: queued)
  [5] Return job_id immediately
         |
         v (BackgroundTask — async)
process_document_async()
  [1] Mark document + job as "processing"
  [2] Extract text
        PDF  -> pdfplumber (fallback: PyPDF2)
        DOCX -> python-docx
        TXT  -> UTF-8 decode
  [3] Claude API call #1: classify_document()
        -> Returns document_type + confidence
  [4] Store extracted text + classification in DB
  [5] For each of 17 NDIS standards:
        Claude API call #2: analyze_compliance_against_standard()
        -> Returns score, status, evidence, gaps, remediation
        -> Upsert compliance_scores record
        -> Insert gap_analysis record (if non-compliant)
  [6] Mark document as "completed"
  [7] Refresh dashboard materialized view
  [8] Mark job as "completed"
         |
         v
Client polls GET /api/compliance/jobs/{job_id}
until status == "completed"
```

---

## Deployment

### Railway

1. Create a new Railway project
2. Connect your GitHub repository
3. Add environment variables in the Railway dashboard
4. Railway auto-detects the Python app and deploys using `uvicorn`

Add a `Procfile` if needed:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Render

1. Create a new Web Service
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## CORS Configuration

The `CORS_ORIGINS` environment variable accepts a comma-separated list of allowed origins:

```
CORS_ORIGINS=https://veridahq.com,https://www.veridahq.com,http://localhost:3000
```

For development, `http://localhost:3000` and `http://localhost:8080` are included by default in `app/config.py`.

---

## Security Notes

- The `SUPABASE_SERVICE_KEY` bypasses Row Level Security. Never expose it to clients.
- All user-facing endpoints require a valid Supabase JWT (`Authorization: Bearer <token>`).
- File uploads are validated for extension and size before storage.
- RLS policies ensure users can only access data from their own organisation.
- Password reset emails use anti-enumeration protection (always return success).
