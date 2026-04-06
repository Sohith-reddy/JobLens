"""
URL scraping module for job postings.
"""

from core.scraping.scraper import (
    extract_job_text_from_url,
    extract_job_text_from_url_sync,
    ScraperError,
    URLValidationError,
    SSRFError,
    FetchError,
    ExtractionError,
    validate_url,
    check_ssrf,
    compute_confidence,
)

__all__ = [
    "extract_job_text_from_url",
    "extract_job_text_from_url_sync",
    "ScraperError",
    "URLValidationError",
    "SSRFError",
    "FetchError",
    "ExtractionError",
    "validate_url",
    "check_ssrf",
    "compute_confidence",
]
