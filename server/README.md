# JobLens AI - Job Scam Detection & Resume Matching

Gate-based ensemble for detecting fraudulent job postings using ML + rule-based analysis, plus resume-JD compatibility scoring.

## Features

- **ML Model**: SentenceTransformer embeddings (`all-mpnet-base-v2`) + Logistic Regression
- **Rule Engine**: 20+ configurable rules for detecting scam patterns
- **Gate Logic**: Critical rules override ML; ensemble decision for edge cases
- **URL Scraping**: Extract job descriptions from URLs with multi-strategy extraction
- **Resume Matching**: Parse PDFs, compute fit scores, credibility analysis, and suggestions
- **LLM Integration**: Optional Groq API for enhanced section labeling and rewrite suggestions
- **REST API**: FastAPI endpoints for scoring text, URLs, and resume matching

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install Playwright for JS-heavy sites
pip install playwright
playwright install chromium
```

## Quick Start

### Start the API Server

```bash
# Development
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/score` | POST | Score job posting text |
| `/score_url` | POST | Scrape URL and score |
| `/resume_match` | POST | Match resume (base64 PDF) against JD |
| `/resume_match_multipart` | POST | Match resume (file upload) against JD |
| `/health` | GET | Health check |
| `/rules` | GET | List detection rules |

### Test with curl

#### Score Text

```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "text": "URGENT HIRING! Work from home, earn $5000/week. No experience needed. Pay $50 registration fee to start."
  }'
```

#### Score URL

```bash
curl -X POST http://localhost:8000/score_url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.linkedin.com/jobs/view/1234567890"
  }'
```

#### Health Check

```bash
curl http://localhost:8000/health
```

#### List Rules

```bash
curl http://localhost:8000/rules
```

#### Resume Match (Multipart File Upload)

```bash
curl -X POST http://localhost:8000/resume_match_multipart \
  -F "job_description=Senior Software Engineer position requiring 5+ years of Python experience. Must have experience with AWS, Docker, and PostgreSQL. Responsibilities include designing scalable backend services and mentoring junior engineers." \
  -F "resume=@/path/to/resume.pdf" \
  -F "candidate_id=candidate-123" \
  -F "job_id=job-456" \
  -F "use_llm=true"
```

#### Resume Match (JSON with Base64 PDF)

```bash
# First, encode your PDF to base64
PDF_BASE64=$(base64 -i /path/to/resume.pdf)

# Then send the request
curl -X POST http://localhost:8000/resume_match \
  -H "Content-Type: application/json" \
  -d "{
    \"job_description\": \"Senior Software Engineer position requiring 5+ years of Python experience...\",
    \"resume_pdf_base64\": \"$PDF_BASE64\",
    \"candidate_id\": \"candidate-123\",
    \"job_id\": \"job-456\",
    \"use_llm\": true
  }"
```

## CLI Usage

```bash
# Score a file
python score_cli.py --file job_description.txt

# Score text directly
python score_cli.py --text "Job posting text here..."

# List all rules
python score_cli.py --list-rules

# Test URL scraper
python scraper.py "https://example.com/job-posting"
```

## URL Scraping

The `/score_url` endpoint uses a multi-strategy extraction approach:

### Extraction Strategies (in order)

1. **Fast Path**: HTTP GET + `readability-lxml`
   - Fastest, works for most static sites
   - Extracts main content automatically

2. **BeautifulSoup Fallback**: Heuristic-based extraction
   - Looks for job-specific containers (`<main>`, `<article>`, `.job-description`, etc.)
   - Scores candidates by text length and keyword density

3. **Playwright Rendering**: For JS-heavy sites
   - Full browser rendering with Chromium
   - Only used when other methods fail
   - Requires `playwright install chromium`

### Security Features

- **URL Validation**: Only `http://` and `https://` schemes allowed
- **SSRF Protection**: Blocks private IP ranges (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, etc.)
- **Size Limits**: Max 2MB response size
- **Timeouts**: 10s for HTTP, 15s for Playwright

### Response Fields

```json
{
  "url": "https://example.com/job",
  "final_extracted_text": "Job description text...",
  "extraction_method": "readability-lxml",
  "extraction_confidence": 0.85,
  "score_result": {
    "ml_probability": 0.23,
    "ml_pred": 0,
    "rule_hits": [],
    "rule_score": 0.0,
    "final_label": "LEGIT",
    "final_reason": "...",
    "decision_path": ["..."]
  },
  "warnings": []
}
```

### Extraction Confidence

Confidence score (0.0-1.0) based on:
- Text length (ideal >= 1500 chars)
- Job keyword presence (responsibilities, requirements, qualifications, etc.)
- Alphabetic character ratio

## Gate Logic

The ensemble uses a gate-based decision system:

1. **Critical Rule Hit** → `SCAM` (hard override)
2. **ML Probability >= T_HIGH** → `SCAM`
3. **T_LOW <= ML < T_HIGH AND rule_score >= 1.0** → `SUSPICIOUS`
4. **Otherwise** → `LEGIT`

