import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.clients.groq_client import groq_chat, is_groq_available

logger = logging.getLogger(__name__)

# router = APIRouter(prefix="/groq", tags=["Groq AI"])
router = APIRouter()


# SUMMARY_SYSTEM_PROMPT = """You are a job-safety analyst assistant for JobLens AI.

# You will receive a JSON object containing the scam-detection analysis of a job posting.
# Your job is to produce a **concise, human-readable summary** that a non-technical job seeker can understand at a glance.

# STRUCTURE YOUR RESPONSE EXACTLY LIKE THIS (use markdown):

# ## Verdict
# State the final label (LEGIT / SUSPICIOUS / SCAM) with an appropriate emoji (✅, ⚠️, or 🚨) and one sentence explaining what it means for the user.

# ## Risk Score
# Explain the rule score and ML probability in simple terms (e.g., "low risk", "high risk").

# ## Key Findings
# List each rule hit as a bullet point with:
# - A severity indicator (🔴 CRITICAL, 🟠 HIGH, 🟡 MEDIUM, 🟢 LOW)
# - The rule explanation in plain English
# - The matched text snippet (quoted) so the user sees *what* triggered it

# ## Recommendation
# Give 2-3 actionable sentences advising the user what to do next (e.g., "Do not pay any fees", "Verify the company", "Proceed with caution").

# RULES:
# - Keep the entire summary under 300 words.
# - Use simple, friendly language — avoid jargon.
# - Do NOT invent information; only use what the JSON provides.
# - Do NOT output raw JSON or code blocks with JSON.
# """

SUMMARY_SYSTEM_PROMPT = """
You are a job-safety assistant for JobLens AI.

You will receive a JSON object containing analysis results of a job posting. Your task is to convert it into a clear, natural, human-readable explanation that a non-technical job seeker can easily understand.

Write your response as a single coherent paragraph (or at most two short paragraphs).

Requirements:
- Clearly state whether the job is likely SCAM, SUSPICIOUS, or LEGIT.
- Explain the most important reasons based only on the provided data.
- Mention key warning signs in simple language.
- If the job looks risky, explain why in a calm and factual tone.
- If the job looks safe, briefly explain what makes it appear legitimate.
- Do NOT use emojis, colors, bullet points, or structured headings.
- Do NOT include technical terms like ML probability, thresholds, or model scores.
- Do NOT repeat the same idea in different ways.
- Do NOT invent or assume any information not present in the JSON.
- Keep the response under 180–220 words.
- The tone should feel like a trusted career advisor explaining the result to a user.

Focus on clarity, simplicity, and trustworthiness.
"""

class SummarizeRequest(BaseModel):
    ml_probability: float
    ml_pred: int
    rule_hits: list[dict]
    rule_score: float
    final_label: str
    final_reason: str
    decision_path: list[str]
    is_job_posting: bool
    is_legit: bool


class SummarizeResponse(BaseModel):
    summary: str = Field(..., description="Human-readable summary of the scoring result")
    # final_label: str = Field(..., description="Original final label echoed back")
    # is_legit: bool = Field(..., description="Whether the posting was classified as legit")



def generate_score_summary(score_result: dict) -> Optional[str]:
    """
    Generate a human-readable summary of a scoring result using Groq.

    Args:
        score_result: The scoring response dict (same shape as ScoreResponse).

    Returns:
        Markdown-formatted summary string, or None if Groq is unavailable / fails.
    """
    if not is_groq_available():
        logger.warning("Groq API key not configured — cannot generate summary")
        return None

    user_prompt = (
        "Here is the job posting analysis result. "
        "Summarise it for the user:\n\n"
        f"```json\n{json.dumps(score_result, indent=2)}\n```"
    )

    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    summary = groq_chat(
        messages=messages,
        temperature=0.3,  
        max_tokens=1024,
    )

    if summary:
        logger.info("Groq summary generated successfully (%d chars)", len(summary))

    return summary

@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    summary="Generate a human-readable summary of a scoring result",
)
async def summarize_score(request: SummarizeRequest) -> SummarizeResponse:
    """
    Accept a scoring result payload and return a Groq-generated
    human-readable summary in markdown format.
    """
    if not is_groq_available():
        raise HTTPException(
            status_code=503,
            detail="Groq API key is not configured. Set GROQ_API_KEY to enable summaries.",
        )

    score_dict = request.model_dump()
    summary = generate_score_summary(score_dict)

    if summary is None:
        raise HTTPException(
            status_code=502,
            detail="Failed to generate summary from Groq. Please try again.",
        )

    return SummarizeResponse(
        summary=summary,
        # final_label=request.final_label,
        # is_legit=request.is_legit,
    )
