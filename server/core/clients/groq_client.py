"""
Groq API client for JobLens AI.

Provides LLM capabilities for:
- Resume section labeling/segmentation
- Schema completion assistance
- Bullet rewrite suggestions

Uses Groq's fast inference with llama-3.1-8b-instant model.
Falls back gracefully when API key is missing or calls fail.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 4096
REQUEST_TIMEOUT = 30.0


def get_api_key() -> Optional[str]:
    """Get Groq API key from environment. Never log or return in responses."""
    return os.environ.get("GROQ_API_KEY")


def is_groq_available() -> bool:
    """Check if Groq API is available (key is set)."""
    key = get_api_key()
    return bool(key and len(key) > 10)


def groq_chat(
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = REQUEST_TIMEOUT,
) -> Optional[str]:
    """
    Call Groq chat completion API.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model to use (default: llama-3.1-8b-instant)
        temperature: Sampling temperature (default: 0.2 for deterministic)
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds
        
    Returns:
        Response content string, or None if call fails
    """
    api_key = get_api_key()
    if not api_key:
        logger.debug("Groq API key not set, skipping LLM call")
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(GROQ_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if content:
                logger.debug(f"Groq response received: {len(content)} chars")
                return content
            
            logger.warning("Groq returned empty content")
            return None
            
    except httpx.HTTPStatusError as e:
        logger.warning(f"Groq API HTTP error: {e.response.status_code}")
        return None
    except httpx.TimeoutException:
        logger.warning(f"Groq API timeout after {timeout}s")
        return None
    except Exception as e:
        logger.warning(f"Groq API error: {type(e).__name__}: {e}")
        return None


def extract_json_from_response(text: str) -> Optional[dict]:
    """
    Extract JSON from LLM response, handling markdown code blocks.
    
    Args:
        text: Raw LLM response text
        
    Returns:
        Parsed JSON dict, or None if parsing fails
    """
    if not text:
        return None
    
    text = text.strip()
    
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Try extracting from markdown code block
    patterns = [
        r"```json\s*([\s\S]*?)\s*```",
        r"```\s*([\s\S]*?)\s*```",
        r"\{[\s\S]*\}",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                json_str = match.group(1) if "```" in pattern else match.group(0)
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                continue
    
    return None


def safe_json_call(
    messages: list[dict],
    expected_keys: Optional[list[str]] = None,
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Optional[dict]:
    """
    Call Groq and parse JSON response with validation.
    
    Args:
        messages: Chat messages
        expected_keys: Optional list of keys that must be present in response
        model: Model to use
        temperature: Sampling temperature
        max_tokens: Max tokens
        
    Returns:
        Parsed and validated JSON dict, or None if call/parse/validation fails
    """
    response = groq_chat(messages, model, temperature, max_tokens)
    if not response:
        return None
    
    parsed = extract_json_from_response(response)
    if not parsed:
        logger.warning("Failed to parse JSON from Groq response")
        return None
    
    if expected_keys:
        missing = [k for k in expected_keys if k not in parsed]
        if missing:
            logger.warning(f"Groq response missing expected keys: {missing}")
            return None
    
    return parsed


# =============================================================================
# SECTION LABELING PROMPT
# =============================================================================

SECTION_LABELING_SYSTEM = """You are a resume parser assistant. Your task is to label sections of a resume.

CRITICAL RULES:
1. Output ONLY valid JSON - no markdown, no explanations, no extra text
2. Never invent or fabricate information
3. If uncertain about a section, label it as "other"
4. Return empty arrays/objects when data is missing

You will receive resume text with line numbers and candidate section headers.
Return a JSON object mapping section names to line ranges."""

SECTION_LABELING_SCHEMA = """{
  "sections": {
    "summary": {"start": <int>, "end": <int>},
    "skills": {"start": <int>, "end": <int>},
    "experience": {"start": <int>, "end": <int>},
    "projects": {"start": <int>, "end": <int>},
    "education": {"start": <int>, "end": <int>},
    "certifications": {"start": <int>, "end": <int>}
  }
}

Each section should have start and end line numbers. Omit sections not found.
Line numbers are 1-indexed."""


def llm_label_sections(
    resume_text: str,
    candidate_headers: list[dict],
    max_chars: int = 15000,
) -> Optional[dict]:
    """
    Use LLM to label resume sections.
    
    Args:
        resume_text: Raw resume text
        candidate_headers: List of dicts with 'text' and 'line' keys
        max_chars: Max chars to send (truncate if longer)
        
    Returns:
        Dict mapping section names to line ranges, or None if LLM fails
    """
    if not is_groq_available():
        return None
    
    # Truncate if needed
    if len(resume_text) > max_chars:
        resume_text = resume_text[:max_chars] + "\n... [truncated]"
    
    # Add line numbers
    lines = resume_text.split("\n")
    numbered_text = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines[:500]))
    
    headers_str = "\n".join(
        f"- Line {h.get('line', '?')}: \"{h.get('text', '')}\"" 
        for h in candidate_headers[:20]
    )
    
    user_prompt = f"""Resume text with line numbers:
