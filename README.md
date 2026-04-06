# JobLens AI

JobLens AI is a full-stack application for:
- Detecting potentially fraudulent job postings using ML + rule-based scoring
- Matching resumes against job descriptions with actionable feedback
- Providing a modern React dashboard for analysis workflows

---

## Table of Contents
- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Frontend (UI)](#frontend-ui)
- [Backend (API)](#backend-api)
- [Setup](#setup)
- [API Endpoints](#api-endpoints)
- [Environment Variables](#environment-variables)
- [Run in Development](#run-in-development)
- [API Docs](#api-docs)

---

## Overview

JobLens combines a React frontend and a FastAPI backend:

- **UI Layer**: Collects job text/URL + resume upload, then displays scam verdicts, warnings, and resume-fit insights.
- **Scam Detection Engine**: Uses SentenceTransformer embeddings + Logistic Regression with a configurable rule engine and gate logic.
- **Resume Matching Engine**: Parses PDF resumes, computes fit/credibility scores, and returns improvement suggestions.

---

## Tech Stack

### Frontend
- React 18
- Vite
- Tailwind CSS
- React Router
- Radix UI primitives + custom UI components

### Backend
- Python 3.9+
- FastAPI + Uvicorn
- sentence-transformers
- scikit-learn
- PyMuPDF / pdfminer.six
- BeautifulSoup + readability-lxml
- Playwright (optional fallback for JS-heavy pages)

---

## Project Structure

```text
JobLens/
├── client/                    # React + Vite frontend
│   ├── src/
│   │   ├── pages/             # Home, Dashboard, Docs, Auth, etc.
│   │   ├── components/        # UI/layout/dashboard components
│   │   └── lib/joblensApi.js  # Frontend API client
│   └── README.md
├── server/                    # FastAPI backend
│   ├── api/                   # App factory, routes, models, services, config
│   ├── core/                  # Scoring, scraping, parsing, matching, clients
│   ├── data/                  # Models/cache/datasets
│   ├── scripts/               # Training and helper scripts
│   ├── app.py                 # Backend entrypoint
│   └── README.md
└── README.md                  # This file
```

---

## Frontend (UI)

The frontend provides the end-user workflow:

- Submit job postings as **text** or **URL**
- Upload resume (UI accepts PDF/DOC/DOCX; backend processes PDF)
- View analysis report in dashboard cards:
  - Fraud Verdict + risk score + rule flags
  - Company extraction confidence metadata
  - Resume compatibility score + missing skills
  - API warnings and decision rationale
- Browse in-app Docs page with live backend health/rules metadata

### Frontend Routes

- `/` and `/about` – About page
- `/analyze` – Input page for job + resume analysis
- `/dashboard` – Result view
- `/docs` – Product/API info pulled from backend metadata
- `/plans`, `/profile`, `/login`, `/signup`

### Frontend API Integration

By default, the client calls:

`http://localhost:8000`

Overridable via:

```bash
VITE_JOBLENS_API_BASE_URL=http://your-api-host:8000
```

---

## Backend (API)

Backend documentation is based on and consolidated from `server/README.md`.

### Core Features

- **ML Model**: SentenceTransformer embeddings (`all-mpnet-base-v2`) + Logistic Regression
- **Rule Engine**: 20+ configurable detection rules
- **Gate Logic**: Critical rules can override ML output; ensemble-based final label
- **URL Scraping**: Multi-strategy extraction from job URLs
- **Resume Matching**: PDF parsing, fit/credibility scoring, and suggestions
- **Optional LLM Integration**: Groq API for enhanced parsing/rewrite quality
- **REST API**: Endpoints for scoring, resume matching, health, and rules

### URL Scraping Strategy

1. HTTP + readability-lxml fast path  
2. BeautifulSoup heuristic fallback  
3. Playwright rendering for JS-heavy pages (optional but supported)

### Security Controls

- URL scheme validation (`http`/`https`)
- SSRF protection for private/internal ranges
- Response size limits
- Request timeout controls

### Ensemble Decision Logic

1. Critical rule hit → `SCAM`
2. High ML probability → `SCAM`
3. Mid ML probability + rule score threshold → `SUSPICIOUS`
4. Otherwise → `LEGIT`

---

## Setup

### 1) Backend setup

```bash
cd /home/runner/work/JobLens/JobLens/server

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Optional (for JS-heavy URL extraction fallback)
playwright install chromium
```

### 2) Frontend setup

```bash
cd /home/runner/work/JobLens/JobLens/client
npm install
```

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/scoring/text` | POST | Score job posting text (plain text body) |
| `/scoring/url` | POST | Scrape URL and score extracted posting |
| `/resume/match` | POST | Upload PDF resume + JD and get match analysis |
| `/resume/cache` | DELETE | Clear resume parse cache (optional `candidate_id`) |
| `/health` | GET | Health check |
| `/rules` | GET | List configured scam-detection rules |

---

## Environment Variables

### Frontend

```bash
VITE_JOBLENS_API_BASE_URL=http://localhost:8000
```

### Backend

```bash
# Optional LLM support
GROQ_API_KEY=your-groq-api-key

# Optional overrides
MODEL_PATH=/absolute/path/to/job_scam_model.joblib
HOST=0.0.0.0
PORT=8000
```

---

## Run in Development

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

Then open the Vite URL shown in terminal (typically `http://localhost:5173`).

---

## API Docs

Once backend is running:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
