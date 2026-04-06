"""
Core business logic modules for JobLens.

This package contains the main functionality:
- scoring: Job scam detection using ML + rules
- matching: Resume-JD matching and scoring
- parsing: Resume PDF parsing
- analysis: Job description analysis
- scraping: URL scraping for job postings
- clients: External API clients (Groq LLM)
"""

from core.scoring import evaluate_job_posting, get_model, get_rules_summary, clear_model_cache
from core.matching import compute_match, FitScore, CredibilityScore, MatchResult
from core.parsing import parse_resume, ParseResult, clear_cache
from core.analysis import analyze_job_description, JDAnalysis
from core.scraping import extract_job_text_from_url, ScraperError
from core.clients import is_groq_available, ModelArtifact

__all__ = [
    # Scoring
    "evaluate_job_posting",
    "get_model",
    "get_rules_summary",
    "clear_model_cache",
    # Matching
    "compute_match",
    "FitScore",
    "CredibilityScore",
    "MatchResult",
    # Parsing
    "parse_resume",
    "ParseResult",
    "clear_cache",
    # Analysis
    "analyze_job_description",
    "JDAnalysis",
    # Scraping
    "extract_job_text_from_url",
    "ScraperError",
    # Clients
    "is_groq_available",
    "ModelArtifact",
]
