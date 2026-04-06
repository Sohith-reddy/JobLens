"""
Resume parser for JobLens AI.

Extracts structured data from PDF resumes using:
1. PyMuPDF (fitz) for PDF text extraction
2. Heuristic section detection
3. Optional LLM-assisted section labeling
4. SQLite caching for performance

No OCR support - handles text-based PDFs only.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Configuration
MAX_PDF_SIZE = 10 * 1024 * 1024  # 10 MB
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_CACHE_PATH = _PROJECT_ROOT / "data" / "joblens_cache.db"
CACHE_DB_PATH = os.environ.get("JOBLENS_CACHE_DB", str(_DEFAULT_CACHE_PATH))
TEXT_TRUNCATE_LIMIT = 50000  # Max chars to process


@dataclass
class ResumeSchema:
    """Structured resume data schema."""
    basics: dict = field(default_factory=lambda: {
        "name": "",
        "email": "",
        "phone": "",
        "location": "",
        "links": [],
    })
    summary: str = ""
    skills: dict = field(default_factory=lambda: {
        "technical": [],
        "tools": [],
        "soft": [],
    })
    experience: list = field(default_factory=list)
    projects: list = field(default_factory=list)
    education: list = field(default_factory=list)
    certifications: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "basics": self.basics,
            "summary": self.summary,
            "skills": self.skills,
            "experience": self.experience,
            "projects": self.projects,
            "education": self.education,
            "certifications": self.certifications,
        }


@dataclass
class ParseResult:
    """Result of resume parsing."""
    schema: dict
    raw_text: str
    parse_warnings: list[str]
    parse_confidence: float
    timings_ms: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "raw_text": self.raw_text,
            "parse_warnings": self.parse_warnings,
            "parse_confidence": self.parse_confidence,
        }


# =============================================================================
# CACHE
# =============================================================================

def init_cache_db():
    """Initialize SQLite cache database."""
    conn = sqlite3.connect(CACHE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resume_cache (
            cache_key TEXT PRIMARY KEY,
            raw_text TEXT,
            schema_json TEXT,
            created_at TEXT,
            candidate_id TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_cache_key(candidate_id: Optional[str], pdf_bytes: bytes) -> str:
    """Generate cache key from candidate ID and PDF hash."""
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()[:16]
    cid = candidate_id or "anon"
    return f"{cid}_{pdf_hash}"


def get_cached_parse(cache_key: str) -> Optional[dict]:
    """Retrieve cached parse result."""
    try:
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT raw_text, schema_json FROM resume_cache WHERE cache_key = ?",
            (cache_key,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "raw_text": row[0],
                "schema": json.loads(row[1]),
            }
        return None
    except Exception as e:
        logger.debug(f"Cache read error: {e}")
        return None


def set_cached_parse(
    cache_key: str, 
    raw_text: str, 
    schema: dict, 
    candidate_id: Optional[str]
):
    """Store parse result in cache."""
    try:
        init_cache_db()
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO resume_cache 
            (cache_key, raw_text, schema_json, created_at, candidate_id)
            VALUES (?, ?, ?, ?, ?)
        """, (
            cache_key,
            raw_text,
            json.dumps(schema),
            datetime.utcnow().isoformat(),
            candidate_id or "anon",
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"Cache write error: {e}")


def clear_cache(candidate_id: Optional[str] = None):
    """
    Clear the resume cache.
    
    Args:
        candidate_id: If provided, only clear cache for this candidate.
                     If None, clear all cache entries.
    """
    try:
        init_cache_db()
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        
        if candidate_id:
            cursor.execute(
                "DELETE FROM resume_cache WHERE candidate_id = ? OR cache_key LIKE ?",
                (candidate_id, f"{candidate_id}_%")
            )
        else:
            cursor.execute("DELETE FROM resume_cache")
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        logger.info(f"Cleared {deleted} cache entries")
        return deleted
    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return 0


