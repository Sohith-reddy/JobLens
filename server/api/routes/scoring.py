"""
Scoring endpoints for job scam detection.
"""

import logging
from typing import Union

from fastapi import APIRouter, Body, HTTPException

from api.models.scoring import (
    ScoreResponse,
    ScoreURLRequest,
    ScoreURLResponse,
    NotJobPostingResponse,
    NotJobPostingURLResponse,
)
from api.config import DEFAULT_MODEL_PATH

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scoring", tags=["Scoring"])


@router.post(
    "/url",
    response_model=Union[ScoreURLResponse, NotJobPostingURLResponse],
    summary="Score job posting from URL",
)
async def score_job_posting_url(
    request: ScoreURLRequest,
) -> Union[ScoreURLResponse, NotJobPostingURLResponse]:
    """
    Scrape a job posting URL and score it for scam indicators.

    If the content is not a job posting, returns a simple message.

    Extraction strategy (in order):
    1. Fast path: HTTP GET + readability-lxml extraction
    2. Fallback: BeautifulSoup heuristics for job containers
    3. Advanced: Playwright rendering for JS-heavy sites (if enabled)

    Security features:
    - URL scheme validation (http/https only)
    - SSRF protection (blocks private IPs)
    - Response size limits (2MB max)
    - Strict timeouts (10s for HTTP, 15s for Playwright)
    """
    from core.scoring import evaluate_job_posting
    from core.scraping.scraper import (
        extract_job_text_from_url,
        URLValidationError,
        SSRFError,
        FetchError,
        ExtractionError,
    )

    try:
        logger.info(f"Scraping URL: {request.url}")
        extraction_result = await extract_job_text_from_url(
            url=request.url,
            use_playwright=True,
        )

        extracted_text = extraction_result["text"]
        extraction_method = extraction_result["method"]
        extraction_confidence = extraction_result["confidence"]
        warnings = extraction_result["warnings"]

        logger.info(
            f"Extraction complete: method={extraction_method}, "
            f"confidence={extraction_confidence:.2f}, "
            f"text_length={len(extracted_text)}"
        )

        score_result = evaluate_job_posting(
            text=extracted_text,
            model_path=DEFAULT_MODEL_PATH,
        )

        if not score_result.get("is_job_posting", True):
            logger.info(f"URL not a job posting: {score_result['final_reason']}")
            return NotJobPostingURLResponse(
                url=request.url,
                is_job_posting=False,
                message=f"This URL does not contain a job posting. {score_result['final_reason']}",
            )

        logger.info(
            f"Scored URL posting: label={score_result['final_label']}, "
            f"ml_prob={score_result['ml_probability']:.4f}, "
            f"rule_score={score_result['rule_score']:.2f}"
        )

        return ScoreURLResponse(
            url=request.url,
            final_extracted_text=extracted_text,
            extraction_method=extraction_method,
            extraction_confidence=extraction_confidence,
            score_result=ScoreResponse(**score_result),
            warnings=warnings,
        )

    except URLValidationError as e:
        logger.warning(f"URL validation failed: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid URL: {str(e)}")
    except SSRFError as e:
        logger.warning(f"SSRF protection triggered: {e}")
        raise HTTPException(status_code=403, detail=f"Access denied: {str(e)}")
    except FetchError as e:
        logger.warning(f"Failed to fetch URL: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch URL: {str(e)}")
    except ExtractionError as e:
        logger.warning(f"Failed to extract text: {e}")
        raise HTTPException(
            status_code=422, detail=f"Failed to extract job description: {str(e)}"
        )
    except FileNotFoundError as e:
        logger.error(f"Model file not found: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Model file not found: {DEFAULT_MODEL_PATH}",
        )
    except Exception as e:
        logger.error(f"Error processing URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )


@router.post(
    "/text",
    response_model=Union[ScoreResponse, NotJobPostingResponse],
    summary="Score job posting from plain text",
)
async def score_plain_text(
    text: str = Body(
        ...,
        media_type="text/plain",
        description="Plain text job description",
        openapi_examples={
            "software_engineer": {
                "summary": "Software Engineer Job",
                "description": "A typical software engineering job posting",
                "value": "Software Engineer at TechCorp\n\nWe are looking for a skilled Software Engineer to join our team. Requirements: 3+ years of Python experience, knowledge of REST APIs, and familiarity with cloud services (AWS/GCP). Competitive salary and benefits package."
            },
            "suspicious_job": {
                "summary": "Suspicious Job Posting",
                "description": "A job posting with potential red flags",
                "value": "URGENT HIRING! Work from home and earn $5000/week! No experience needed. Send your personal details and bank information to get started immediately. This is a limited time opportunity!"
            }
        }
    ),
) -> Union[ScoreResponse, NotJobPostingResponse]:
    """
    Score a job posting using plain text body (no JSON required).

    If the text is not a job posting, returns a simple message.

    Simply send the job description as the raw request body.
    Useful for multiline text that's difficult to JSON-escape.

    Example:
        curl -X POST http://localhost:8000/scoring/text \\
          -H "Content-Type: text/plain" \\
          -d "Your job description here..."
    """
    from core.scoring import evaluate_job_posting

    try:
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text body cannot be empty")

        result = evaluate_job_posting(
            text=text,
            model_path=DEFAULT_MODEL_PATH,
        )

        if not result.get("is_job_posting", True):
            logger.info(f"Not a job posting: {result['final_reason']}")
            return NotJobPostingResponse(
                is_job_posting=False,
                message=f"This text is not a job posting. {result['final_reason']}",
            )

        logger.info(
            f"Scored plain text posting: label={result['final_label']}, "
            f"ml_prob={result['ml_probability']:.4f}, "
            f"rule_score={result['rule_score']:.2f}"
        )

        return ScoreResponse(**result)

    except FileNotFoundError as e:
        logger.error(f"Model file not found: {e}")
        raise HTTPException(
            status_code=500, detail=f"Model file not found: {DEFAULT_MODEL_PATH}"
        )
    except Exception as e:
        logger.error(f"Error scoring job posting: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )
