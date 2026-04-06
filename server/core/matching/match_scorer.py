"""
Resume-JD matching scorer for JobLens AI.

Computes fit scores, credibility scores, and generates suggestions
using embeddings and heuristics with optional LLM assistance.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Configuration
EMBEDDING_MODEL = "all-mpnet-base-v2"
EMBEDDING_CACHE_SIZE = 1000

# Technical keywords that are valid for ATS suggestions
TECHNICAL_KEYWORD_PATTERNS = {
    # Programming languages
    "python", "java", "javascript", "typescript", "c++", "c#", "golang", "go",
    "rust", "ruby", "php", "scala", "kotlin", "swift", "objective-c", "perl",
    "r", "matlab", "julia", "haskell", "erlang", "elixir", "clojure", "lua",
    # Frontend
    "react", "angular", "vue", "svelte", "nextjs", "nuxt", "gatsby", "redux",
    "webpack", "vite", "babel", "tailwind", "bootstrap", "sass", "less", "css",
    "html", "dom", "jquery", "typescript",
    # Backend
    "node", "nodejs", "express", "django", "flask", "fastapi", "spring",
    "springboot", "rails", "laravel", "asp.net", ".net", "gin", "fiber",
    "nestjs", "koa", "hapi",
    # Cloud & DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "k8s", "terraform",
    "ansible", "jenkins", "circleci", "github actions", "gitlab", "ci/cd",
    "devops", "sre", "cloudformation", "helm", "istio", "prometheus",
    "grafana", "datadog", "splunk", "elk", "nginx", "apache",
    # Databases
    "sql", "mysql", "postgresql", "postgres", "mongodb", "redis", "cassandra",
    "dynamodb", "elasticsearch", "neo4j", "couchdb", "firebase", "supabase",
    "oracle", "mssql", "sqlite", "nosql", "graphql",
    # Data & ML
    "machine learning", "deep learning", "nlp", "computer vision", "ai", "ml",
    "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
    "spark", "hadoop", "kafka", "airflow", "databricks", "snowflake",
    "tableau", "powerbi", "looker", "dbt", "etl", "data pipeline",
    # Architecture & Concepts
    "microservices", "rest", "api", "grpc", "websocket", "graphql",
    "distributed systems", "system design", "scalability", "high availability",
    "load balancing", "caching", "message queue", "rabbitmq", "sqs", "pubsub",
    # Security
    "security", "oauth", "jwt", "authentication", "authorization", "ssl",
    "encryption", "penetration testing", "soc2", "gdpr", "compliance",
    # Testing
    "testing", "tdd", "bdd", "unit testing", "integration testing", "e2e",
    "selenium", "cypress", "jest", "pytest", "junit", "mocha", "qa",
    # Mobile
    "ios", "android", "react native", "flutter", "swiftui", "uikit",
    "kotlin", "xamarin", "mobile development",
    # Tools
    "git", "linux", "unix", "shell", "bash", "vim", "vscode", "intellij",
    "jira", "confluence", "slack", "figma", "postman", "swagger",
    # Methodologies
    "agile", "scrum", "kanban", "lean", "waterfall",
}


def _is_technical_keyword(keyword: str) -> bool:
    """
    Check if a keyword is technical/professional and suitable for ATS suggestions.
    
    Args:
        keyword: The keyword to check
        
    Returns:
        True if the keyword is technical/relevant for resumes
    """
    kw_lower = keyword.lower().strip()
    
    # Check exact match
    if kw_lower in TECHNICAL_KEYWORD_PATTERNS:
        return True
    
    # Check if keyword contains any technical term
    for tech in TECHNICAL_KEYWORD_PATTERNS:
        if tech in kw_lower or kw_lower in tech:
            return True
    
    # Check for common technical patterns
    tech_patterns = [
        r"^[a-z]+\.js$",  # *.js frameworks
        r"^[a-z]+sql$",   # *sql databases
        r"^[a-z]+-[a-z]+$",  # hyphenated tech terms
        r"^[a-z]+db$",    # *db databases
    ]
    
    for pattern in tech_patterns:
        if re.match(pattern, kw_lower):
            return True
    
    return False


def _is_keyword_present(keyword: str, resume_text_lower: str, resume_skill_set: set) -> bool:
    """
    Check if a keyword is present in the resume (text or skills).
    
    Args:
        keyword: The keyword to check (lowercase)
        resume_text_lower: Lowercase resume text
        resume_skill_set: Set of lowercase skills from resume schema
        
    Returns:
        True if keyword is found in resume
    """
    kw = keyword.lower().strip()
    
    # Direct match in skills set
    if kw in resume_skill_set:
        return True
    
    # Check for variations in skill set (e.g., "react.js" vs "react")
    kw_base = re.sub(r"\.js$", "", kw)  # Remove .js suffix
    kw_base = re.sub(r"js$", "", kw_base)  # Remove js suffix
    for skill in resume_skill_set:
        skill_base = re.sub(r"\.js$", "", skill)
        skill_base = re.sub(r"js$", "", skill_base)
        if kw_base == skill_base or kw == skill_base or kw_base == skill:
            return True
    
    # Word boundary search in resume text
    # This ensures "java" matches "Java" but not "javascript"
    if re.search(r"\b" + re.escape(kw) + r"\b", resume_text_lower):
        return True
    
    # Check common variations
    variations = [
        kw,
        kw.replace("-", " "),  # ci-cd -> ci cd
        kw.replace(" ", "-"),  # ci cd -> ci-cd
        kw.replace(".", ""),   # node.js -> nodejs
        kw + ".js",            # react -> react.js
        kw.replace(".js", ""), # react.js -> react
    ]
    
    for var in variations:
        if var in resume_skill_set:
            return True
        if re.search(r"\b" + re.escape(var) + r"\b", resume_text_lower):
            return True
    
    return False


# =============================================================================
# EMBEDDING CACHE & MODEL
# =============================================================================

_embedding_model = None
_embedding_cache: dict[str, np.ndarray] = {}


def get_embedding_model():
    """Get or load the sentence transformer model."""
    global _embedding_model
    
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("Embedding model loaded")
        except ImportError:
            raise ImportError("sentence-transformers not installed. Run: pip install sentence-transformers")
    
    return _embedding_model


def get_embeddings(texts: list[str], use_cache: bool = True) -> np.ndarray:
    """
    Get embeddings for texts with caching.
    
    Args:
        texts: List of texts to embed
        use_cache: Whether to use embedding cache
        
    Returns:
        Numpy array of embeddings (N x dim)
    """
    global _embedding_cache
    
    model = get_embedding_model()
    
    if not use_cache:
        return model.encode(texts, convert_to_numpy=True)
    
    # Check cache
    embeddings = []
    texts_to_encode = []
    indices_to_encode = []
    
    for i, text in enumerate(texts):
        cache_key = text[:500]  # Truncate for cache key
        if cache_key in _embedding_cache:
            embeddings.append((i, _embedding_cache[cache_key]))
        else:
            texts_to_encode.append(text)
            indices_to_encode.append(i)
    
    # Encode missing texts
    if texts_to_encode:
        new_embeddings = model.encode(texts_to_encode, convert_to_numpy=True)
        
        for idx, text, emb in zip(indices_to_encode, texts_to_encode, new_embeddings):
            cache_key = text[:500]
            _embedding_cache[cache_key] = emb
            embeddings.append((idx, emb))
            
            # Limit cache size
            if len(_embedding_cache) > EMBEDDING_CACHE_SIZE:
                # Remove oldest entries
                keys = list(_embedding_cache.keys())
                for k in keys[:100]:
                    del _embedding_cache[k]
    
    # Sort by original index and return
    embeddings.sort(key=lambda x: x[0])
    return np.array([e[1] for e in embeddings])


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def batch_cosine_similarity(query: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between query and corpus vectors."""
    query_norm = query / (np.linalg.norm(query) + 1e-8)
    corpus_norms = corpus / (np.linalg.norm(corpus, axis=1, keepdims=True) + 1e-8)
    return np.dot(corpus_norms, query_norm)