Default thresholds:
- `T_HIGH = max(model_threshold, 0.60)`
- `T_LOW = min(model_threshold, 0.45)`

## Rule Severities

| Severity | Weight | Examples |
|----------|--------|----------|
| CRITICAL | 2.0 | Upfront fees, SSN requests, crypto payments |
| HIGH | 1.0 | No interview, unrealistic pay, generic email |
| MEDIUM | 0.5 | Vague company, rushed hiring, urgency |
| LOW | 0.25 | Poor grammar, formatting issues |

## Resume Matching

The `/resume_match` and `/resume_match_multipart` endpoints provide comprehensive resume-JD compatibility analysis.

### Features

- **PDF Parsing**: PyMuPDF (fitz) with pdfminer.six fallback
- **Structured Schema**: Extracts basics, skills, experience, projects, education, certifications
- **Fit Score (0-100)**: Skill match, experience match, ATS keyword match, role alignment
- **Credibility Score (0-100)**: Specificity, consistency, verifiability, clarity
- **Suggestions**: Missing requirements, bullet rewrites, ATS improvements, project recommendations
- **LLM Integration**: Optional Groq API for enhanced analysis

### Environment Variables

```bash
# Optional: Enable LLM features (Groq API)
export GROQ_API_KEY="your-groq-api-key"

# Optional: Custom cache database path
export JOBLENS_CACHE_DB="/path/to/cache.db"
```

### Response Schema

```json
{
  "job_id": "job-456",
  "candidate_id": "candidate-123",
  "resume_parse": {
    "schema": {
      "basics": {"name": "", "email": "", "phone": "", "location": "", "links": []},
      "summary": "",
      "skills": {"technical": [], "tools": [], "soft": []},
      "experience": [{"company": "", "title": "", "start": "", "end": "", "bullets": [], "tech": [], "impact_metrics": []}],
      "projects": [{"name": "", "bullets": [], "tech": [], "links": []}],
      "education": [{"school": "", "degree": "", "start": "", "end": ""}],
      "certifications": []
    },
    "raw_text": "...",
    "parse_warnings": [],
    "parse_confidence": 0.85
  },
  "fit_score": {
    "overall": 72,
    "components": {
      "skill_match": 28,
      "experience_match": 22,
      "ats_keyword_match": 14,
      "role_alignment": 8
    },
    "must_have_gaps": ["Kubernetes", "GraphQL"],
    "evidence_map": {"Python": ["Found in resume skills: Python"]}
  },
  "credibility_score": {
    "overall": 68,
    "signals": {
      "specificity": 18,
      "consistency": 20,
      "verifiability": 15,
      "clarity": 15
    },
    "boosters": ["LinkedIn profile provided", "Strong quantification: 5 metrics found"],
    "flags": ["Few specific technologies mentioned"]
  },
  "suggestions": {
    "missing_requirements": ["Experience with Kubernetes"],
    "bullet_rewrites": [
      {
        "original": "Worked on backend services",
        "rewrite_options": ["Designed and implemented scalable backend services handling 10K+ requests/second"],
        "why": "Issues: uses vague 'worked on', no quantification",
        "guardrail_note": "Consider adding only if true."
      }
    ],
    "ats_improvements": ["Consider incorporating these keywords if applicable: kubernetes, graphql"],
    "project_recommendations": ["Consider building a project demonstrating: Kubernetes, GraphQL"]
  },
  "timings_ms": {
    "pdf_extract": 45,
    "parse": 120,
    "embed": 350,
    "scoring": 80,
    "llm": 1200
  }
}
```

### LLM Usage (Optional)

The system uses Groq API with `llama-3.1-8b-instant` for:

1. **Section Labeling**: Helps identify resume sections when heuristics are uncertain
2. **Schema Completion**: Fills missing fields from resume text
3. **Bullet Rewrites**: Suggests improved bullet points with guardrails

LLM is **optional** - the system works without `GROQ_API_KEY` using heuristics only.

## Project Structure

```
JobLens/
├── app.py              # FastAPI application
├── gate_scorer.py      # Ensemble scoring logic
├── scraper.py          # URL scraping module
├── resume_parser.py    # PDF parsing and schema extraction
├── jd_analyzer.py      # Job description analysis
├── match_scorer.py     # Resume-JD matching and scoring
├── groq_client.py      # Groq LLM API client
├── score_cli.py        # Command-line interface
├── model_artifact.py   # Model dataclass
├── train_job_scam_model_mpnet.py  # Model training
├── job_scam_model.joblib          # Trained model
├── joblens_cache.db    # SQLite cache (auto-created)
├── requirements.txt    # Dependencies
└── README.md           # This file
```

## Development

### Training a New Model

```bash
python train_job_scam_model_mpnet.py
```

### Running Tests

```bash
# Test scraper
python scraper.py "https://example.com/job"

# Test scorer
python score_cli.py --file sample_jd.txt
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

MIT