```
{numbered_text}
```

Candidate section headers detected:
{headers_str}

Return JSON mapping sections to line ranges. Use this schema:
{SECTION_LABELING_SCHEMA}"""

    messages = [
        {"role": "system", "content": SECTION_LABELING_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    
    result = safe_json_call(messages, expected_keys=["sections"])
    return result.get("sections") if result else None


# =============================================================================
# SCHEMA COMPLETION PROMPT
# =============================================================================

SCHEMA_COMPLETION_SYSTEM = """You are a resume parser assistant. Your task is to fill in missing fields in a partially parsed resume schema.

CRITICAL RULES:
1. Output ONLY valid JSON - no markdown, no explanations
2. NEVER invent facts - if information is not in the source text, return empty string or empty array
3. Do not fabricate employers, job titles, dates, metrics, or skills
4. Only extract information that is explicitly stated in the resume text
5. Return empty values when uncertain

You will receive:
1. The current partially parsed schema
2. The original resume text

Fill in any missing fields you can find in the text."""


def llm_complete_schema(
    partial_schema: dict,
    resume_text: str,
    max_chars: int = 12000,
) -> Optional[dict]:
    """
    Use LLM to fill missing fields in resume schema.
    
    Args:
        partial_schema: Partially parsed resume schema
        resume_text: Original resume text
        max_chars: Max chars to send
        
    Returns:
        Completed schema dict, or None if LLM fails
    """
    if not is_groq_available():
        return None
    
    if len(resume_text) > max_chars:
        resume_text = resume_text[:max_chars] + "\n... [truncated]"
    
    schema_str = json.dumps(partial_schema, indent=2)
    
    user_prompt = f"""Current parsed schema (some fields may be empty):
```json
{schema_str}
```

Original resume text:
```
{resume_text}
```