# =============================================================================
# FIT SCORE COMPONENTS
# =============================================================================

@dataclass
class FitScore:
    """Resume-JD fit score breakdown."""
    overall: int = 0
    components: dict = field(default_factory=lambda: {
        "skill_match": 0,
        "experience_match": 0,
        "ats_keyword_match": 0,
        "role_alignment": 0,
    })
    must_have_gaps: list[str] = field(default_factory=list)
    evidence_map: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "components": self.components,
            "must_have_gaps": self.must_have_gaps,
            "evidence_map": self.evidence_map,
        }


def compute_skill_match(
    resume_skills: dict,
    jd_required_skills: list[str],
    jd_preferred_skills: list[str],
) -> tuple[int, list[str], dict]:
    """
    Compute skill match score (0-35).
    
    Returns:
        Tuple of (score, gaps, evidence_map)
    """
    score = 0
    gaps = []
    evidence = {}
    
    # Flatten resume skills
    resume_skill_set = set()
    for category in ["technical", "tools", "soft"]:
        skills = resume_skills.get(category, [])
        resume_skill_set.update(s.lower() for s in skills)
    
    # Check required skills
    required_matches = 0
    for skill in jd_required_skills:
        skill_lower = skill.lower()
        if skill_lower in resume_skill_set:
            required_matches += 1
            evidence[skill] = [f"Found in resume skills: {skill}"]
        else:
            # Check for partial/semantic match
            matched = False
            for rs in resume_skill_set:
                if skill_lower in rs or rs in skill_lower:
                    required_matches += 0.5
                    evidence[skill] = [f"Partial match: {rs}"]
                    matched = True
                    break
            if not matched:
                gaps.append(skill)
    
    # Score for required skills (0-25)
    if jd_required_skills:
        required_ratio = required_matches / len(jd_required_skills)
        score += int(required_ratio * 25)
    else:
        score += 15  # No requirements = assume decent match
    
    # Check preferred skills (0-10)
    preferred_matches = 0
    for skill in jd_preferred_skills:
        skill_lower = skill.lower()
        if skill_lower in resume_skill_set:
            preferred_matches += 1
            if skill not in evidence:
                evidence[skill] = [f"Found in resume skills: {skill}"]
    
    if jd_preferred_skills:
        preferred_ratio = preferred_matches / len(jd_preferred_skills)
        score += int(preferred_ratio * 10)
    else:
        score += 5
    
    return min(35, score), gaps[:10], evidence


