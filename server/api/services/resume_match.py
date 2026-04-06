"""
Resume matching service.

Core business logic for matching resumes against job descriptions.
"""

import hashlib


def process_resume_match(
    job_description: str,
    pdf_bytes: bytes,
    use_llm: bool,
    force_reparse: bool = False,
) -> dict:
    """
    Core resume matching logic.

    Args:
        job_description: JD text
        pdf_bytes: Raw PDF bytes
        use_llm: Whether to use LLM
        force_reparse: Whether to force re-parsing even if cached

    Returns:
        Complete response dict with fit score, credibility score, and suggestions.
    """
    from core.parsing import parse_resume, invalidate_cache_for_pdf
    from core.matching import compute_match

    timings = {}

    # Use PDF hash as cache key
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]

    if force_reparse:
        invalidate_cache_for_pdf(pdf_bytes, pdf_hash)

    parse_result = parse_resume(
        pdf_bytes=pdf_bytes,
        candidate_id=pdf_hash,
        use_llm=use_llm,
        use_cache=not force_reparse,
    )
    timings["pdf_extract"] = parse_result.timings_ms.get("pdf_extract", 0)
    timings["parse"] = parse_result.timings_ms.get("parse", 0) + parse_result.timings_ms.get(
        "field_extraction", 0
    )

    match_result = compute_match(
        resume_schema=parse_result.schema,
        resume_text=parse_result.raw_text,
        jd_text=job_description,
        use_llm=use_llm,
    )
    timings["embed"] = match_result.timings_ms.get("fit_scoring", 0)
    timings["scoring"] = match_result.timings_ms.get(
        "credibility_scoring", 0
    ) + match_result.timings_ms.get("jd_analysis", 0)
    timings["llm"] = match_result.timings_ms.get("suggestions", 0) if use_llm else 0

    response = {
        "resume_parse": {
            "schema": parse_result.schema,
            "raw_text": parse_result.raw_text[:10000],
            "parse_warnings": parse_result.parse_warnings,
            "parse_confidence": parse_result.parse_confidence,
        },
        "fit_score": match_result.fit_score.to_dict(),
        "credibility_score": match_result.credibility_score.to_dict(),
        "suggestions": match_result.suggestions.to_dict(),
        "timings_ms": timings,
    }

    return response
