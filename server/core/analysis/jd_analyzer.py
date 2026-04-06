"""
Job Description analyzer for JobLens AI.

Extracts structured requirements, keywords, and skills from job descriptions
for matching against resumes.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class JDAnalysis:
    """Analyzed job description data."""
    title: str = ""
    company: str = ""
    location: str = ""
    
    # Requirements categorized by importance
    must_have: list[str] = field(default_factory=list)
    nice_to_have: list[str] = field(default_factory=list)
    
    # Skills extracted
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    
    # Experience requirements
    min_years_experience: Optional[int] = None
    max_years_experience: Optional[int] = None
    seniority_level: str = ""  # entry, mid, senior, lead, principal
    
    # Keywords for ATS matching
    keywords: list[str] = field(default_factory=list)
    
    # Responsibilities
    responsibilities: list[str] = field(default_factory=list)
    
    # Raw sections
    raw_requirements: str = ""
    raw_responsibilities: str = ""
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "must_have": self.must_have,
            "nice_to_have": self.nice_to_have,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "min_years_experience": self.min_years_experience,
            "max_years_experience": self.max_years_experience,
            "seniority_level": self.seniority_level,
            "keywords": self.keywords,
            "responsibilities": self.responsibilities,
        }


# =============================================================================
# SECTION DETECTION
# =============================================================================

SECTION_PATTERNS = {
    "requirements": [
        r"(?i)^requirements?\s*:?$",
        r"(?i)^qualifications?\s*:?$",
        r"(?i)^what\s+we('re|\s+are)\s+looking\s+for\s*:?$",
        r"(?i)^who\s+you\s+are\s*:?$",
        r"(?i)^you\s+have\s*:?$",
        r"(?i)^must\s+have\s*:?$",
        r"(?i)^required\s+skills?\s*:?$",
        r"(?i)^minimum\s+qualifications?\s*:?$",
        r"(?i)^basic\s+qualifications?\s*:?$",
    ],
    "nice_to_have": [
        r"(?i)^nice\s+to\s+have\s*:?$",
        r"(?i)^preferred\s+qualifications?\s*:?$",
        r"(?i)^bonus\s+points?\s*:?$",
        r"(?i)^plus\s*:?$",
        r"(?i)^desired\s+skills?\s*:?$",
        r"(?i)^additional\s+qualifications?\s*:?$",
    ],
    "responsibilities": [
        r"(?i)^responsibilities?\s*:?$",
        r"(?i)^what\s+you('ll|\s+will)\s+do\s*:?$",
        r"(?i)^the\s+role\s*:?$",
        r"(?i)^about\s+the\s+role\s*:?$",
        r"(?i)^job\s+description\s*:?$",
        r"(?i)^duties\s*:?$",
        r"(?i)^key\s+responsibilities?\s*:?$",
        r"(?i)^your\s+impact\s*:?$",
    ],
    "about": [
        r"(?i)^about\s+(us|the\s+company|the\s+team)\s*:?$",
        r"(?i)^who\s+we\s+are\s*:?$",
        r"(?i)^company\s+description\s*:?$",
    ],
    "benefits": [
        r"(?i)^benefits?\s*:?$",
        r"(?i)^perks?\s*:?$",
        r"(?i)^what\s+we\s+offer\s*:?$",
        r"(?i)^compensation\s*:?$",
    ],
}


def detect_sections(text: str) -> dict[str, tuple[int, int]]:
    """
    Detect section boundaries in JD text.
    
    Returns:
        Dict mapping section type to (start_line, end_line) tuples
    """
    lines = text.split("\n")
    section_starts = []
    
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped or len(line_stripped) > 80:
            continue
        
        for section_type, patterns in SECTION_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, line_stripped):
                    section_starts.append((i, section_type))
                    break
            else:
                continue
            break
    
    # Build section ranges
    sections = {}
    for idx, (start_line, section_type) in enumerate(section_starts):
        if idx + 1 < len(section_starts):
            end_line = section_starts[idx + 1][0]
        else:
            end_line = len(lines)
        
        # Handle multiple sections of same type
        if section_type in sections:
            # Extend existing section
            existing_start, existing_end = sections[section_type]
            sections[section_type] = (existing_start, max(existing_end, end_line))
        else:
            sections[section_type] = (start_line + 1, end_line)  # Skip header line
    
    return sections


def extract_section_text(text: str, sections: dict, section_type: str) -> str:
    """Extract text for a specific section."""
    if section_type not in sections:
        return ""
    
    lines = text.split("\n")
    start, end = sections[section_type]
    return "\n".join(lines[start:end]).strip()


# =============================================================================
# SKILL EXTRACTION
# =============================================================================

TECH_SKILLS = {
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "perl",
    
    # Web frameworks
    "react", "reactjs", "react.js", "angular", "angularjs", "vue", "vuejs",
    "vue.js", "next.js", "nextjs", "nuxt", "svelte", "ember", "backbone",
    "node", "nodejs", "node.js", "express", "expressjs", "fastify", "nestjs",
    "django", "flask", "fastapi", "spring", "spring boot", "springboot",
    "rails", "ruby on rails", "laravel", "symfony", "asp.net", ".net",
    
    # Databases
    "sql", "mysql", "postgresql", "postgres", "mongodb", "redis", "elasticsearch",
    "cassandra", "dynamodb", "oracle", "sqlite", "mariadb", "couchdb", "neo4j",
    "graphql", "nosql", "firebase", "supabase",
    
    # Cloud & DevOps
    "aws", "amazon web services", "azure", "gcp", "google cloud", "cloud",
    "docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins", "ci/cd",
    "github actions", "gitlab ci", "circleci", "travis", "devops", "sre",
    "linux", "unix", "bash", "shell", "powershell",
    
    # Data & ML
    "machine learning", "ml", "deep learning", "dl", "artificial intelligence", "ai",
    "nlp", "natural language processing", "computer vision", "cv",
    "tensorflow", "pytorch", "keras", "scikit-learn", "sklearn", "pandas",
    "numpy", "scipy", "spark", "pyspark", "hadoop", "hive", "airflow",
    "data science", "data engineering", "data analysis", "analytics",
    "tableau", "power bi", "looker", "metabase",
    
    # Mobile
    "ios", "android", "react native", "flutter", "xamarin", "cordova",
    
    # Other
    "api", "rest", "restful", "microservices", "serverless", "lambda",
    "git", "github", "gitlab", "bitbucket", "svn",
    "agile", "scrum", "kanban", "jira", "confluence",
    "html", "css", "sass", "less", "tailwind", "bootstrap",
    "webpack", "vite", "babel", "npm", "yarn", "pnpm",
    "testing", "unit testing", "integration testing", "e2e", "selenium",
    "jest", "mocha", "pytest", "junit", "cypress", "playwright",
}

SOFT_SKILLS = {
    "leadership", "communication", "teamwork", "collaboration", "problem-solving",
    "analytical", "critical thinking", "creativity", "adaptability", "flexibility",
    "time management", "organization", "attention to detail", "detail-oriented",
    "project management", "stakeholder management", "cross-functional",
    "mentoring", "coaching", "presentation", "public speaking", "negotiation",
    "customer-facing", "client-facing", "interpersonal", "empathy",
}


def extract_skills(text: str) -> tuple[list[str], list[str]]:
    """
    Extract technical and soft skills from text.
    
    Returns:
        Tuple of (technical_skills, soft_skills)
    """
    text_lower = text.lower()
    
    tech = []
    soft = []
    
    for skill in TECH_SKILLS:
        # Match whole word
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            tech.append(skill.title() if len(skill) > 3 else skill.upper())
    
    for skill in SOFT_SKILLS:
        pattern = r"\b" + re.escape(skill) + r"\b"
        if re.search(pattern, text_lower):
            soft.append(skill.title())
    
    return list(dict.fromkeys(tech)), list(dict.fromkeys(soft))


# =============================================================================
# EXPERIENCE EXTRACTION
# =============================================================================

EXPERIENCE_PATTERNS = [
    r"(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)",
    r"(\d+)\s*-\s*(\d+)\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)",
    r"(?:minimum|at\s+least|min)\s+(\d+)\s*(?:years?|yrs?)",
    r"(\d+)\+?\s*(?:years?|yrs?)(?:\s+in|\s+with)",
]

SENIORITY_PATTERNS = {
    "entry": [r"entry[\s-]?level", r"junior", r"associate", r"graduate", r"new\s+grad", r"0-2\s+years?"],
    "mid": [r"mid[\s-]?level", r"intermediate", r"2-5\s+years?", r"3-5\s+years?"],
    "senior": [r"senior", r"sr\.?", r"5\+?\s+years?", r"5-8\s+years?", r"experienced"],
    "lead": [r"lead", r"principal", r"staff", r"architect", r"8\+?\s+years?", r"10\+?\s+years?"],
    "manager": [r"manager", r"director", r"head\s+of", r"vp", r"vice\s+president"],
}


def extract_experience_requirements(text: str) -> tuple[Optional[int], Optional[int], str]:
    """
    Extract experience requirements from text.
    
    Returns:
        Tuple of (min_years, max_years, seniority_level)
    """
    text_lower = text.lower()
    
    min_years = None
    max_years = None
    
    for pattern in EXPERIENCE_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            groups = match.groups()
            if len(groups) == 2 and groups[1]:
                min_years = int(groups[0])
                max_years = int(groups[1])
            elif groups[0]:
                min_years = int(groups[0])
            break
    
    # Detect seniority level
    seniority = ""
    for level, patterns in SENIORITY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                seniority = level
                break
        if seniority:
            break
    
    # Infer seniority from years if not detected
    if not seniority and min_years is not None:
        if min_years <= 2:
            seniority = "entry"
        elif min_years <= 5:
            seniority = "mid"
        elif min_years <= 8:
            seniority = "senior"
        else:
            seniority = "lead"
    
    return min_years, max_years, seniority


# =============================================================================
# KEYWORD EXTRACTION
# =============================================================================

def extract_keywords(text: str, tech_skills: list[str]) -> list[str]:
    """
    Extract important keywords for ATS matching.
    
    Only extracts technical/professional keywords relevant for resumes,
    not generic words or perks/benefits.
    
    Args:
        text: JD text
        tech_skills: Already extracted technical skills
        
    Returns:
        List of keywords sorted by importance
    """
    keywords = set()
    
    # Add technical skills (these are the most important)
    keywords.update(s.lower() for s in tech_skills)
    
    # Known technical/professional keywords to look for
    tech_keyword_patterns = [
        # Programming & frameworks
        r"\b(python|java|javascript|typescript|c\+\+|golang|rust|ruby|php|scala|kotlin|swift)\b",
        r"\b(react|angular|vue|node|django|flask|spring|rails|laravel|express)\b",
        r"\b(aws|azure|gcp|docker|kubernetes|terraform|jenkins|ci/cd|devops)\b",
        r"\b(sql|nosql|postgresql|mysql|mongodb|redis|elasticsearch|cassandra|dynamodb)\b",
        r"\b(machine learning|deep learning|nlp|computer vision|ai|ml|data science)\b",
        r"\b(tensorflow|pytorch|keras|scikit-learn|pandas|numpy|spark)\b",
        r"\b(rest|graphql|grpc|microservices|api|websocket)\b",
        r"\b(git|linux|unix|shell|bash|powershell)\b",
        r"\b(agile|scrum|kanban|jira|confluence)\b",
        # Domain-specific
        r"\b(fintech|healthcare|e-commerce|saas|b2b|b2c)\b",
        r"\b(distributed systems|system design|architecture|scalability)\b",
        r"\b(security|authentication|authorization|oauth|jwt)\b",
        r"\b(testing|tdd|bdd|unit testing|integration testing|qa)\b",
        r"\b(performance|optimization|caching|load balancing)\b",
    ]
    
    text_lower = text.lower()
    for pattern in tech_keyword_patterns:
        matches = re.findall(pattern, text_lower)
        keywords.update(matches)
    
    # Extract terms after "experience with/in" (usually technical)
    exp_pattern = r"experience\s+(?:with|in)\s+([A-Za-z0-9\s,/]+?)(?:\.|,|;|\n|$)"
    exp_matches = re.findall(exp_pattern, text_lower)
    for match in exp_matches:
        terms = re.split(r"[,/]", match)
        for term in terms:
            term = term.strip()
            if len(term) > 2 and len(term) < 30:
                # Only add if it looks technical (not generic words)
                if not _is_generic_word(term):
                    keywords.add(term)
    
    # Extract terms after "knowledge of" or "proficiency in"
    knowledge_pattern = r"(?:knowledge of|proficiency in|familiarity with|expertise in)\s+([A-Za-z0-9\s,/]+?)(?:\.|,|;|\n|$)"
    knowledge_matches = re.findall(knowledge_pattern, text_lower)
    for match in knowledge_matches:
        terms = re.split(r"[,/]", match)
        for term in terms:
            term = term.strip()
            if len(term) > 2 and len(term) < 30 and not _is_generic_word(term):
                keywords.add(term)
    
    # Remove any remaining generic words
    keywords = {k for k in keywords if not _is_generic_word(k) and len(k) > 1}
    
    # Split compound keywords like "python and java" into individual keywords
    final_keywords = set()
    for kw in keywords:
        if " and " in kw.lower() or " or " in kw.lower():
            # Split and add individual parts
            parts = re.split(r"\s+(?:and|or)\s+", kw, flags=re.IGNORECASE)
            for part in parts:
                part = part.strip()
                if len(part) > 1 and not _is_generic_word(part):
                    final_keywords.add(part)
        else:
            final_keywords.add(kw)
    
    return sorted(final_keywords)[:50]


def _is_generic_word(word: str) -> bool:
    """Check if a word is generic/non-technical and should be excluded."""
    generic_words = {
        # Common stop words
        "the", "and", "for", "with", "our", "you", "your", "will", "are", "this",
        "that", "have", "has", "can", "about", "work", "working", "team", "teams",
        "company", "role", "position", "job", "opportunity", "looking", "seeking",
        "ideal", "candidate", "candidates", "ability", "strong", "excellent",
        "good", "great", "best", "experience", "years", "year", "minimum",
        "required", "preferred", "must", "should", "would", "could", "may",
        # Perks/benefits (not resume-relevant)
        "salary", "bonus", "benefits", "insurance", "health", "dental", "vision",
        "vacation", "pto", "holiday", "holidays", "remote", "hybrid", "office",
        "flexible", "flexibility", "culture", "environment", "growth", "career",
        "breakfast", "lunch", "dinner", "snacks", "food", "meals", "free",
        "cab", "transport", "transportation", "commute", "parking",
        "gym", "fitness", "wellness", "mental", "stipend", "allowance",
        "stock", "equity", "options", "vesting", "401k", "retirement",
        # Generic adjectives
        "additional", "brilliant", "amazing", "awesome", "fantastic", "exciting",
        "dynamic", "innovative", "cutting-edge", "world-class", "leading",
        "fast-paced", "collaborative", "inclusive", "diverse", "passionate",
        # Location/company words
        "new york", "san francisco", "london", "bangalore", "hyderabad",
        "headquarters", "campus", "building", "floor", "tower",
        # Generic verbs/nouns
        "build", "create", "develop", "design", "implement", "maintain",
        "support", "help", "assist", "contribute", "collaborate", "communicate",
        "manage", "lead", "drive", "deliver", "ensure", "provide",
        "solutions", "products", "services", "customers", "clients", "users",
        "business", "industry", "market", "sector",
        # Other non-technical
        "knowledge", "skills", "qualifications", "requirements", "responsibilities",
        "duties", "tasks", "projects", "initiatives", "goals", "objectives",
    }
    
    word_lower = word.lower().strip()
    
    # Check exact match
    if word_lower in generic_words:
        return True
    
    # Check if any generic word is contained (for multi-word phrases)
    for gw in generic_words:
        if gw in word_lower and len(word_lower) < len(gw) + 5:
            return True
    
    return False


# =============================================================================
# BULLET EXTRACTION
# =============================================================================

def extract_bullets(text: str) -> list[str]:
    """Extract bullet points from text."""
    bullets = []
    
    for line in text.split("\n"):
        line = line.strip()
        
        # Check for bullet markers
        if re.match(r"^[•\-*–›▪◦]\s+", line) or re.match(r"^\d+\.\s+", line):
            bullet = re.sub(r"^[•\-*–›▪◦\d.]+\s*", "", line)
            if len(bullet) > 15:
                bullets.append(bullet)
        # Check for lines that look like requirements
        elif line and len(line) > 20 and len(line) < 300:
            if any(line.lower().startswith(kw) for kw in ["must", "should", "ability", "experience", "knowledge", "proficiency", "familiarity", "understanding"]):
                bullets.append(line)
    
    return bullets


# =============================================================================
# MAIN ANALYZER
# =============================================================================

def analyze_job_description(jd_text: str, use_llm: bool = True) -> JDAnalysis:
    """
    Analyze a job description and extract structured data.
    
    Args:
        jd_text: Raw job description text
        use_llm: Whether to use LLM for keyword classification (default: True)
        
    Returns:
        JDAnalysis with extracted data
    """
    analysis = JDAnalysis()
    
    if not jd_text or len(jd_text.strip()) < 50:
        return analysis
    
    # Detect sections
    sections = detect_sections(jd_text)
    
    # Extract requirements
    req_text = extract_section_text(jd_text, sections, "requirements")
    analysis.raw_requirements = req_text
    
    if req_text:
        analysis.must_have = extract_bullets(req_text)[:15]
    else:
        # Try to find requirements in full text
        analysis.must_have = extract_bullets(jd_text)[:10]
    
    # Extract nice-to-have
    nice_text = extract_section_text(jd_text, sections, "nice_to_have")
    if nice_text:
        analysis.nice_to_have = extract_bullets(nice_text)[:10]
    
    # Extract responsibilities
    resp_text = extract_section_text(jd_text, sections, "responsibilities")
    analysis.raw_responsibilities = resp_text
    
    if resp_text:
        analysis.responsibilities = extract_bullets(resp_text)[:15]
    
    # Extract skills
    tech_skills, soft_skills = extract_skills(jd_text)
    analysis.required_skills = tech_skills[:25]
    analysis.preferred_skills = soft_skills[:15]
    
    # Extract experience requirements
    min_years, max_years, seniority = extract_experience_requirements(jd_text)
    analysis.min_years_experience = min_years
    analysis.max_years_experience = max_years
    analysis.seniority_level = seniority
    
    # Extract keywords (heuristic first)
    heuristic_keywords = extract_keywords(jd_text, tech_skills)
    
    # Use LLM to filter/classify technical keywords if available
    if use_llm and heuristic_keywords:
        llm_keywords = _llm_filter_keywords(heuristic_keywords, jd_text)
        if llm_keywords is not None:
            analysis.keywords = llm_keywords
            logger.info(f"LLM filtered keywords: {len(heuristic_keywords)} -> {len(llm_keywords)}")
        else:
            analysis.keywords = heuristic_keywords
    else:
        analysis.keywords = heuristic_keywords
    
    # Try to extract title (usually in first few lines)
    lines = jd_text.strip().split("\n")[:10]
    for line in lines:
        line = line.strip()
        if len(line) > 5 and len(line) < 80:
            # Check if it looks like a job title
            title_keywords = ["engineer", "developer", "manager", "analyst", "designer", "scientist", "architect", "lead", "director", "specialist", "coordinator", "associate", "intern"]
            if any(kw in line.lower() for kw in title_keywords):
                analysis.title = line
                break
    
    return analysis


def _llm_filter_keywords(keywords: list[str], jd_text: str) -> Optional[list[str]]:
    """
    Use LLM to filter keywords to only technical/professional ones.
    
    Args:
        keywords: List of extracted keywords
        jd_text: Original JD text for context
        
    Returns:
        Filtered list of technical keywords, or None if LLM unavailable
    """
    try:
        from core.clients.groq_client import llm_classify_technical_keywords, is_groq_available
        
        if not is_groq_available():
            return None
        
        return llm_classify_technical_keywords(keywords, jd_text)
    except ImportError:
        logger.debug("groq_client not available for keyword filtering")
        return None
    except Exception as e:
        logger.warning(f"LLM keyword filtering failed: {e}")
        return None


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    import json
    
    sample_jd = """
    Senior Software Engineer - Backend
    
    About the Role:
    We're looking for a Senior Software Engineer to join our backend team.
    
    Responsibilities:
    • Design and implement scalable backend services
    • Lead technical discussions and code reviews
    • Mentor junior engineers
    • Collaborate with product and design teams
    
    Requirements:
    • 5+ years of experience in software development
    • Strong proficiency in Python or Go
    • Experience with PostgreSQL and Redis
    • Knowledge of AWS services (EC2, S3, Lambda)
    • Experience with Docker and Kubernetes
    
    Nice to Have:
    • Experience with machine learning systems
    • Contributions to open source projects
    • Experience with GraphQL
    
    Benefits:
    • Competitive salary
    • Remote work options
    • Health insurance
    """
    
    analysis = analyze_job_description(sample_jd)
    print(json.dumps(analysis.to_dict(), indent=2))