def compute_experience_match(
    resume_experience: list[dict],
    jd_min_years: Optional[int],
    jd_max_years: Optional[int],
    jd_seniority: str,
) -> tuple[int, dict]:
    """
    Compute experience match score (0-30).
    
    Returns:
        Tuple of (score, evidence_map)
    """
    score = 0
    evidence = {}
    
    # Estimate years of experience from resume
    total_years = 0
    for exp in resume_experience:
        start = exp.get("start", "")
        end = exp.get("end", "")
        
        # Try to parse years
        start_year = None
        end_year = None
        
        if start:
            year_match = re.search(r"20\d{2}|19\d{2}", start)
            if year_match:
                start_year = int(year_match.group())
        
        if end:
            if any(kw in end.lower() for kw in ["present", "current", "now", "ongoing"]):
                end_year = 2024
            else:
                year_match = re.search(r"20\d{2}|19\d{2}", end)
                if year_match:
                    end_year = int(year_match.group())
        
        if start_year and end_year:
            total_years += max(0, end_year - start_year)
        elif start_year:
            total_years += 2  # Assume 2 years if end date missing
    
    evidence["estimated_years"] = [f"Estimated {total_years} years from {len(resume_experience)} positions"]
    
    # Score based on years match (0-15)
    if jd_min_years is not None:
        if total_years >= jd_min_years:
            score += 15
        elif total_years >= jd_min_years - 1:
            score += 10
        elif total_years >= jd_min_years - 2:
            score += 5
        else:
            score += 2
    else:
        score += 10  # No requirement = assume match
    
    # Score based on seniority alignment (0-10)
    seniority_scores = {
        "entry": (0, 2),
        "mid": (2, 5),
        "senior": (5, 10),
        "lead": (8, 15),
        "manager": (10, 20),
    }
    
    if jd_seniority and jd_seniority in seniority_scores:
        min_exp, max_exp = seniority_scores[jd_seniority]
        if min_exp <= total_years <= max_exp + 3:
            score += 10
        elif total_years >= min_exp:
            score += 7
        else:
            score += 3
    else:
        score += 7
    
    # Bonus for number of relevant positions (0-5)
    if len(resume_experience) >= 3:
        score += 5
    elif len(resume_experience) >= 2:
        score += 3
    elif len(resume_experience) >= 1:
        score += 2
    
    return min(30, score), evidence


def compute_ats_keyword_match(
    resume_text: str,
    jd_keywords: list[str],
    jd_must_have: list[str],
) -> tuple[int, list[str], dict]:
    """
    Compute ATS keyword match score (0-20).
    
    Returns:
        Tuple of (score, gaps, evidence_map)
    """
    score = 0
    gaps = []
    evidence = {}
    
    resume_lower = resume_text.lower()
    
    # Check keywords (0-12)
    keyword_matches = 0
    for kw in jd_keywords:
        kw_lower = kw.lower()
        if kw_lower in resume_lower:
            keyword_matches += 1
            evidence[kw] = ["Found in resume text"]
    
    if jd_keywords:
        keyword_ratio = keyword_matches / len(jd_keywords)
        score += int(keyword_ratio * 12)
    else:
        score += 8
    
    # Check must-have requirements (0-8)
    must_have_matches = 0
    for req in jd_must_have:
        req_lower = req.lower()
        # Extract key terms from requirement
        terms = re.findall(r"\b[a-z]{4,}\b", req_lower)
        matches = sum(1 for t in terms if t in resume_lower)
        
        if terms and matches / len(terms) >= 0.5:
            must_have_matches += 1
            evidence[req[:50]] = [f"Matched {matches}/{len(terms)} key terms"]
        else:
            # Extract specific skill/technology names from the requirement
            # instead of storing the full sentence
            skill_gaps = _extract_skills_from_requirement(req, resume_lower)
            for skill in skill_gaps:
                if skill not in gaps:
                    gaps.append(skill)
    
    if jd_must_have:
        must_have_ratio = must_have_matches / len(jd_must_have)
        score += int(must_have_ratio * 8)
    else:
        score += 5
    
    return min(20, score), gaps[:8], evidence


def _extract_skills_from_requirement(requirement: str, resume_lower: str) -> list[str]:
    """
    Extract specific skill/technology names from a requirement sentence,
    filtering out skills already in the resume.
    
    Args:
        requirement: Full requirement sentence like "Experience with Docker and Kubernetes"
        resume_lower: Lowercase resume text for checking existing skills
        
    Returns:
        List of extracted skill names that are missing from resume
    """
    req_lower = requirement.lower()
    found_skills = []
    found_normalized = set()  # Track normalized versions to avoid duplicates
    
    # Known technical terms to look for (canonical name -> variations)
    tech_terms = {
        "Kubernetes": ["kubernetes", "k8s"],
        "Docker": ["docker"],
        "PostgreSQL": ["postgresql", "postgres"],
        "MongoDB": ["mongodb", "mongo"],
        "MySQL": ["mysql"],
        "Elasticsearch": ["elasticsearch", "elastic"],
        "Redis": ["redis"],
        "Kafka": ["kafka"],
        "AWS": ["aws", "amazon web services"],
        "Azure": ["azure"],
        "GCP": ["gcp", "google cloud"],
        "Linux": ["linux"],
        "Shell": ["shell", "bash", "shell scripting"],
        "Python": ["python"],
        "Java": ["java"],
        "JavaScript": ["javascript", "js"],
        "TypeScript": ["typescript", "ts"],
        "React": ["react", "reactjs", "react.js"],
        "Angular": ["angular"],
        "Vue": ["vue", "vuejs", "vue.js"],
        "Node.js": ["node", "nodejs", "node.js"],
        "Django": ["django"],
        "Flask": ["flask"],
        "Spring": ["spring", "springboot", "spring boot"],
        "GraphQL": ["graphql"],
        "REST API": ["rest", "restful", "rest api"],
        "Microservices": ["microservices", "micro-services"],
        "CI/CD": ["ci/cd", "cicd", "continuous integration"],
        "Jenkins": ["jenkins"],
        "Terraform": ["terraform"],
        "Ansible": ["ansible"],
        "Git": ["git"],
        "Agile": ["agile"],
        "Scrum": ["scrum"],
        "NoSQL": ["nosql"],
        "SQL": ["sql"],
        "Swift": ["swift"],
        "Kotlin": ["kotlin"],
        "Go": ["golang"],  # Only match "golang", not "go" (too common)
        "Rust": ["rust"],
        "Ruby": ["ruby"],
        "Scala": ["scala"],
        "Hadoop": ["hadoop"],
        "Spark": ["spark", "apache spark"],
    }
    
    for canonical, variations in tech_terms.items():
        for var in variations:
            # Use word boundary to avoid partial matches
            if re.search(r"\b" + re.escape(var) + r"\b", req_lower):
                # Check if this skill is missing from resume
                is_in_resume = any(
                    re.search(r"\b" + re.escape(v) + r"\b", resume_lower)
                    for v in variations
                )
                
                if not is_in_resume:
                    normalized = canonical.lower()
                    if normalized not in found_normalized:
                        found_skills.append(canonical)
                        found_normalized.add(normalized)
                break  # Found a match for this skill, move to next
    
    return found_skills


def compute_role_alignment(
    resume_bullets: list[str],
    jd_responsibilities: list[str],
) -> tuple[int, dict]:
    """
    Compute role alignment score using embeddings (0-15).
    
    Returns:
        Tuple of (score, evidence_map)
    """
    evidence = {}
    
    if not resume_bullets or not jd_responsibilities:
        return 8, evidence  # Default score if no data
    
    try:
        # Get embeddings
        t0 = time.time()
        resume_embs = get_embeddings(resume_bullets[:20])
        jd_embs = get_embeddings(jd_responsibilities[:15])
        
        # Compute average similarity
        similarities = []
        for i, jd_emb in enumerate(jd_embs):
            sims = batch_cosine_similarity(jd_emb, resume_embs)
            max_sim = float(np.max(sims))
            max_idx = int(np.argmax(sims))
            similarities.append(max_sim)
            
            if max_sim > 0.5:
                resp_preview = jd_responsibilities[i][:50]
                bullet_preview = resume_bullets[max_idx][:50]
                evidence[resp_preview] = [f"Matched: {bullet_preview}... (sim={max_sim:.2f})"]
        
        avg_similarity = np.mean(similarities) if similarities else 0.5
        
        # Convert to score (0-15)
        # Similarity 0.3-0.8 maps to score 0-15
        normalized = (avg_similarity - 0.3) / 0.5
        score = int(max(0, min(1, normalized)) * 15)
        
        evidence["_avg_similarity"] = [f"Average semantic similarity: {avg_similarity:.3f}"]
        
        return score, evidence
        
    except Exception as e:
        logger.warning(f"Role alignment computation failed: {e}")
        return 8, {"error": [str(e)]}


def compute_fit_score(
    resume_schema: dict,
    resume_text: str,
    jd_analysis: dict,
) -> FitScore:
    """
    Compute overall fit score between resume and JD.
    
    Args:
        resume_schema: Parsed resume schema
        resume_text: Raw resume text
        jd_analysis: Analyzed JD data
        
    Returns:
        FitScore with breakdown
    """
    fit = FitScore()
    all_evidence = {}
    all_gaps = []
    
    # Skill match (0-35)
    skill_score, skill_gaps, skill_evidence = compute_skill_match(
        resume_schema.get("skills", {}),
        jd_analysis.get("required_skills", []),
        jd_analysis.get("preferred_skills", []),
    )
    fit.components["skill_match"] = skill_score
    all_gaps.extend(skill_gaps)
    all_evidence.update(skill_evidence)
    
    # Experience match (0-30)
    exp_score, exp_evidence = compute_experience_match(
        resume_schema.get("experience", []),
        jd_analysis.get("min_years_experience"),
        jd_analysis.get("max_years_experience"),
        jd_analysis.get("seniority_level", ""),
    )
    fit.components["experience_match"] = exp_score
    all_evidence.update(exp_evidence)
    
    # ATS keyword match (0-20)
    ats_score, ats_gaps, ats_evidence = compute_ats_keyword_match(
        resume_text,
        jd_analysis.get("keywords", []),
        jd_analysis.get("must_have", []),
    )
    fit.components["ats_keyword_match"] = ats_score
    all_gaps.extend(ats_gaps)
    all_evidence.update(ats_evidence)
    
    # Role alignment (0-15)
    resume_bullets = []
    for exp in resume_schema.get("experience", []):
        resume_bullets.extend(exp.get("bullets", []))
    for proj in resume_schema.get("projects", []):
        resume_bullets.extend(proj.get("bullets", []))
    
    role_score, role_evidence = compute_role_alignment(
        resume_bullets,
        jd_analysis.get("responsibilities", []),
    )
    fit.components["role_alignment"] = role_score
    all_evidence.update(role_evidence)
    
    # Compute overall
    fit.overall = sum(fit.components.values())
    fit.must_have_gaps = list(dict.fromkeys(all_gaps))[:15]
    fit.evidence_map = all_evidence
    
    return fit


# =============================================================================
# CREDIBILITY SCORE
# =============================================================================

@dataclass
class CredibilityScore:
    """Resume credibility score breakdown."""
    overall: int = 0
    signals: dict = field(default_factory=lambda: {
        "specificity": 0,
        "consistency": 0,
        "verifiability": 0,
        "clarity": 0,
    })
    boosters: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "signals": self.signals,
            "boosters": self.boosters,
            "flags": self.flags,
        }


def compute_specificity(resume_schema: dict, resume_text: str) -> tuple[int, list[str], list[str]]:
    """
    Compute specificity score (0-25).
    
    Looks for: quantified impacts, named technologies, concrete scope.
    """
    score = 0
    boosters = []
    flags = []
    
    # Check for metrics in bullets
    metrics_count = 0
    for exp in resume_schema.get("experience", []):
        for bullet in exp.get("bullets", []):
            if re.search(r"\d+%|\$[\d,]+|\d+x|\d+\+", bullet):
                metrics_count += 1
        metrics_count += len(exp.get("impact_metrics", []))
    
    if metrics_count >= 5:
        score += 12
        boosters.append(f"Strong quantification: {metrics_count} metrics found")
    elif metrics_count >= 3:
        score += 8
        boosters.append(f"Good quantification: {metrics_count} metrics found")
    elif metrics_count >= 1:
        score += 4
    else:
        flags.append("No quantified achievements found")
    
    # Check for named technologies
    tech_count = len(resume_schema.get("skills", {}).get("technical", []))
    if tech_count >= 10:
        score += 8
        boosters.append(f"Rich technical detail: {tech_count} technologies")
    elif tech_count >= 5:
        score += 5
    elif tech_count >= 2:
        score += 2
    else:
        flags.append("Few specific technologies mentioned")
    
    # Check for concrete company/project names
    companies = [exp.get("company", "") for exp in resume_schema.get("experience", [])]
    named_companies = sum(1 for c in companies if c and len(c) > 2)
    
    if named_companies >= 2:
        score += 5
    elif named_companies >= 1:
        score += 3
    else:
        flags.append("Company names not clearly specified")
    
    return min(25, score), boosters, flags


def compute_consistency(resume_schema: dict) -> tuple[int, list[str], list[str]]:
    """
    Compute consistency score (0-25).
    
    Looks for: date overlaps, implausible sequences, contradictions.
    """
    score = 20  # Start high, deduct for issues
    boosters = []
    flags = []
    
    experience = resume_schema.get("experience", [])
    
    # Check for date overlaps or gaps
    dates = []
    for exp in experience:
        start = exp.get("start", "")
        end = exp.get("end", "")
        
        start_year = None
        end_year = None
        
        if start:
            match = re.search(r"(20\d{2}|19\d{2})", start)
            if match:
                start_year = int(match.group())
        
        if end:
            if any(kw in end.lower() for kw in ["present", "current", "now"]):
                end_year = 2024
            else:
                match = re.search(r"(20\d{2}|19\d{2})", end)
                if match:
                    end_year = int(match.group())
        
        if start_year and end_year:
            dates.append((start_year, end_year, exp.get("company", "Unknown")))
    
    # Check for overlaps
    dates.sort(key=lambda x: x[0])
    for i in range(len(dates) - 1):
        if dates[i][1] > dates[i + 1][0] + 1:  # Allow 1 year overlap
            flags.append(f"Possible date overlap: {dates[i][2]} and {dates[i+1][2]}")
            score -= 5
    
    # Check for implausible tenure
    for start, end, company in dates:
        tenure = end - start
        if tenure > 15:
            flags.append(f"Unusually long tenure at {company}: {tenure} years")
            score -= 3
        elif tenure < 0:
            flags.append(f"Invalid date range at {company}")
            score -= 5
    
    # Check for too many short stints
    short_stints = sum(1 for s, e, _ in dates if e - s < 1)
    if short_stints > 3:
        flags.append(f"Multiple very short positions ({short_stints})")
        score -= 3
    
    if not flags:
        boosters.append("Consistent timeline with no apparent gaps")
        score += 5
    
    return max(0, min(25, score)), boosters, flags


def compute_verifiability(resume_schema: dict) -> tuple[int, list[str], list[str]]:
    """
    Compute verifiability score (0-25).
    
    Looks for: portfolio/github/linkedin links, publications.
    """
    score = 0
    boosters = []
    flags = []
    
    links = resume_schema.get("basics", {}).get("links", [])
    
    # Check for LinkedIn
    has_linkedin = any("linkedin" in link.lower() for link in links)
    if has_linkedin:
        score += 8
        boosters.append("LinkedIn profile provided")
    
    # Check for GitHub/GitLab
    has_github = any(site in link.lower() for link in links for site in ["github", "gitlab", "bitbucket"])
    if has_github:
        score += 10
        boosters.append("Code repository profile provided")
    
    # Check for portfolio/personal site
    has_portfolio = any(
        not any(site in link.lower() for site in ["linkedin", "github", "gitlab", "bitbucket", "twitter", "facebook"])
        for link in links
    )
    if has_portfolio and len(links) > 2:
        score += 5
        boosters.append("Portfolio or personal website provided")
    
    # Check for certifications
    certs = resume_schema.get("certifications", [])
    if certs:
        score += 2
        boosters.append(f"{len(certs)} certifications listed")
    
    if not links:
        flags.append("No professional links provided (LinkedIn, GitHub, etc.)")
    
    if score < 10:
        flags.append("Limited verifiable online presence")
    
    return min(25, score), boosters, flags


