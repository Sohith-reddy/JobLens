# JobLens AI

JobLens AI is a full-stack platform that helps job seekers and teams:
- detect potentially fraudulent job postings using ML + rule-based scoring
- evaluate resume-to-job fit with structured feedback
- review results in a modern React dashboard

---

## Table of Contents
- [Overview](#overview)
- [Core Capabilities](#core-capabilities)
- [Architecture and Project Structure](#architecture-and-project-structure)
- [Authentication (Supabase)](#authentication-supabase)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Development Runbook](#development-runbook)
- [Documentation and Support](#documentation-and-support)

---

## Overview

JobLens combines a React frontend (`client/`) and a FastAPI backend (`server/`) to deliver an end-to-end analysis workflow:
1. validate and score job postings (text or URL)
2. upload a resume for compatibility and credibility analysis
3. view actionable insights and warnings in a dashboard

---

## Core Capabilities

- **Scam Detection Engine**: Ensemble of SentenceTransformer + Logistic Regression + weighted rule engine
- **Resume Matching**: PDF resume parsing, fit scoring, credibility scoring, and improvement suggestions
- **URL Intelligence**: Multi-stage extraction pipeline for job descriptions from live URLs
- **Operational Endpoints**: Health and rule metadata endpoints for product observability

---

## Architecture and Project Structure

```text
JobLens/
├── client/                        # React + Vite frontend
│   ├── src/
│   │   ├── components/            # Shared UI and layout components
│   │   ├── pages/                 # Home, Dashboard, Docs, Profile, Auth pages
│   │   └── lib/                   # API/auth clients and shared utilities
│   └── README.md
├── server/                        # FastAPI backend
│   ├── api/                       # Application factory, routes, schema models
│   ├── core/                      # Scoring, parsing, scraping, matching logic
│   ├── data/                      # Trained model and datasets
│   ├── scripts/                   # Training/inference helper scripts
│   └── README.md
└── README.md
```

---

## Authentication (Supabase)

Login and signup in the frontend are integrated with **Supabase Auth** (`@supabase/supabase-js`):
- `client/src/lib/supabaseClient.js` initializes the Supabase client
- `client/src/pages/auth/Login.jsx` authenticates users with `signInWithPassword`
- `client/src/pages/auth/Signup.jsx` handles account creation

If Supabase variables are missing, the UI shows a clear configuration error instead of silently failing.

Required frontend environment variables:

```bash
VITE_SUPABASE_URL=your-supabase-project-url
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

---

## Technology Stack

### Frontend
- React 18
- Vite
- Tailwind CSS
- React Router
- Radix UI primitives
- Supabase JavaScript SDK

### Backend
- Python 3.9+
- FastAPI + Uvicorn
- sentence-transformers
- scikit-learn
- PyMuPDF / pdfminer.six
- BeautifulSoup + readability-lxml

---

## Getting Started

### 1) Backend setup

```bash
cd /home/runner/work/JobLens/JobLens/server
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Frontend setup

```bash
cd /home/runner/work/JobLens/JobLens/client
npm install
```

> After setup, configure `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` before using login/signup. See [Configuration](#configuration).

---

## Configuration

### Frontend

```bash
VITE_JOBLENS_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=your-supabase-project-url
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

### Backend Environment Variables (optional)

```bash
GROQ_API_KEY=your-groq-api-key
MODEL_PATH=/absolute/path/to/job_scam_model.joblib
HOST=0.0.0.0
PORT=8000
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/scoring/text` | POST | Score a job posting from plain text body |
| `/scoring/url` | POST | Scrape and score a job posting URL |
| `/resume/match` | POST | Upload resume PDF + job description for matching |
| `/resume/cache` | DELETE | Clear cached resume parsing results |
| `/health` | GET | Service health check |
| `/rules` | GET | Detection rules and metadata |
| `/summarize` | POST | Fake Job Posting Summarization |

---

## Development Runbook

Start backend:

```bash
cd /home/runner/work/JobLens/JobLens/server
source .venv/bin/activate
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Start frontend (new terminal):

```bash
cd /home/runner/work/JobLens/JobLens/client
npm run dev
```

---

## Documentation and Support

- API docs (when backend is running):
  - Swagger UI: `http://localhost:8000/docs`
  - ReDoc: `http://localhost:8000/redoc`
- For issues, feature requests, or contribution discussions, please open an issue in this repository.
