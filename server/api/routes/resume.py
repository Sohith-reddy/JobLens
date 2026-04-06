"""
Resume matching endpoints.
"""

import logging
from typing import Optional, Union

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.models.resume import ResumeMatchResponse, JDValidationResponse
from api.services.resume_match import process_resume_match
from api.config import MAX_PDF_SIZE, DEFAULT_MODEL_PATH

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["Resume Matching"])


@router.post(
    "/match",
    response_model=Union[ResumeMatchResponse, JDValidationResponse],
    summary="Match resume against job description",
)
async def resume_match(
    resume: UploadFile = File(..., description="PDF resume file"),
    job_description: str = Form(
        ...,
        description="Job description text",
        json_schema_extra={"example": "Enter job description here..."},
    ),
    use_llm: bool = Form(default=True, description="Whether to use LLM for enhanced analysis"),
    force_reparse: bool = Form(default=False, description="Force re-parsing even if cached"),
) -> Union[ResumeMatchResponse, JDValidationResponse]:
    """
    Match a resume against a job description (multipart form upload).

    First validates the job description to ensure it's a legitimate job posting
    (not a scam or irrelevant content). If validation fails, returns a
    JDValidationResponse with details.

    Accepts multipart/form-data with:
    - resume: PDF file upload
    - job_description: Job description text
    - use_llm: Whether to use LLM for enhanced analysis (default: true)
    - force_reparse: Force re-parsing even if cached (default: false)

    Returns comprehensive matching analysis including:
    - Resume parsing with structured schema
    - Fit score (0-100) with component breakdown
    - Credibility score (0-100) with signal breakdown
    - Improvement suggestions with bullet rewrites

    Example:
        curl -X POST http://localhost:8000/resume/match \\
          -F "resume=@resume.pdf" \\
          -F "job_description=Senior Software Engineer position..."
    """
    from core.scoring import evaluate_job_posting

    try:
        # First, validate the job description
        logger.info("Validating job description...")
        jd_validation = evaluate_job_posting(
            text=job_description,
            model_path=DEFAULT_MODEL_PATH,
        )

        # Check if it's not a job posting
        if not jd_validation.get("is_job_posting", True):
            logger.warning(f"JD validation failed: not a job posting - {jd_validation['final_reason']}")
            return JDValidationResponse(
                is_valid_job_posting=False,
                message=f"The provided text is not a valid job posting. {jd_validation['final_reason']}",
                final_label="NOT_JOB_POSTING",
            )

        # Check if it's a scam
        if jd_validation.get("final_label") == "SCAM":
            logger.warning(f"JD validation failed: scam detected - {jd_validation['final_reason']}")
            return JDValidationResponse(
                is_valid_job_posting=False,
                message=f"This job posting appears to be a scam. {jd_validation['final_reason']}",
                scam_score=jd_validation.get("ml_probability"),
                final_label="SCAM",
            )

        # Check if it's suspicious (optional - you can remove this block if you want to allow suspicious JDs)
        if jd_validation.get("final_label") == "SUSPICIOUS":
            logger.warning(f"JD validation: suspicious posting - {jd_validation['final_reason']}")
            return JDValidationResponse(
                is_valid_job_posting=False,
                message=f"This job posting has suspicious indicators. {jd_validation['final_reason']}",
                scam_score=jd_validation.get("ml_probability"),
                final_label="SUSPICIOUS",
            )

        logger.info(f"JD validation passed: {jd_validation['final_label']}")

        # Validate PDF file
        if not resume.filename or not resume.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400, detail="File must be a PDF (*.pdf)"
            )

        pdf_bytes = await resume.read()

        if len(pdf_bytes) > MAX_PDF_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"PDF too large: {len(pdf_bytes)} bytes (max {MAX_PDF_SIZE})",
            )

        if not pdf_bytes.startswith(b"%PDF"):
            raise HTTPException(
                status_code=400, detail="Invalid PDF file (missing PDF header)"
            )

        logger.info(
            f"Processing resume match: pdf_size={len(pdf_bytes)}, use_llm={use_llm}"
        )

        result = process_resume_match(
            job_description=job_description,
            pdf_bytes=pdf_bytes,
            use_llm=use_llm,
            force_reparse=force_reparse,
        )

        logger.info(
            f"Resume match complete: fit={result['fit_score']['overall']}, "
            f"credibility={result['credibility_score']['overall']}"
        )

        return ResumeMatchResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing resume match: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )


@router.delete(
    "/cache",
    summary="Clear resume parsing cache",
)
async def clear_resume_cache(candidate_id: Optional[str] = None):
    """
    Clear the resume parsing cache.

    Args:
        candidate_id: If provided, only clear cache for this candidate.
                     If not provided, clears all cache entries.

    Returns:
        Number of cache entries deleted.
    """
    from core.parsing import clear_cache

    deleted = clear_cache(candidate_id)

    if candidate_id:
        logger.info(f"Cleared {deleted} cache entries for candidate: {candidate_id}")
    else:
        logger.info(f"Cleared all {deleted} cache entries")

    return {"deleted": deleted, "candidate_id": candidate_id}