def compute_clarity(resume_schema: dict, resume_text: str) -> tuple[int, list[str], list[str]]:
    """
    Compute clarity score (0-25).
    
    Looks for: bullet structure, action verbs, low vagueness.
    """
    score = 0
    boosters = []
    flags = []
    
    # Check bullet structure
    all_bullets = []
    for exp in resume_schema.get("experience", []):
        all_bullets.extend(exp.get("bullets", []))
    for proj in resume_schema.get("projects", []):
        all_bullets.extend(proj.get("bullets", []))
    
    if len(all_bullets) >= 10:
        score += 8
        boosters.append(f"Well-structured with {len(all_bullets)} bullet points")
    elif len(all_bullets) >= 5:
        score += 5
    elif len(all_bullets) >= 2:
        score += 2
    else:
        flags.append("Few structured bullet points")
    
    # Check for action verbs
    action_verbs = [
        "led", "developed", "implemented", "designed", "built", "created",
        "managed", "improved", "increased", "reduced", "achieved", "delivered",
        "launched", "optimized", "automated", "streamlined", "collaborated",
        "mentored", "architected", "engineered", "analyzed", "resolved",
    ]
    
    action_count = 0
    for bullet in all_bullets:
        bullet_lower = bullet.lower()
        if any(bullet_lower.startswith(verb) or f" {verb} " in bullet_lower for verb in action_verbs):
            action_count += 1
    
    if all_bullets:
        action_ratio = action_count / len(all_bullets)
        if action_ratio >= 0.7:
            score += 10
            boosters.append("Strong use of action verbs")
        elif action_ratio >= 0.4:
            score += 6
        elif action_ratio >= 0.2:
            score += 3
        else:
            flags.append("Weak action verbs in bullet points")
    
    # Check for vague language
    vague_terms = ["various", "several", "many", "some", "stuff", "things", "etc", "helped with", "worked on", "responsible for"]
    vague_count = sum(1 for term in vague_terms if term in resume_text.lower())
    
    if vague_count == 0:
        score += 7
        boosters.append("Clear, specific language throughout")
    elif vague_count <= 2:
        score += 4
    else:
        flags.append(f"Vague language detected ({vague_count} instances)")
    
    return min(25, score), boosters, flags


def compute_credibility_score(resume_schema: dict, resume_text: str) -> CredibilityScore:
    """
    Compute overall credibility score for resume.
    
    Args:
        resume_schema: Parsed resume schema
        resume_text: Raw resume text
        
    Returns:
        CredibilityScore with breakdown
    """
    cred = CredibilityScore()
    all_boosters = []
    all_flags = []
    
    # Specificity (0-25)
    spec_score, spec_boosters, spec_flags = compute_specificity(resume_schema, resume_text)
    cred.signals["specificity"] = spec_score
    all_boosters.extend(spec_boosters)
    all_flags.extend(spec_flags)
    
    # Consistency (0-25)
    cons_score, cons_boosters, cons_flags = compute_consistency(resume_schema)
    cred.signals["consistency"] = cons_score
    all_boosters.extend(cons_boosters)
    all_flags.extend(cons_flags)
    
    # Verifiability (0-25)
    ver_score, ver_boosters, ver_flags = compute_verifiability(resume_schema)
    cred.signals["verifiability"] = ver_score
    all_boosters.extend(ver_boosters)
    all_flags.extend(ver_flags)
    
    # Clarity (0-25)
    clar_score, clar_boosters, clar_flags = compute_clarity(resume_schema, resume_text)
    cred.signals["clarity"] = clar_score
    all_boosters.extend(clar_boosters)
    all_flags.extend(clar_flags)
    
    # Compute overall
    cred.overall = sum(cred.signals.values())
    cred.boosters = all_boosters[:10]
    cred.flags = all_flags[:10]
    
    return cred


# =============================================================================
# SUGGESTIONS
# =============================================================================

@dataclass
class Suggestions:
    """Improvement suggestions for resume."""
    missing_requirements: list[str] = field(default_factory=list)
    bullet_rewrites: list[dict] = field(default_factory=list)
    ats_improvements: list[str] = field(default_factory=list)
    project_recommendations: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "missing_requirements": self.missing_requirements,
            "bullet_rewrites": self.bullet_rewrites,
            "ats_improvements": self.ats_improvements,
            "project_recommendations": self.project_recommendations,
        }