def invalidate_cache_for_pdf(pdf_bytes: bytes, candidate_id: Optional[str] = None):
    """Invalidate cache for a specific PDF."""
    cache_key = get_cache_key(candidate_id, pdf_bytes)
    try:
        init_cache_db()
        conn = sqlite3.connect(CACHE_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM resume_cache WHERE cache_key = ?", (cache_key,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted > 0
    except Exception as e:
        logger.debug(f"Cache invalidation error: {e}")
        return False


# =============================================================================
# PDF EXTRACTION
# =============================================================================

def extract_text_pymupdf(pdf_bytes: bytes) -> tuple[str, list[str]]:
    """
    Extract text from PDF using PyMuPDF (fitz).
    
    Returns:
        Tuple of (extracted_text, warnings)
    """
    warnings = []
    
    try:
        import fitz
    except ImportError:
        raise ImportError("PyMuPDF (fitz) not installed. Run: pip install PyMuPDF")
    
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        text_parts = []
        total_pages = len(doc)
        empty_pages = 0
        
        for page_num, page in enumerate(doc):
            page_text = page.get_text("text")
            
            if not page_text.strip():
                empty_pages += 1
            else:
                text_parts.append(page_text)
        
        doc.close()
        
        if empty_pages == total_pages:
            warnings.append("PDF appears to be scanned/image-based (no extractable text)")
        elif empty_pages > 0:
            warnings.append(f"{empty_pages}/{total_pages} pages have no extractable text")
        
        text = "\n".join(text_parts)
        return text.strip(), warnings
        
    except Exception as e:
        logger.warning(f"PyMuPDF extraction failed: {e}")
        raise


def extract_text_pdfminer(pdf_bytes: bytes) -> tuple[str, list[str]]:
    """
    Fallback extraction using pdfminer.six.
    
    Returns:
        Tuple of (extracted_text, warnings)
    """
    warnings = []
    
    try:
        from pdfminer.high_level import extract_text
        from io import BytesIO
    except ImportError:
        raise ImportError("pdfminer.six not installed. Run: pip install pdfminer.six")
    
    try:
        text = extract_text(BytesIO(pdf_bytes))
        
        if not text.strip():
            warnings.append("PDF appears to be scanned/image-based (no extractable text)")
        
        return text.strip(), warnings
        
    except Exception as e:
        logger.warning(f"pdfminer extraction failed: {e}")
        raise


def extract_pdf_text(pdf_bytes: bytes) -> tuple[str, list[str]]:
    """
    Extract text from PDF with fallback.
    
    Returns:
        Tuple of (extracted_text, warnings)
    """
    # Try PyMuPDF first
    try:
        return extract_text_pymupdf(pdf_bytes)
    except ImportError:
        logger.info("PyMuPDF not available, trying pdfminer")
    except Exception as e:
        logger.warning(f"PyMuPDF failed: {e}, trying pdfminer")
    
    # Fallback to pdfminer
    return extract_text_pdfminer(pdf_bytes)


# =============================================================================
# SECTION DETECTION (HEURISTICS)
# =============================================================================

SECTION_PATTERNS = {
    "summary": [
        r"(?i)^(professional\s+)?summary$",
        r"(?i)^(career\s+)?objective$",
        r"(?i)^profile$",
        r"(?i)^about\s+me$",
        r"(?i)^overview$",
    ],
    "skills": [
        r"(?i)^(technical\s+)?skills$",
        r"(?i)^competenc(ies|es)$",
        r"(?i)^technologies$",
        r"(?i)^expertise$",
        r"(?i)^proficiencies$",
        r"(?i)^tools\s*(and|&)\s*technologies$",
        r"(?i)^core\s+competencies$",
    ],
    "experience": [
        r"(?i)^(work\s+)?experience$",
        r"(?i)^employment(\s+history)?$",
        r"(?i)^professional\s+experience$",
        r"(?i)^career\s+history$",
        r"(?i)^work\s+history$",
    ],
    "projects": [
        r"(?i)^projects$",
        r"(?i)^personal\s+projects$",
        r"(?i)^side\s+projects$",
        r"(?i)^key\s+projects$",
        r"(?i)^academic\s+projects$",
    ],
    "education": [
        r"(?i)^education$",
        r"(?i)^academic\s+background$",
        r"(?i)^qualifications$",
        r"(?i)^educational\s+background$",
    ],
    "certifications": [
        r"(?i)^certifications?$",
        r"(?i)^licenses?\s*(and|&)?\s*certifications?$",
        r"(?i)^credentials$",
        r"(?i)^professional\s+certifications?$",
        r"(?i)^awards?\s*(and|&)?\s*certifications?$",
        r"(?i)^achievements?\s*(and|&)?\s*certific",
        r"(?i)^achievements?\s*(and|&)?\s*awards?$",
        r"(?i)^achievements$",
        r"(?i)^honors?\s*(and|&)?\s*awards?$",
        r"(?i)^awards$",
    ],
}


def detect_section_headers(text: str) -> list[dict]:
    """
    Detect potential section headers in resume text.
    
    Returns:
        List of dicts with 'text', 'line', 'section_type' keys
    """
    lines = text.split("\n")
    headers = []
    
    # Words that look like headers but are actually company names or other content
    false_positive_patterns = [
        r"(?i)^eventbrite$",
        r"(?i)^google$",
        r"(?i)^amazon$",
        r"(?i)^microsoft$",
        r"(?i)^apple$",
        r"(?i)^meta$",
        r"(?i)^facebook$",
        r"(?i)^netflix$",
        r"(?i)^uber$",
        r"(?i)^airbnb$",
        r"(?i)^linkedin$",
        r"(?i)^twitter$",
        r"(?i)^portfolio$",  # Often just a link label
        r"(?i)^leetcode$",
        r"(?i)^github$",
        r"^\d+\.?\d*\s*(cgpa|gpa|%|percent).*$",  # GPA lines
        r"^.*\d+\.?\d*\s*(cgpa|gpa).*$",  # Lines containing GPA
        r"^[A-Z][a-z]+\s+[A-Z][a-z]+$",  # Two-word names (likely person/company names)
        r"^\d+\.?\d*\s*%$",  # Percentage lines
    ]
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Skip empty or very long lines
        if not line_stripped or len(line_stripped) > 60:
            continue
        
        # Skip lines that are likely false positives
        is_false_positive = any(re.match(p, line_stripped) for p in false_positive_patterns)
        if is_false_positive:
            continue
        
        # Check against known patterns
        matched = False
        for section_type, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, line_stripped):
                    headers.append({
                        "text": line_stripped,
                        "line": i + 1,
                        "section_type": section_type,
                    })
                    matched = True
                    break
            if matched:
                break
        
        if not matched:
            # Only consider ALL CAPS lines as potential headers if they:
            # 1. Are ALL CAPS
            # 2. Have more than one word OR are a known section keyword
            # 3. Don't look like company names
            if line_stripped.isupper() and len(line_stripped) > 5 and len(line_stripped) < 40:
                words = line_stripped.split()
                # Must have multiple words or be a known section-like word
                section_keywords = ["SKILLS", "EXPERIENCE", "EDUCATION", "PROJECTS", "SUMMARY", 
                                   "CERTIFICATIONS", "ACHIEVEMENTS", "AWARDS", "QUALIFICATIONS",
                                   "OBJECTIVE", "PROFILE", "BACKGROUND", "HISTORY"]
                if len(words) >= 2 or any(kw in line_stripped for kw in section_keywords):
                    headers.append({
                        "text": line_stripped,
                        "line": i + 1,
                        "section_type": "unknown",
                    })
    
    return headers