Fill in any missing fields you can find. Return the complete schema as JSON.
IMPORTANT: Do not invent any information. Only use what's in the text."""

    messages = [
        {"role": "system", "content": SCHEMA_COMPLETION_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    
    return safe_json_call(messages, expected_keys=["basics"])


# =============================================================================
# BULLET REWRITE SUGGESTIONS PROMPT
# =============================================================================

BULLET_REWRITE_SYSTEM = """You are a resume improvement assistant. Your task is to suggest bullet point rewrites that better match a job description.

CRITICAL RULES:
1. Output ONLY valid JSON - no markdown, no explanations
2. NEVER fabricate achievements, metrics, employers, or skills
3. All suggestions must be phrased as "Consider adding if true" or similar
4. Rewrites should enhance clarity and ATS compatibility while preserving truthfulness
5. Focus on action verbs, quantifiable impacts, and relevant keywords

IMPORTANT FOR missing_requirements:
- Return ONLY specific skill/technology names that are missing (e.g., "Kubernetes", "PostgreSQL", "Shell scripting")
- Do NOT return full sentences like "Experience with Docker and Kubernetes"
- Do NOT include skills the candidate already has
- Each item should be a single technology/skill name, max 3-4 words

IMPORTANT FOR ats_improvements:
- Do NOT suggest adding skills the candidate already has
- Focus on formatting, structure, and keyword optimization tips
- Be specific and actionable

Return suggestions in this exact JSON format:
{
  "bullet_rewrites": [
    {
      "original": "original bullet text",
      "rewrite_options": ["option 1", "option 2"],
      "why": "explanation of improvement",
      "guardrail_note": "Consider adding only if this accurately reflects your experience."
    }
  ],
  "missing_requirements": ["Kubernetes", "PostgreSQL"],
  "ats_improvements": ["Use action verbs at the start of bullets", "Add metrics where possible"],
  "project_recommendations": ["Build a project using X and Y"]
}"""


def llm_suggest_improvements(
    resume_bullets: list[str],
    jd_requirements: list[str],
    jd_keywords: list[str],
    max_bullets: int = 15,
) -> Optional[dict]:
    """
    Use LLM to suggest bullet rewrites and improvements.
    
    Args:
        resume_bullets: List of resume bullet points
        jd_requirements: List of JD requirements
        jd_keywords: List of important JD keywords
        max_bullets: Max bullets to process
        
    Returns:
        Dict with suggestions, or None if LLM fails
    """
    if not is_groq_available():
        return None
    
    bullets_str = "\n".join(f"- {b}" for b in resume_bullets[:max_bullets])
    reqs_str = "\n".join(f"- {r}" for r in jd_requirements[:15])
    keywords_str = ", ".join(jd_keywords[:30])
    
    user_prompt = f"""Job Description Requirements:
{reqs_str}

Important Keywords: {keywords_str}

Resume Bullets to Improve:
{bullets_str}

Suggest improvements. Remember:
- Never fabricate metrics or achievements
- All suggestions must include guardrail notes
- Focus on ATS optimization and clarity"""

    messages = [
        {"role": "system", "content": BULLET_REWRITE_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    
    return safe_json_call(
        messages, 
        expected_keys=["bullet_rewrites"],
        max_tokens=3000,
    )


# =============================================================================
# TECHNICAL KEYWORD CLASSIFICATION
# =============================================================================

KEYWORD_CLASSIFIER_SYSTEM = """You are an expert at classifying keywords for resume/job matching.

Your task is to identify which keywords from a job description are TECHNICAL or PROFESSIONAL skills that should appear on a resume.

INCLUDE (technical/professional):
- Programming languages (Python, Java, C++, etc.)
- Frameworks and libraries (React, Django, TensorFlow, etc.)
- Databases (PostgreSQL, MongoDB, Redis, etc.)
- Cloud platforms (AWS, Azure, GCP, etc.)
- DevOps tools (Docker, Kubernetes, Jenkins, etc.)
- Methodologies (Agile, Scrum, TDD, etc.)
- Domain-specific technical terms (microservices, REST API, CI/CD, etc.)
- Certifications and standards (PMP, AWS Certified, SOC2, etc.)

EXCLUDE (not for resumes):
- Company perks/benefits (breakfast, cab, gym, insurance, vacation, etc.)
- Generic adjectives (brilliant, amazing, exciting, dynamic, etc.)
- Location names (Gurgaon, New York, etc.)
- Company names unless they're also product names
- Generic business words (opportunity, growth, culture, team, etc.)
- Salary/compensation terms (bonus, equity, stock, etc.)
- Compound phrases like "Python and Java" - split into individual keywords instead

IMPORTANT RULES:
1. Return INDIVIDUAL keywords only, not compound phrases
2. If input has "Python and Java", return ["Python", "Java"] separately
3. Each keyword should be a single technology/skill/tool
4. Normalize variations (e.g., "Node.js" and "NodeJS" -> "Node.js")

Respond with JSON only:
{
  "technical_keywords": ["keyword1", "keyword2", ...]
}

Only include keywords that a candidate should genuinely add to their resume to improve ATS matching."""


def llm_classify_technical_keywords(
    keywords: list[str],
    jd_context: str = "",
) -> Optional[list[str]]:
    """
    Use LLM to classify which keywords are technical/professional.
    
    Args:
        keywords: List of extracted keywords to classify
        jd_context: Optional JD text for context (truncated)
        
    Returns:
        List of technical keywords, or None if LLM unavailable/fails
    """
    if not is_groq_available():
        logger.debug("Groq not available for keyword classification")
        return None
    
    if not keywords:
        return []
    
    # Limit keywords to avoid token overflow
    keywords_to_classify = keywords[:50]
    keywords_str = ", ".join(keywords_to_classify)
    
    # Truncate JD context
    context_str = ""
    if jd_context:
        context_str = f"\n\nJob Description Context (for reference):\n{jd_context[:1000]}..."
    
    user_prompt = f"""Classify these keywords extracted from a job description.
Return only the technical/professional keywords suitable for a resume.

Keywords to classify:
{keywords_str}
{context_str}

Return JSON with the technical keywords only."""

    messages = [
        {"role": "system", "content": KEYWORD_CLASSIFIER_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    
    result = safe_json_call(
        messages,
        expected_keys=["technical_keywords"],
        max_tokens=1000,
        temperature=0.1,  # Very deterministic for classification
    )
    
    if result and "technical_keywords" in result:
        # Validate that returned keywords were in original list
        original_lower = {k.lower() for k in keywords_to_classify}
        validated = [
            kw for kw in result["technical_keywords"]
            if kw.lower() in original_lower
        ]
        return validated
    
    return None


# =============================================================================
# JOB POSTING RELEVANCE CHECK
# =============================================================================

RELEVANCE_CHECK_SYSTEM = """You are a content classifier. Your task is to determine if the given text is related to a job opportunity, hiring, or employment offer.

CLASSIFY AS JOB POSTING (is_job_posting: true) if the text:
- Mentions hiring, job openings, or employment opportunities
- Contains job titles or roles
- Discusses work responsibilities or requirements
- Mentions salary, pay, or compensation
- Claims to offer work-from-home or remote work opportunities
- Asks for registration fees or payments for jobs (even if suspicious)

IMPORTANT: Even if the job posting looks suspicious or like a scam, still classify it as a job posting. We have a separate system to detect scams - your job is only to determine if the text is JOB-RELATED.

CLASSIFY AS NOT JOB POSTING (is_job_posting: false) ONLY if the text is clearly:
- News articles about non-employment topics
- Product advertisements or sales pitches (selling products, not jobs)
- Personal messages or conversations
- Random text, spam, or gibberish with no job context
- Error pages, login pages, or navigation menus
- Recipe, weather, sports, or entertainment content

Respond with ONLY a JSON object:
{
  "is_job_posting": true or false,
  "confidence": number from 0.0 to 1.0 representing how confident you are in your classification (1.0 = very confident, 0.5 = uncertain),
  "reason": "brief explanation"
}"""


def check_job_posting_relevance(
    text: str,
    min_confidence: float = 0.6,
) -> tuple[bool, str]:
    """
    Check if the given text is a relevant job posting using Groq LLM.
    
    Args:
        text: Text to check for job posting relevance
        min_confidence: Minimum confidence threshold (default 0.6)
        
    Returns:
        Tuple of (is_relevant: bool, reason: str)
        - If Groq is unavailable, returns (True, "Groq unavailable, skipping relevance check")
        - If text is clearly a job posting, returns (True, "...")
        - If text is not a job posting, returns (False, "reason why not")
    """
    if not is_groq_available():
        logger.debug("Groq not available, skipping relevance check")
        return True, "Groq unavailable, skipping relevance check"
    
    if not text or len(text.strip()) < 50:
        return False, "Text too short to be a valid job posting"
    
    # Truncate very long text to save tokens
    sample_text = text[:3000] if len(text) > 3000 else text
    
    user_prompt = f"""Analyze this text and determine if it's a job posting or job description:

---
{sample_text}
---

Respond with JSON only."""

    messages = [
        {"role": "system", "content": RELEVANCE_CHECK_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
    
    result = safe_json_call(
        messages,
        expected_keys=["is_job_posting"],
        max_tokens=200,
        temperature=0.1,
    )
    
    if not result:
        # If LLM call fails, assume it's relevant to avoid blocking legitimate requests
        logger.warning("Relevance check LLM call failed, assuming relevant")
        return True, "Relevance check failed, proceeding with analysis"
    
    is_job_posting = result.get("is_job_posting", True)
    confidence = result.get("confidence", 0.5)
    reason = result.get("reason", "No reason provided")
    
    # The LLM returns:
    # - is_job_posting: boolean classification (True = job posting, False = not)
    # - confidence: how confident it is in the classification (0.0 to 1.0)
    #   - High confidence = very sure about the classification
    #   - Low confidence = uncertain about the classification
    
    if is_job_posting:
        # Classified as job posting - return True
        return True, reason
    
    # Classified as NOT a job posting
    # Only reject if confidence in this classification is high enough
    if confidence >= min_confidence:
        # High confidence it's not a job posting - reject
        return False, reason
    
    # Low confidence in the "not a job posting" classification
    # Be conservative and allow it through
    logger.debug(f"Low confidence ({confidence}) in rejection, allowing through")
    return True, f"Low confidence classification ({confidence:.0%}), proceeding with analysis"


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    print(f"Groq available: {is_groq_available()}")
    
    if is_groq_available():
        test_messages = [
            {"role": "system", "content": "You are a helpful assistant. Respond with JSON only."},
            {"role": "user", "content": "Return a JSON object with key 'test' and value 'success'"},
        ]
        
        result = safe_json_call(test_messages, expected_keys=["test"])
        print(f"Test result: {result}")
        
        # Test keyword classification
        test_keywords = [
            "python", "java", "postgresql", "docker", "kubernetes",
            "breakfast", "cab", "gym", "brilliant", "additional",
            "react", "mongodb", "elasticsearch", "benefits", "salary",
            "agile", "microservices", "gurgaon", "tower", "vacation"
        ]
        print(f"\nTesting keyword classification...")
        tech_keywords = llm_classify_technical_keywords(test_keywords)
        print(f"Technical keywords: {tech_keywords}")
        
        # Test relevance check
        print(f"\nTesting job posting relevance check...")
        test_texts = [
            "We are hiring a Software Engineer with 3+ years of Python experience.",
            "Today's weather is sunny with a high of 75 degrees.",
            "Buy our amazing product now! 50% off limited time offer!",
        ]
        for text in test_texts:
            is_relevant, reason = check_job_posting_relevance(text)
            print(f"  '{text[:50]}...' -> relevant={is_relevant}, reason={reason}")