def generate_heuristic_suggestions(
    resume_schema: dict,
    resume_text: str,
    jd_analysis: dict,
    fit_score: FitScore,
    credibility_score: CredibilityScore,
) -> Suggestions:
    """
    Generate improvement suggestions using heuristics.
    
    Args:
        resume_schema: Parsed resume schema
        resume_text: Raw resume text
        jd_analysis: Analyzed JD data
        fit_score: Computed fit score
        credibility_score: Computed credibility score
        
    Returns:
        Suggestions object
    """
    suggestions = Suggestions()
    
    # Missing requirements from fit score gaps (deduplicated)
    seen_gaps = set()
    for gap in fit_score.must_have_gaps[:8]:
        gap_lower = gap.lower().strip()
        if gap_lower not in seen_gaps:
            seen_gaps.add(gap_lower)
            suggestions.missing_requirements.append(gap)
    
    # ATS improvements - keywords are already filtered by LLM in jd_analyzer
    resume_lower = resume_text.lower()
    
    # Build a set of all resume skills (normalized to lowercase)
    resume_skill_set = set()
    for cat in ["technical", "tools", "soft"]:
        for skill in resume_schema.get("skills", {}).get(cat, []):
            resume_skill_set.add(skill.lower().strip())
    
    missing_keywords = []
    
    # Keywords from jd_analysis are already filtered to be technical/professional
    # (LLM filtering happens in jd_analyzer.analyze_job_description)
    for kw in jd_analysis.get("keywords", [])[:30]:
        kw_lower = kw.lower().strip()
        
        # Skip compound phrases like "python and java" - split and check individually
        if " and " in kw_lower or " or " in kw_lower:
            # Split compound keywords and check each part
            parts = re.split(r"\s+(?:and|or)\s+", kw_lower)
            all_present = all(
                _is_keyword_present(part.strip(), resume_lower, resume_skill_set)
                for part in parts if part.strip()
            )
            if all_present:
                continue  # All parts are present, skip this compound keyword
        
        # Check if keyword is missing from resume
        if not _is_keyword_present(kw_lower, resume_lower, resume_skill_set):
            # Double-check with heuristic filter as fallback
            if _is_technical_keyword(kw_lower):
                missing_keywords.append(kw)
    
    if missing_keywords:
        suggestions.ats_improvements.append(
            f"Consider adding these technical skills if applicable: {', '.join(missing_keywords[:8])}"
        )
    
    # Check for common ATS issues
    if not resume_schema.get("basics", {}).get("email"):
        suggestions.ats_improvements.append("Add a clear email address at the top of your resume")
    
    if not resume_schema.get("basics", {}).get("phone"):
        suggestions.ats_improvements.append("Add a phone number for recruiter contact")
    
    if len(resume_schema.get("skills", {}).get("technical", [])) < 5:
        suggestions.ats_improvements.append("Add a dedicated Skills section with relevant technologies")
    
    # Project recommendations based on gaps
    jd_skills = set(s.lower() for s in jd_analysis.get("required_skills", []))
    resume_skills = set()
    for cat in ["technical", "tools"]:
        resume_skills.update(s.lower() for s in resume_schema.get("skills", {}).get(cat, []))
    
    skill_gaps = jd_skills - resume_skills
    if skill_gaps:
        gap_list = list(skill_gaps)[:5]
        suggestions.project_recommendations.append(
            f"Consider building a project demonstrating: {', '.join(gap_list)}"
        )
    
    # Bullet rewrite suggestions (heuristic)
    all_bullets = []
    for exp in resume_schema.get("experience", []):
        all_bullets.extend(exp.get("bullets", []))
    
    weak_bullets = []
    for bullet in all_bullets[:10]:
        bullet_lower = bullet.lower()
        
        # Check for weak patterns
        issues = []
        if bullet_lower.startswith("responsible for"):
            issues.append("starts with 'responsible for'")
        if "helped" in bullet_lower and not re.search(r"\d", bullet):
            issues.append("uses 'helped' without metrics")
        if "worked on" in bullet_lower:
            issues.append("uses vague 'worked on'")
        if len(bullet) < 30:
            issues.append("too short")
        if not re.search(r"\d", bullet) and len(bullet) > 50:
            issues.append("no quantification")
        
        if issues:
            weak_bullets.append((bullet, issues))
    
    for bullet, issues in weak_bullets[:5]:
        suggestions.bullet_rewrites.append({
            "original": bullet,
            "rewrite_options": [],  # Will be filled by LLM if available
            "why": f"Issues: {', '.join(issues)}",
            "guardrail_note": "Consider rewriting with specific metrics and action verbs, only if accurate.",
        })
    
    return suggestions


def generate_llm_suggestions(
    resume_schema: dict,
    jd_analysis: dict,
    heuristic_suggestions: Suggestions,
) -> Suggestions:
    """
    Enhance suggestions using LLM.
    
    Args:
        resume_schema: Parsed resume schema
        jd_analysis: Analyzed JD data
        heuristic_suggestions: Base heuristic suggestions
        
    Returns:
        Enhanced Suggestions object
    """
    try:
        from core.clients.groq_client import llm_suggest_improvements, is_groq_available
        
        if not is_groq_available():
            return heuristic_suggestions
        
        # Collect resume bullets
        resume_bullets = []
        for exp in resume_schema.get("experience", []):
            resume_bullets.extend(exp.get("bullets", []))
        for proj in resume_schema.get("projects", []):
            resume_bullets.extend(proj.get("bullets", []))
        
        if not resume_bullets:
            return heuristic_suggestions
        
        # Get LLM suggestions
        llm_result = llm_suggest_improvements(
            resume_bullets=resume_bullets[:15],
            jd_requirements=jd_analysis.get("must_have", [])[:10],
            jd_keywords=jd_analysis.get("keywords", [])[:20],
        )
        
        if not llm_result:
            return heuristic_suggestions
        
        # Merge LLM suggestions with heuristic suggestions
        # Priority: heuristic keyword-based suggestions first, then LLM enhancements
        enhanced = Suggestions()
        
        # Missing requirements: prefer heuristic (based on actual skill gap analysis)
        # LLM often returns full requirement sentences - we only want specific skill gaps
        # Deduplicate by normalized name (case-insensitive)
        seen_requirements = set()
        deduped_requirements = []
        
        for req in heuristic_suggestions.missing_requirements:
            normalized = req.lower().strip()
            if normalized not in seen_requirements:
                seen_requirements.add(normalized)
                deduped_requirements.append(req)
        
        # Build set of resume skills for filtering
        resume_skills_lower = set()
        for cat in ["technical", "tools"]:
            for skill in resume_schema.get("skills", {}).get(cat, []):
                resume_skills_lower.add(skill.lower().strip())
                # Also add variations
                skill_base = skill.lower().replace(".js", "").replace("-", " ")
                resume_skills_lower.add(skill_base)
        
        llm_missing = llm_result.get("missing_requirements", [])
        for req in llm_missing:
            req_lower = req.lower().strip()
            
            # Skip duplicates (case-insensitive)
            if req_lower in seen_requirements:
                continue
            
            # Skip full sentences (they're not specific skill gaps)
            # Real skill gaps are short like "Kubernetes", "Shell", "Elasticsearch"
            # Skip if: too long, contains conjunctions, or looks like a sentence
            skip_patterns = [" with ", " and ", " or ", " of ", " in ", " for ", "experience", "knowledge", "familiarity", "understanding"]
            if len(req) > 30 or any(p in req_lower for p in skip_patterns):
                continue
            
            # Skip if requirement mentions skills already in resume
            skills_mentioned = [s for s in resume_skills_lower if s in req_lower and len(s) > 2]
            if skills_mentioned:
                continue
            
            seen_requirements.add(req_lower)
            deduped_requirements.append(req)
        
        enhanced.missing_requirements = deduped_requirements[:8]
        
        # ATS improvements: keep heuristic keyword suggestions first (they're based on actual analysis)
        # then add LLM suggestions that provide additional value
        enhanced.ats_improvements = list(heuristic_suggestions.ats_improvements)
        llm_ats = llm_result.get("ats_improvements", [])
        for imp in llm_ats:
            # Only add LLM suggestions that don't duplicate heuristic ones
            if imp not in enhanced.ats_improvements:
                enhanced.ats_improvements.append(imp)
        enhanced.ats_improvements = enhanced.ats_improvements[:8]
        
        # Project recommendations: combine both
        enhanced.project_recommendations = list(heuristic_suggestions.project_recommendations)
        llm_projects = llm_result.get("project_recommendations", [])
        for rec in llm_projects:
            if rec not in enhanced.project_recommendations:
                enhanced.project_recommendations.append(rec)
        enhanced.project_recommendations = enhanced.project_recommendations[:5]
        
        # Merge bullet rewrites: prefer LLM rewrites as they're more sophisticated
        llm_rewrites = llm_result.get("bullet_rewrites", [])
        if llm_rewrites:
            enhanced.bullet_rewrites = llm_rewrites[:8]
        else:
            enhanced.bullet_rewrites = heuristic_suggestions.bullet_rewrites
        
        return enhanced
        
    except Exception as e:
        logger.warning(f"LLM suggestions failed: {e}")
        return heuristic_suggestions