def split_into_sections(text: str, headers: list[dict]) -> dict[str, str]:
    """
    Split text into sections based on detected headers.
    
    Returns:
        Dict mapping section type to section text
    """
    lines = text.split("\n")
    sections = {}
    
    # Sort headers by line number
    sorted_headers = sorted(headers, key=lambda h: h["line"])
    
    for i, header in enumerate(sorted_headers):
        start_line = header["line"]
        section_type = header["section_type"]
        
        # Find end line (next header or end of document)
        if i + 1 < len(sorted_headers):
            end_line = sorted_headers[i + 1]["line"] - 1
        else:
            end_line = len(lines)
        
        # Extract section text
        section_lines = lines[start_line:end_line]  # Skip header line itself
        section_text = "\n".join(section_lines).strip()
        
        if section_text:
            # Handle multiple sections of same type
            if section_type in sections:
                sections[section_type] += "\n\n" + section_text
            else:
                sections[section_type] = section_text
    
    return sections


# =============================================================================
# FIELD EXTRACTION (HEURISTICS)
# =============================================================================

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}")
URL_PATTERN = re.compile(r"https?://[^\s<>\"]+")
# Pattern to detect social/professional links even without full URLs
LINK_KEYWORDS_PATTERN = re.compile(
    r"(?:linkedin\.com|github\.com|gitlab\.com|bitbucket\.org|leetcode\.com|"
    r"hackerrank\.com|codeforces\.com|codechef\.com|portfolio|"
    r"github|linkedin|leetcode)[:/\s]*([a-zA-Z0-9_-]+)",
    re.IGNORECASE
)
DATE_PATTERN = re.compile(
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*)?(?:20\d{2}|19\d{2})|"
    r"(?:\d{1,2}/\d{4})|"
    r"(?:\d{1,2}/\d{1,2}/\d{2,4})|"
    r"(?:Present|Current|Now|Ongoing|Expected)",
    re.IGNORECASE
)
# Pattern for date ranges like "Jul 2025 – Present" or "2022 - 2026"
DATE_RANGE_PATTERN = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*)?(\d{4})\s*[-–—]\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*)?((?:\d{4})|Present|Current|Expected)",
    re.IGNORECASE
)


def extract_basics(text: str, sections: dict) -> dict:
    """Extract basic contact information."""
    basics = {
        "name": "",
        "email": "",
        "phone": "",
        "location": "",
        "links": [],
    }
    
    # Use first few lines for contact info (usually at top)
    header_lines = text.split("\n")[:20]
    header_text = "\n".join(header_lines)
    
    # Email
    emails = EMAIL_PATTERN.findall(text)
    if emails:
        basics["email"] = emails[0]
    
    # Phone - look for various formats including international
    phone_patterns = [
        r"\+?\d{1,3}[-.\s]?\d{10}",  # +91 7671898733
        r"\+?\d{1,3}[-.\s]?\d{3,4}[-.\s]?\d{3,4}[-.\s]?\d{4}",  # +1-234-567-8901
        r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",  # (123) 456-7890
    ]
    for pattern in phone_patterns:
        match = re.search(pattern, header_text)
        if match:
            basics["phone"] = match.group().strip()
            break
    
    # Links - extract full URLs
    links = set()
    full_urls = URL_PATTERN.findall(text)
    links.update(full_urls)
    
    # Also look for partial link references (common in PDFs)
    # e.g., "ï kaushik-kadari" for LinkedIn, "§ kaushik-kadari" for GitHub
    for line in text.split("\n"):
        line_lower = line.lower()
        # GitHub references
        if "github" in line_lower or "§" in line:
            match = re.search(r"(?:github\.com/|§\s*)([a-zA-Z0-9_-]+)", line, re.IGNORECASE)
            if match:
                links.add(f"https://github.com/{match.group(1)}")
        # LinkedIn references  
        if "linkedin" in line_lower or "ï" in line:
            match = re.search(r"(?:linkedin\.com/in/|ï\s*)([a-zA-Z0-9_-]+)", line, re.IGNORECASE)
            if match:
                links.add(f"https://linkedin.com/in/{match.group(1)}")
        # Leetcode references
        if "leetcode" in line_lower or "Ð" in line:
            match = re.search(r"(?:leetcode\.com/|Ð\s*)([a-zA-Z0-9_-]+)", line, re.IGNORECASE)
            if match:
                links.add(f"https://leetcode.com/{match.group(1)}")
        # Portfolio
        if "portfolio" in line_lower:
            links.add("Portfolio (link in resume)")
    
    basics["links"] = list(links)[:10]
    
    # Name - usually first non-empty line that looks like a name
    for line in header_lines[:8]:
        line = line.strip()
        if not line:
            continue
        # Skip lines with special characters, emails, phones, or section headers
        if (
            len(line) > 2 and 
            len(line) < 50 and
            not EMAIL_PATTERN.search(line) and
            not re.search(r"\d{4,}", line) and  # No long numbers
            not URL_PATTERN.search(line) and
            not any(kw in line.lower() for kw in ["education", "experience", "skills", "project", "summary"]) and
            not line.startswith(("+", "•", "-", "§", "ï", "Ð", "#")) and
            re.match(r"^[A-Z][A-Za-z\s]+$", line)  # Looks like a name (starts with capital, letters/spaces only)
        ):
            basics["name"] = line
            break
    
    # Location - look for city, state/country patterns
    location_patterns = [
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z]+)",  # City, State, Country
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # City, State/Country
        r"([A-Z][a-z]+,\s*[A-Z]{2})",  # City, ST
    ]
    for pattern in location_patterns:
        match = re.search(pattern, header_text)
        if match:
            loc = match.group(1)
            # Avoid matching section headers
            if not any(kw in loc.lower() for kw in ["education", "experience", "skills", "project"]):
                basics["location"] = loc
                break
    
    return basics


def extract_skills(text: str, sections: dict) -> dict:
    """Extract skills categorized by type."""
    skills = {
        "technical": [],
        "tools": [],
        "soft": [],
    }
    
    skills_text = sections.get("skills", "")
    
    # Common technical skills (languages, frameworks, databases, cloud, etc.)
    tech_keywords = [
        # Languages
        "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang", "rust", "swift", "kotlin", "ruby", "php", "scala", "r",
        "c", "perl", "haskell", "lua", "dart", "objective-c", "shell", "bash",
        # Frontend
        "react", "react.js", "reactjs", "angular", "vue", "vue.js", "vuejs", "svelte", "next.js", "nextjs", "nuxt", "gatsby",
        "html", "css", "sass", "scss", "less", "tailwind", "bootstrap", "material-ui", "chakra",
        # Backend
        "node", "node.js", "nodejs", "express", "express.js", "expressjs", "django", "flask", "fastapi", "spring", "spring boot",
        "rails", "ruby on rails", "laravel", "asp.net", ".net", "nestjs",
        # Mobile
        "swiftui", "uikit", "react native", "flutter", "android", "ios",
        # Databases
        "sql", "nosql", "mongodb", "postgresql", "postgres", "mysql", "redis", "elasticsearch", "cassandra", "dynamodb",
        "sqlite", "oracle", "mariadb", "neo4j", "firebase", "supabase",
        # Cloud & DevOps
        "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s", "terraform", "jenkins", "ci/cd", "github actions",
        "ansible", "puppet", "chef", "vagrant", "nginx", "apache",
        # AI/ML
        "machine learning", "deep learning", "nlp", "computer vision", "tensorflow", "pytorch", "keras", "scikit-learn",
        "pandas", "numpy", "scipy", "opencv", "huggingface", "langchain", "llm", "gen ai", "generative ai", "rag",
        # Other
        "git", "linux", "unix", "api", "rest", "restful", "graphql", "grpc", "microservices", "websocket",
        "webpack", "vite", "babel", "npm", "yarn", "pnpm",
        "cuda", "openmp", "mpi", "parallel programming", "hpc",
    ]
    
    # Common tools
    tool_keywords = [
        "jira", "confluence", "slack", "trello", "asana", "notion", "linear",
        "figma", "sketch", "adobe", "photoshop", "illustrator", "xd",
        "excel", "powerpoint", "word", "google sheets", "google docs",
        "tableau", "power bi", "looker", "datadog", "splunk", "grafana", "prometheus",
        "postman", "swagger", "insomnia", "vscode", "intellij", "pycharm", "xcode", "android studio",
        "github", "gitlab", "bitbucket", "sourcetree",
        "google colab", "jupyter", "staruml",
    ]
    
    # Common soft skills
    soft_keywords = [
        "leadership", "communication", "teamwork", "problem-solving", "problem solving",
        "analytical", "creative", "adaptable", "organized", "detail-oriented",
        "time management", "project management", "agile", "scrum", "kanban",
        "collaboration", "mentoring", "presentation", "negotiation", "critical thinking",
    ]
    
    # First, try to extract from skills section with structured parsing
    if skills_text:
        # Look for "Languages:", "Frontend:", etc. patterns
        category_patterns = [
            (r"languages?:\s*([^\n]+)", "technical"),
            (r"frontend:\s*([^\n]+)", "technical"),
            (r"backend:\s*([^\n]+)", "technical"),
            (r"databases?:\s*([^\n]+)", "technical"),
            (r"tools?\s*(?:&|and)?\s*platforms?:\s*([^\n]+)", "tools"),
            (r"frameworks?:\s*([^\n]+)", "technical"),
            (r"app\s*development:\s*([^\n]+)", "technical"),
        ]
        
        for pattern, category in category_patterns:
            match = re.search(pattern, skills_text, re.IGNORECASE)
            if match:
                items = re.split(r"[,;|]", match.group(1))
                for item in items:
                    item = item.strip()
                    if item and len(item) > 1 and len(item) < 30:
                        skills[category].append(item)
    
    # Also scan full text for known keywords
    full_text_lower = text.lower()
    
    for kw in tech_keywords:
        if kw in full_text_lower:
            # Normalize the keyword
            normalized = kw.replace(".", "").replace("-", "")
            if len(kw) <= 3:
                display = kw.upper()
            elif kw in ["javascript", "typescript", "postgresql", "mongodb", "elasticsearch"]:
                display = kw.title().replace("sql", "SQL").replace("db", "DB")
            elif "." in kw or kw.endswith("js"):
                display = kw  # Keep as-is for things like "React.js"
            else:
                display = kw.title()
            
            # Avoid duplicates (case-insensitive)
            if not any(s.lower() == display.lower() for s in skills["technical"]):
                skills["technical"].append(display)
    
    for kw in tool_keywords:
        if kw in full_text_lower:
            display = kw.title()
            if not any(s.lower() == display.lower() for s in skills["tools"]):
                skills["tools"].append(display)
    
    for kw in soft_keywords:
        if kw in full_text_lower:
            display = kw.title()
            if not any(s.lower() == display.lower() for s in skills["soft"]):
                skills["soft"].append(display)
    
    # Deduplicate and limit
    skills["technical"] = list(dict.fromkeys(skills["technical"]))[:30]
    skills["tools"] = list(dict.fromkeys(skills["tools"]))[:20]
    skills["soft"] = list(dict.fromkeys(skills["soft"]))[:15]
    
    return skills