# =============================================================================
# MAIN SCORING FUNCTION
# =============================================================================

@dataclass
class MatchResult:
    """Complete matching result."""
    fit_score: FitScore
    credibility_score: CredibilityScore
    suggestions: Suggestions
    timings_ms: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "fit_score": self.fit_score.to_dict(),
            "credibility_score": self.credibility_score.to_dict(),
            "suggestions": self.suggestions.to_dict(),
        }


def compute_match(
    resume_schema: dict,
    resume_text: str,
    jd_text: str,
    use_llm: bool = True,
) -> MatchResult:
    """
    Compute complete resume-JD match analysis.
    
    Args:
        resume_schema: Parsed resume schema
        resume_text: Raw resume text
        jd_text: Raw job description text
        use_llm: Whether to use LLM for suggestions
        
    Returns:
        MatchResult with all scores and suggestions
    """
    timings = {}
    
    # Analyze JD (pass use_llm for keyword classification)
    t0 = time.time()
    from core.analysis.jd_analyzer import analyze_job_description
    jd_analysis = analyze_job_description(jd_text, use_llm=use_llm).to_dict()
    timings["jd_analysis"] = int((time.time() - t0) * 1000)
    
    # Compute fit score
    t0 = time.time()
    fit = compute_fit_score(resume_schema, resume_text, jd_analysis)
    timings["fit_scoring"] = int((time.time() - t0) * 1000)
    
    # Compute credibility score
    t0 = time.time()
    credibility = compute_credibility_score(resume_schema, resume_text)
    timings["credibility_scoring"] = int((time.time() - t0) * 1000)
    
    # Generate suggestions
    t0 = time.time()
    suggestions = generate_heuristic_suggestions(
        resume_schema, resume_text, jd_analysis, fit, credibility
    )
    
    if use_llm:
        suggestions = generate_llm_suggestions(resume_schema, jd_analysis, suggestions)
    
    timings["suggestions"] = int((time.time() - t0) * 1000)
    
    return MatchResult(
        fit_score=fit,
        credibility_score=credibility,
        suggestions=suggestions,
        timings_ms=timings,
    )


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    import json
    
    # Sample data for testing
    sample_resume = {
        "basics": {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "555-123-4567",
            "location": "San Francisco, CA",
            "links": ["https://github.com/johndoe", "https://linkedin.com/in/johndoe"],
        },
        "summary": "Senior software engineer with 5+ years of experience",
        "skills": {
            "technical": ["Python", "JavaScript", "React", "PostgreSQL", "AWS"],
            "tools": ["Docker", "Git", "Jira"],
            "soft": ["Leadership", "Communication"],
        },
        "experience": [
            {
                "company": "Tech Corp",
                "title": "Senior Software Engineer",
                "start": "2020",
                "end": "Present",
                "bullets": [
                    "Led development of microservices architecture serving 1M+ users",
                    "Reduced API latency by 40% through optimization",
                    "Mentored team of 3 junior developers",
                ],
                "tech": ["Python", "AWS", "PostgreSQL"],
                "impact_metrics": ["1M+ users", "40%"],
            }
        ],
        "projects": [],
        "education": [{"school": "UC Berkeley", "degree": "BS Computer Science", "start": "2012", "end": "2016"}],
        "certifications": ["AWS Solutions Architect"],
    }
    
    sample_jd = """
    Senior Software Engineer
    
    Requirements:
    - 5+ years of software development experience
    - Strong proficiency in Python and JavaScript
    - Experience with AWS and cloud services
    - Knowledge of PostgreSQL or similar databases
    
    Responsibilities:
    - Design and implement scalable backend services
    - Lead technical discussions and code reviews
    - Mentor junior engineers
    """
    
    result = compute_match(
        resume_schema=sample_resume,
        resume_text=json.dumps(sample_resume),
        jd_text=sample_jd,
        use_llm=False,
    )
    
    print("Fit Score:", result.fit_score.overall)
    print("Components:", result.fit_score.components)
    print("\nCredibility Score:", result.credibility_score.overall)
    print("Signals:", result.credibility_score.signals)
    print("\nSuggestions:", json.dumps(result.suggestions.to_dict(), indent=2))