def extract_experience(text: str, sections: dict) -> list[dict]:
    """Extract work experience entries."""
    experience = []
    
    exp_text = sections.get("experience", "")
    if not exp_text:
        return experience
    
    lines = [l.strip() for l in exp_text.split("\n")]
    
    # Job title keywords to identify title lines
    title_keywords = [
        "engineer", "developer", "manager", "analyst", "designer", "lead", 
        "director", "intern", "scientist", "architect", "consultant", "specialist",
        "coordinator", "administrator", "associate", "executive", "officer",
        "sde", "swe", "mts", "sse", "staff", "principal", "senior", "junior"
    ]
    
    current_entry = None
    last_was_bullet = False
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        if not line:
            i += 1
            continue
        
        is_bullet = line.startswith(("•", "-", "*", "–", "›"))
        is_date_line = bool(DATE_RANGE_PATTERN.search(line)) and len(line) < 40
        is_title_line = any(kw in line.lower() for kw in title_keywords) and len(line) < 60 and not is_bullet
        is_location_line = bool(re.match(r"^[A-Z][a-z]+(?:,\s*[A-Z][a-z]+)+$", line)) and len(line) < 50
        
        # Check if this is a continuation line (non-bullet line that continues previous bullet)
        is_continuation = False
        if not is_bullet and current_entry and last_was_bullet and current_entry["bullets"]:
            last_bullet = current_entry["bullets"][-1]
            # Continuation conditions:
            # 1. Previous bullet doesn't end with punctuation, OR
            # 2. Current line starts with lowercase, OR
            # 3. Current line is clearly a fragment (short, no capital start pattern)
            ends_incomplete = not last_bullet.rstrip().endswith((".", "!", "?", ":"))
            starts_lowercase = line[0].islower() if line else False
            is_fragment = len(line) < 80 and not re.match(r"^[A-Z][a-z]+\s+[A-Z]", line)
            
            if not is_date_line and not is_title_line and not is_location_line:
                if ends_incomplete or starts_lowercase or (is_fragment and not line[0].isupper()):
                    is_continuation = True
        
        if is_continuation:
            # Append to the last bullet
            current_entry["bullets"][-1] += " " + line
            # Re-extract metrics from updated bullet
            metrics = re.findall(r"\d+%|\$[\d,]+[KMB]?|\d+[KMB]\+?|\d+x|\d+\+", line)
            current_entry["impact_metrics"].extend(metrics)
            last_was_bullet = True
            i += 1
            continue
        
        # Check if this is a company name line (starts a new entry)
        is_company_line = (
            not is_bullet and 
            not is_date_line and 
            not is_title_line and 
            not is_location_line and
            len(line) > 2 and 
            len(line) < 80 and
            not line.lower().startswith(("languages", "tools", "relevant", "•"))
        )
        
        # Look ahead to see if this starts a new experience block
        if is_company_line:
            # Check next few lines for date/title pattern
            has_following_date = False
            has_following_title = False
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j]
                if not next_line:
                    continue
                if DATE_RANGE_PATTERN.search(next_line):
                    has_following_date = True
                if any(kw in next_line.lower() for kw in title_keywords):
                    has_following_title = True
                if next_line.startswith(("•", "-")):
                    break
            
            if has_following_date or has_following_title:
                # This is a new experience entry
                if current_entry and (current_entry["company"] or current_entry["title"]):
                    experience.append(current_entry)
                
                current_entry = {
                    "company": line,
                    "title": "",
                    "start": "",
                    "end": "",
                    "location": "",
                    "bullets": [],
                    "tech": [],
                    "impact_metrics": [],
                }
                last_was_bullet = False
                i += 1
                continue
        
        # If we have a current entry, try to fill in its fields
        if current_entry is not None:
            if is_date_line and not current_entry["start"]:
                date_match = DATE_RANGE_PATTERN.search(line)
                if date_match:
                    current_entry["start"] = f"{date_match.group(1) or ''}{date_match.group(2)}".strip()
                    current_entry["end"] = f"{date_match.group(3) or ''}{date_match.group(4)}".strip()
                last_was_bullet = False
            elif is_title_line and not current_entry["title"]:
                current_entry["title"] = line
                last_was_bullet = False
            elif is_location_line and not current_entry["location"]:
                current_entry["location"] = line
                last_was_bullet = False
            elif is_bullet:
                bullet = re.sub(r"^[•\-*–›\d.]+\s*", "", line)
                if len(bullet) > 10:
                    current_entry["bullets"].append(bullet)
                    # Extract metrics
                    metrics = re.findall(r"\d+%|\$[\d,]+[KMB]?|\d+[KMB]\+?|\d+x|\d+\+", bullet)
                    current_entry["impact_metrics"].extend(metrics)
                last_was_bullet = True
            else:
                last_was_bullet = False
        
        i += 1
    
    # Don't forget the last entry
    if current_entry and (current_entry["company"] or current_entry["title"]):
        experience.append(current_entry)
    
    # Filter out invalid entries (like continuation fragments that got mistakenly added)
    valid_experience = []
    for exp in experience:
        # Must have either a real company name or title
        has_valid_company = exp["company"] and len(exp["company"]) > 3 and not exp["company"].endswith(".")
        has_valid_title = exp["title"] and len(exp["title"]) > 3
        if has_valid_company or has_valid_title:
            valid_experience.append(exp)
    
    return valid_experience[:10]


def extract_projects(text: str, sections: dict) -> list[dict]:
    """Extract project entries."""
    projects = []
    
    proj_text = sections.get("projects", "")
    if not proj_text:
        return projects
    
    lines = proj_text.split("\n")
    current_project = None
    last_was_bullet = False
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        if not line_stripped:
            continue
        
        is_bullet = line_stripped.startswith(("•", "-", "*", "–", "›"))
        
        # Check if this is a date-only line (like "Feb 2025" or "Jul 2024")
        is_date_only = bool(re.match(r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}$", line_stripped, re.IGNORECASE))
        is_year_only = bool(re.match(r"^\d{4}$", line_stripped))
        
        if is_date_only or is_year_only:
            # This is a date line, associate with current project
            if current_project:
                current_project["date"] = line_stripped
            continue
        
        # Check if this is a continuation line (non-bullet line that continues previous bullet)
        # Continuation lines typically:
        # - Don't start with capital letter at beginning of sentence context
        # - Are short fragments
        # - Come right after a bullet that doesn't end with period
        is_continuation = False
        if not is_bullet and current_project and last_was_bullet:
            # Check if previous bullet ended without proper punctuation
            if current_project["bullets"]:
                last_bullet = current_project["bullets"][-1]
                if not last_bullet.endswith((".", "!", "?")):
                    # This line likely continues the previous bullet
                    is_continuation = True
        
        if is_continuation:
            # Append to the last bullet
            if current_project and current_project["bullets"]:
                current_project["bullets"][-1] += " " + line_stripped
            last_was_bullet = True
            continue
        
        # Check if this is a project header line
        # Project headers typically:
        # - Start with § or contain | with tech stack
        # - Have "Demo" or "Working Demo" in them
        # - Are followed by bullets or date
        if not is_bullet:
            has_project_indicator = (
                line_stripped.startswith("§") or
                "|" in line_stripped or
                "demo" in line_stripped.lower() or
                "github.com" in line_stripped.lower()
            )
            
            # Also check if followed by date or bullets
            next_is_date_or_bullet = False
            for j in range(i + 1, min(i + 3, len(lines))):
                next_line = lines[j].strip()
                if not next_line:
                    continue
                if next_line.startswith(("•", "-", "*", "–", "›")):
                    next_is_date_or_bullet = True
                    break
                if re.match(r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}$", next_line, re.IGNORECASE):
                    next_is_date_or_bullet = True
                    break
                # If next line is another potential header, stop
                if "|" in next_line or next_line.startswith("§"):
                    break
            
            if has_project_indicator or next_is_date_or_bullet:
                # Save previous project
                if current_project and current_project["name"]:
                    projects.append(current_project)
                
                # Start new project
                current_project = {
                    "name": "",
                    "bullets": [],
                    "tech": [],
                    "links": [],
                    "date": "",
                }
                
                # Parse project name and tech stack
                name = line_stripped
                # Remove leading symbols like §
                name = re.sub(r"^[§#*]+\s*", "", name)
                
                # Extract tech stack from name (e.g., "Project | React.js, Express.js, MongoDB, LLM, Gen AI")
                if "|" in name:
                    parts = name.split("|")
                    name = parts[0].strip()
                    if len(parts) > 1:
                        tech_str = "|".join(parts[1:])
                        # Extract individual technologies
                        techs = re.findall(r"[A-Za-z][A-Za-z0-9.+#]+(?:\s+[A-Za-z]+)?", tech_str)
                        current_project["tech"] = [t.strip() for t in techs if len(t.strip()) > 1 and t.strip().lower() not in ["working", "demo", "live"]]
                
                # Check for demo link indicator
                if "demo" in line_stripped.lower():
                    current_project["links"].append("Demo available")
                
                # Extract any URLs
                urls = URL_PATTERN.findall(line_stripped)
                current_project["links"].extend(urls)
                
                current_project["name"] = name.strip()
                last_was_bullet = False
                continue
        
        # Handle bullet points
        if is_bullet and current_project is not None:
            bullet = re.sub(r"^[•\-*–›\d.]+\s*", "", line_stripped)
            if len(bullet) > 10:
                current_project["bullets"].append(bullet)
            last_was_bullet = True
        else:
            last_was_bullet = False
    
    # Don't forget the last project
    if current_project and current_project["name"]:
        projects.append(current_project)
    
    # Clean up projects
    cleaned_projects = []
    for proj in projects:
        # Remove date field
        if "date" in proj:
            del proj["date"]
        # Only include projects with actual content
        if proj["name"] and (proj["bullets"] or proj["tech"]):
            cleaned_projects.append(proj)
    
    return cleaned_projects[:8]


def extract_education(text: str, sections: dict) -> list[dict]:
    """Extract education entries."""
    education = []
    
    edu_text = sections.get("education", "")
    if not edu_text:
        return education
    
    lines = edu_text.split("\n")
    current_entry = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Check for degree keywords
        degree_keywords = ["bachelor", "master", "phd", "doctorate", "associate", "b.s.", "m.s.", "b.a.", "m.a.", "mba", "bs", "ms", "ba", "ma", "b.tech", "m.tech", "btech", "mtech", "b.e.", "m.e."]
        has_degree = any(kw in line.lower() for kw in degree_keywords)
        
        # Check for school keywords
        school_keywords = ["university", "college", "institute", "school", "academy"]
        has_school = any(kw in line.lower() for kw in school_keywords)
        
        # Check for date range
        date_match = DATE_RANGE_PATTERN.search(line)
        
        if has_school:
            # Save previous entry
            if current_entry and (current_entry["school"] or current_entry["degree"]):
                education.append(current_entry)
            
            # Start new entry
            current_entry = {
                "school": "",
                "degree": "",
                "field": "",
                "start": "",
                "end": "",
                "gpa": "",
            }
            
            # Extract school name (remove date if present)
            school_name = line
            if date_match:
                current_entry["start"] = f"{date_match.group(1) or ''}{date_match.group(2)}".strip()
                current_entry["end"] = f"{date_match.group(3) or ''}{date_match.group(4)}".strip()
                school_name = DATE_RANGE_PATTERN.sub("", school_name).strip()
            
            current_entry["school"] = school_name
            
        elif has_degree and current_entry:
            # This line has degree info
            degree_line = line
            if date_match and not current_entry["start"]:
                current_entry["start"] = f"{date_match.group(1) or ''}{date_match.group(2)}".strip()
                current_entry["end"] = f"{date_match.group(3) or ''}{date_match.group(4)}".strip()
                degree_line = DATE_RANGE_PATTERN.sub("", degree_line).strip()
            
            current_entry["degree"] = degree_line
            
        elif current_entry:
            # Check for dates
            if date_match and not current_entry["start"]:
                current_entry["start"] = f"{date_match.group(1) or ''}{date_match.group(2)}".strip()
                current_entry["end"] = f"{date_match.group(3) or ''}{date_match.group(4)}".strip()
            
            # Check for GPA/CGPA
            gpa_match = re.search(r"(\d+\.?\d*)\s*(?:CGPA|GPA|cgpa|gpa)", line, re.IGNORECASE)
            if gpa_match:
                current_entry["gpa"] = gpa_match.group(1)
            
            # Check for percentage
            pct_match = re.search(r"(\d+\.?\d*)\s*%", line)
            if pct_match and not current_entry["gpa"]:
                current_entry["gpa"] = f"{pct_match.group(1)}%"
    
    # Don't forget the last entry
    if current_entry and (current_entry["school"] or current_entry["degree"]):
        education.append(current_entry)
    
    # Clean up - remove empty fields
    cleaned_education = []
    for edu in education:
        cleaned = {
            "school": edu.get("school", ""),
            "degree": edu.get("degree", ""),
            "start": edu.get("start", ""),
            "end": edu.get("end", ""),
        }
        if edu.get("gpa"):
            cleaned["gpa"] = edu["gpa"]
        if edu.get("field"):
            cleaned["field"] = edu["field"]
        cleaned_education.append(cleaned)
    
    return cleaned_education[:5]


def extract_certifications(text: str, sections: dict) -> list[str]:
    """Extract certifications and achievements."""
    certs = []
    
    # Check for certifications section
    cert_text = sections.get("certifications", "")
    
    if cert_text:
        for line in cert_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Skip section headers (ALL CAPS short lines)
            if line.upper() == line and len(line) < 50:
                continue
            
            # Skip lines that are just section header variations
            header_patterns = [
                r"^achievements?\s*(and|&)?\s*certific",
                r"^certifications?\s*(and|&)?\s*achievements?",
                r"^awards?\s*(and|&)?\s*achievements?",
                r"^honors?\s*(and|&)?\s*awards?",
            ]
            is_header = any(re.match(p, line, re.IGNORECASE) for p in header_patterns)
            if is_header:
                continue
            
            # Only include lines that start with bullet points (actual achievements)
            if line.startswith(("•", "-", "*", "–", "›")):
                # Remove bullet markers
                clean_line = re.sub(r"^[•\-*–›\d.]+\s*", "", line)
                if clean_line and len(clean_line) > 15 and len(clean_line) < 250:
                    # Verify it looks like an achievement/certification
                    achievement_indicators = [
                        "achieved", "secured", "rank", "place", "winner", "won",
                        "certified", "certification", "certificate", "completed",
                        "awarded", "recognized", "selected", "top", "first",
                        "nptel", "coursera", "udemy", "linkedin learning",
                        "leetcode", "hackerrank", "codeforces", "codechef",
                        "aws", "azure", "gcp", "google", "microsoft", "oracle"
                    ]
                    line_lower = clean_line.lower()
                    if any(ind in line_lower for ind in achievement_indicators):
                        certs.append(clean_line)
    
    # If no certifications found in section, search full text for achievement patterns
    if not certs:
        # Look for bullet points with achievement keywords anywhere in text
        for line in text.split("\n"):
            line = line.strip()
            if not line.startswith(("•", "-")):
                continue
            
            clean_line = re.sub(r"^[•\-*–›\d.]+\s*", "", line)
            if not clean_line or len(clean_line) < 15 or len(clean_line) > 250:
                continue
            
            line_lower = clean_line.lower()
            achievement_indicators = [
                "achieved", "secured", "rank", "place", "winner", "won",
                "certified", "certification", "certificate", "completed",
                "awarded", "recognized", "selected", "top", "first",
                "nptel", "coursera", "udemy", "linkedin learning",
                "leetcode", "hackerrank", "codeforces", "codechef",
                "knight", "rating", "solved", "problems"
            ]
            
            if any(ind in line_lower for ind in achievement_indicators):
                # Make sure it's not an experience bullet
                experience_indicators = ["developed", "built", "implemented", "designed", "created", "managed", "led"]
                if not any(ind in line_lower for ind in experience_indicators):
                    certs.append(clean_line)
    
    # Deduplicate while preserving order
    seen = set()
    unique_certs = []
    for cert in certs:
        cert_lower = cert.lower()
        if cert_lower not in seen:
            seen.add(cert_lower)
            unique_certs.append(cert)
    
    return unique_certs[:10]


# =============================================================================
# MAIN PARSER
# =============================================================================

def parse_resume(
    pdf_bytes: bytes,
    candidate_id: Optional[str] = None,
    use_llm: bool = True,
    use_cache: bool = True,
) -> ParseResult:
    """
    Parse a PDF resume into structured schema.
    
    Args:
        pdf_bytes: Raw PDF file bytes
        candidate_id: Optional candidate identifier for caching
        use_llm: Whether to use LLM for section labeling assistance
        use_cache: Whether to use/update cache
        
    Returns:
        ParseResult with schema, raw_text, warnings, and confidence
    """
    timings = {}
    warnings = []
    
    # Validate PDF size
    if len(pdf_bytes) > MAX_PDF_SIZE:
        raise ValueError(f"PDF too large: {len(pdf_bytes)} bytes (max {MAX_PDF_SIZE})")
    
    # Check cache
    cache_key = get_cache_key(candidate_id, pdf_bytes)
    
    if use_cache:
        init_cache_db()
        cached = get_cached_parse(cache_key)
        if cached:
            logger.info(f"Cache hit for {cache_key}")
            return ParseResult(
                schema=cached["schema"],
                raw_text=cached["raw_text"],
                parse_warnings=["Loaded from cache"],
                parse_confidence=0.9,
                timings_ms={"cache_hit": True},
            )
    
    # Extract text from PDF
    t0 = time.time()
    try:
        raw_text, extract_warnings = extract_pdf_text(pdf_bytes)
        warnings.extend(extract_warnings)
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise ValueError(f"Failed to extract text from PDF: {e}")
    timings["pdf_extract"] = int((time.time() - t0) * 1000)
    
    if not raw_text.strip():
        warnings.append("No text extracted from PDF - may be scanned/image-based")
        return ParseResult(
            schema=ResumeSchema().to_dict(),
            raw_text="",
            parse_warnings=warnings,
            parse_confidence=0.0,
            timings_ms=timings,
        )
    
    # Truncate if needed
    if len(raw_text) > TEXT_TRUNCATE_LIMIT:
        raw_text = raw_text[:TEXT_TRUNCATE_LIMIT]
        warnings.append(f"Text truncated to {TEXT_TRUNCATE_LIMIT} characters")
    
    # Detect section headers
    t0 = time.time()
    headers = detect_section_headers(raw_text)
    
    # Optionally use LLM for section labeling
    if use_llm and headers:
        try:
            from core.clients.groq_client import llm_label_sections, is_groq_available
            
            if is_groq_available():
                llm_sections = llm_label_sections(raw_text, headers)
                if llm_sections:
                    # Merge LLM results with heuristic headers
                    for section_type, line_range in llm_sections.items():
                        if isinstance(line_range, dict) and "start" in line_range:
                            # Update header section types based on LLM
                            for h in headers:
                                if h["line"] >= line_range.get("start", 0) and h["line"] <= line_range.get("end", 9999):
                                    if h["section_type"] == "unknown":
                                        h["section_type"] = section_type
        except Exception as e:
            logger.debug(f"LLM section labeling failed: {e}")
    
    # Split into sections
    sections = split_into_sections(raw_text, headers)
    timings["parse"] = int((time.time() - t0) * 1000)
    
    # Extract fields
    t0 = time.time()
    schema = ResumeSchema()
    schema.basics = extract_basics(raw_text, sections)
    schema.summary = sections.get("summary", "")[:2000]
    schema.skills = extract_skills(raw_text, sections)
    schema.experience = extract_experience(raw_text, sections)
    schema.projects = extract_projects(raw_text, sections)
    schema.education = extract_education(raw_text, sections)
    schema.certifications = extract_certifications(raw_text, sections)
    
    # Optionally use LLM to complete schema
    if use_llm:
        try:
            from core.clients.groq_client import llm_complete_schema, is_groq_available
            
            if is_groq_available():
                completed = llm_complete_schema(schema.to_dict(), raw_text)
                if completed:
                    # Merge LLM completions (only fill empty fields)
                    if not schema.basics.get("name") and completed.get("basics", {}).get("name"):
                        schema.basics["name"] = completed["basics"]["name"]
                    if not schema.summary and completed.get("summary"):
                        schema.summary = completed["summary"][:2000]
        except Exception as e:
            logger.debug(f"LLM schema completion failed: {e}")
    
    timings["field_extraction"] = int((time.time() - t0) * 1000)
    
    # Calculate confidence
    confidence = calculate_parse_confidence(schema.to_dict(), raw_text)
    
    # Cache result
    if use_cache:
        set_cached_parse(cache_key, raw_text, schema.to_dict(), candidate_id)
    
    return ParseResult(
        schema=schema.to_dict(),
        raw_text=raw_text,
        parse_warnings=warnings,
        parse_confidence=confidence,
        timings_ms=timings,
    )


def calculate_parse_confidence(schema: dict, raw_text: str) -> float:
    """Calculate confidence score for parse quality."""
    score = 0.0
    
    # Basics (0.2)
    basics = schema.get("basics", {})
    if basics.get("name"):
        score += 0.05
    if basics.get("email"):
        score += 0.05
    if basics.get("phone"):
        score += 0.03
    if basics.get("links"):
        score += 0.02
    if basics.get("location"):
        score += 0.05
    
    # Skills (0.2)
    skills = schema.get("skills", {})
    tech_count = len(skills.get("technical", []))
    if tech_count >= 5:
        score += 0.15
    elif tech_count >= 2:
        score += 0.08
    if skills.get("tools"):
        score += 0.03
    if skills.get("soft"):
        score += 0.02
    
    # Experience (0.3)
    experience = schema.get("experience", [])
    if len(experience) >= 2:
        score += 0.15
    elif len(experience) >= 1:
        score += 0.08
    
    # Check experience quality
    for exp in experience[:3]:
        if exp.get("title") and exp.get("company"):
            score += 0.03
        if exp.get("bullets"):
            score += 0.02
    
    # Education (0.15)
    education = schema.get("education", [])
    if education:
        score += 0.1
        if education[0].get("degree"):
            score += 0.05
    
    # Projects (0.1)
    if schema.get("projects"):
        score += 0.05
        if len(schema["projects"]) >= 2:
            score += 0.05
    
    # Summary (0.05)
    if schema.get("summary"):
        score += 0.05
    
    return min(1.0, round(score, 2))


def parse_resume_from_base64(
    base64_pdf: str,
    candidate_id: Optional[str] = None,
    use_llm: bool = True,
) -> ParseResult:
    """
    Parse resume from base64-encoded PDF.
    
    Args:
        base64_pdf: Base64-encoded PDF bytes
        candidate_id: Optional candidate identifier
        use_llm: Whether to use LLM assistance
        
    Returns:
        ParseResult
    """
    try:
        pdf_bytes = base64.b64decode(base64_pdf)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}")
    
    return parse_resume(pdf_bytes, candidate_id, use_llm)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.DEBUG)
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        result = parse_resume(pdf_bytes, use_llm=False)
        
        print(f"\nParse confidence: {result.parse_confidence}")
        print(f"Warnings: {result.parse_warnings}")
        print(f"Timings: {result.timings_ms}")
        print(f"\nSchema:")
        print(json.dumps(result.schema, indent=2))
    else:
        print("Usage: python resume_parser.py <path_to_pdf>")
