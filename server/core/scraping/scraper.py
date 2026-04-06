"""
Job posting URL scraper for JobLens AI.

Extracts job description text from URLs using multiple strategies:
1. Fast path: requests + readability-lxml
2. Fallback: BeautifulSoup heuristics
3. Advanced: Playwright for JS-heavy sites (optional)

Security features:
- URL scheme validation (http/https only)
- SSRF protection (blocks private IPs)
- Response size limits (2MB max)
- Strict timeouts
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)

# Configuration
MAX_RESPONSE_SIZE = 2 * 1024 * 1024  # 2 MB
REQUEST_TIMEOUT = 10.0  # seconds
PLAYWRIGHT_TIMEOUT = 15000  # milliseconds
MIN_TEXT_LENGTH = 400
IDEAL_TEXT_LENGTH = 1500
MIN_CONFIDENCE_LENGTH = 800

# Check if brotli is available for Accept-Encoding
try:
    import brotli
    _BROTLI_AVAILABLE = True
except ImportError:
    _BROTLI_AVAILABLE = False

# Multiple user agents for rotation (helps bypass basic bot detection)
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def get_headers(user_agent_index: int = 0) -> dict:
    """Get request headers with specified user agent."""
    return {
        "User-Agent": USER_AGENTS[user_agent_index % len(USER_AGENTS)],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br" if _BROTLI_AVAILABLE else "gzip, deflate",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

# Default headers (for backward compatibility)
DEFAULT_HEADERS = get_headers(0)

# Job-related keywords for confidence scoring
JOB_KEYWORDS = [
    "responsibilities",
    "requirements",
    "qualifications",
    "role",
    "about the job",
    "about this role",
    "job description",
    "what you'll do",
    "what we're looking for",
    "benefits",
    "experience",
    "skills",
    "duties",
    "position",
    "opportunity",
    "salary",
    "compensation",
    "apply",
    "candidate",
]

# CSS selectors for job content containers (priority order)
JOB_CONTAINER_SELECTORS = [
    "main",
    "article",
    "[role='main']",
    ".job-description",
    ".job-details",
    ".job-content",
    "#job-description",
    "#job-details",
    "#job-content",
    "[class*='job-description']",
    "[class*='jobDescription']",
    "[class*='job_description']",
    "[id*='job-description']",
    "[id*='jobDescription']",
    "[class*='description']",
    "[class*='responsibilities']",
    "[class*='requirements']",
    ".posting-requirements",
    ".job-posting",
    ".career-details",
    ".vacancy-description",
]

# Private IP ranges for SSRF protection
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),    # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),   # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


@dataclass
class ExtractionResult:
    """Result of job text extraction from URL."""
    text: str
    method: str
    confidence: float
    warnings: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "method": self.method,
            "confidence": self.confidence,
            "warnings": self.warnings,
        }


class ScraperError(Exception):
    """Base exception for scraper errors."""
    pass


class URLValidationError(ScraperError):
    """URL validation failed."""
    pass


class SSRFError(ScraperError):
    """SSRF protection triggered."""
    pass


class FetchError(ScraperError):
    """Failed to fetch URL."""
    pass


class ExtractionError(ScraperError):
    """Failed to extract text from HTML."""
    pass


def validate_url(url: str) -> str:
    """
    Validate URL scheme and format.
    
    Args:
        url: URL to validate
        
    Returns:
        Normalized URL
        
    Raises:
        URLValidationError: If URL is invalid
    """
    if not url or not isinstance(url, str):
        raise URLValidationError("URL must be a non-empty string")
    
    url = url.strip()
    
    parsed = urlparse(url)
    
    if parsed.scheme not in ("http", "https"):
        raise URLValidationError(f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed.")
    
    if not parsed.netloc:
        raise URLValidationError("Invalid URL: missing hostname")
    
    return url


def check_ssrf(hostname: str) -> None:
    """
    Check if hostname resolves to a private IP (SSRF protection).
    
    Args:
        hostname: Hostname to check
        
    Raises:
        SSRFError: If hostname resolves to private IP
    """
    try:
        # Resolve hostname to IP addresses
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            
            try:
                ip = ipaddress.ip_address(ip_str)
                
                for private_range in PRIVATE_IP_RANGES:
                    if ip in private_range:
                        raise SSRFError(f"Access to private IP range blocked: {ip_str}")
                        
            except ValueError:
                continue
                
    except socket.gaierror as e:
        raise FetchError(f"DNS resolution failed for {hostname}: {e}")


def compute_confidence(text: str) -> float:
    """
    Compute extraction confidence score based on heuristics.
    
    Args:
        text: Extracted text
        
    Returns:
        Confidence score between 0.0 and 1.0
    """
    if not text:
        return 0.0
    
    text_lower = text.lower()
    text_len = len(text)
    
    # Length score (0-0.4)
    if text_len >= IDEAL_TEXT_LENGTH:
        length_score = 0.4
    elif text_len >= MIN_CONFIDENCE_LENGTH:
        length_score = 0.2 + 0.2 * (text_len - MIN_CONFIDENCE_LENGTH) / (IDEAL_TEXT_LENGTH - MIN_CONFIDENCE_LENGTH)
    elif text_len >= MIN_TEXT_LENGTH:
        length_score = 0.1 + 0.1 * (text_len - MIN_TEXT_LENGTH) / (MIN_CONFIDENCE_LENGTH - MIN_TEXT_LENGTH)
    else:
        length_score = 0.1 * text_len / MIN_TEXT_LENGTH
    
    # Keyword score (0-0.4)
    keyword_count = sum(1 for kw in JOB_KEYWORDS if kw in text_lower)
    keyword_score = min(0.4, keyword_count * 0.05)
    
    # Alphabetic ratio score (0-0.2)
    alpha_chars = sum(1 for c in text if c.isalpha())
    total_chars = len(text.replace(" ", "").replace("\n", ""))
    alpha_ratio = alpha_chars / max(1, total_chars)
    alpha_score = 0.2 * min(1.0, alpha_ratio / 0.7)  # Ideal ratio ~70%
    
    confidence = length_score + keyword_score + alpha_score
    return round(min(1.0, confidence), 2)


def clean_html(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Remove unwanted elements from HTML.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        Cleaned BeautifulSoup object
    """
    # Remove script, style, and other non-content elements
    for element in soup.find_all([
        "script", "style", "noscript", "iframe", "svg", "canvas",
        "header", "footer", "nav", "aside", "form", "button",
        "meta", "link", "head"
    ]):
        element.decompose()
    
    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Remove hidden elements
    for element in soup.find_all(attrs={"style": re.compile(r"display\s*:\s*none", re.I)}):
        element.decompose()
    
    for element in soup.find_all(attrs={"hidden": True}):
        element.decompose()
    
    return soup


def extract_text_from_meta(html: str) -> Optional[str]:
    """
    Extract job description from meta tags (OpenGraph, JSON-LD, etc.).
    
    This is useful for JS-heavy sites like Workday, Greenhouse, Lever
    that embed job data in meta tags even when content is JS-rendered.
    
    Args:
        html: Raw HTML string
        
    Returns:
        Extracted text or None if extraction fails
    """
    try:
        import json
        soup = BeautifulSoup(html, "lxml")
        
        parts = []
        
        # 1. Try JSON-LD structured data (most reliable)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                
                # Handle array of objects
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") in ["JobPosting", "JobListing"]:
                            data = item
                            break
                    else:
                        continue
                
                if isinstance(data, dict):
                    # JobPosting schema
                    if data.get("@type") in ["JobPosting", "JobListing"]:
                        if data.get("title"):
                            parts.append(f"Title: {data['title']}")
                        if data.get("description"):
                            # Description may contain HTML
                            desc_soup = BeautifulSoup(data["description"], "lxml")
                            parts.append(desc_soup.get_text(separator="\n", strip=True))
                        if data.get("responsibilities"):
                            parts.append(f"Responsibilities: {data['responsibilities']}")
                        if data.get("qualifications"):
                            parts.append(f"Qualifications: {data['qualifications']}")
                        if data.get("skills"):
                            parts.append(f"Skills: {data['skills']}")
                        if data.get("employmentType"):
                            parts.append(f"Employment Type: {data['employmentType']}")
                        if data.get("jobLocation"):
                            loc = data["jobLocation"]
                            if isinstance(loc, dict):
                                addr = loc.get("address", {})
                                if isinstance(addr, dict):
                                    loc_str = ", ".join(filter(None, [
                                        addr.get("addressLocality"),
                                        addr.get("addressRegion"),
                                        addr.get("addressCountry")
                                    ]))
                                    if loc_str:
                                        parts.append(f"Location: {loc_str}")
            except (json.JSONDecodeError, TypeError):
                continue
        
        # 2. Try OpenGraph meta tags
        og_title = soup.find("meta", property="og:title")
        og_desc = soup.find("meta", property="og:description")
        
        if og_title and og_title.get("content"):
            if not any("Title:" in p for p in parts):
                parts.insert(0, f"Title: {og_title['content']}")
        
        if og_desc and og_desc.get("content"):
            desc_text = og_desc["content"]
            # Only add if substantial and not already captured
            if len(desc_text) > 100 and not any(desc_text[:50] in p for p in parts):
                parts.append(desc_text)
        
        # 3. Try standard meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            desc_text = meta_desc["content"]
            if len(desc_text) > 100 and not any(desc_text[:50] in p for p in parts):
                parts.append(desc_text)
        
        # 4. Try Twitter card meta
        twitter_desc = soup.find("meta", attrs={"name": "twitter:description"})
        if twitter_desc and twitter_desc.get("content"):
            desc_text = twitter_desc["content"]
            if len(desc_text) > 100 and not any(desc_text[:50] in p for p in parts):
                parts.append(desc_text)
        
        if parts:
            text = "\n\n".join(parts)
            # Clean up
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r" {2,}", " ", text)
            return text.strip()
        
        return None
        
    except Exception as e:
        logger.debug(f"Meta tag extraction failed: {e}")
        return None


def extract_text_readability(html: str) -> Optional[str]:
    """
    Extract main content using readability-lxml.
    
    Args:
        html: Raw HTML string
        
    Returns:
        Extracted text or None if extraction fails
    """
    try:
        from readability import Document
        
        doc = Document(html)
        summary_html = doc.summary()
        
        soup = BeautifulSoup(summary_html, "lxml")
        text = soup.get_text(separator="\n", strip=True)
        
        # Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        
        return text.strip()
        
    except Exception as e:
        logger.debug(f"Readability extraction failed: {e}")
        return None


def extract_text_beautifulsoup(html: str) -> Optional[str]:
    """
    Extract job description using BeautifulSoup heuristics.
    
    Args:
        html: Raw HTML string
        
    Returns:
        Extracted text or None if extraction fails
    """
    try:
        soup = BeautifulSoup(html, "lxml")
        soup = clean_html(soup)
        
        candidates = []
        
        # Try job-specific selectors first
        for selector in JOB_CONTAINER_SELECTORS:
            try:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(separator="\n", strip=True)
                    if len(text) >= MIN_TEXT_LENGTH:
                        # Score by length and keyword density
                        keyword_count = sum(1 for kw in JOB_KEYWORDS if kw in text.lower())
                        score = len(text) + keyword_count * 500
                        candidates.append((score, text, selector))
            except Exception:
                continue
        
        # If no good candidates, try body
        if not candidates:
            body = soup.find("body")
            if body:
                text = body.get_text(separator="\n", strip=True)
                if len(text) >= MIN_TEXT_LENGTH:
                    candidates.append((len(text), text, "body"))
        
        if candidates:
            # Sort by score descending
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_text = candidates[0][1]
            
            # Clean up
            best_text = re.sub(r"\n{3,}", "\n\n", best_text)
            best_text = re.sub(r" {2,}", " ", best_text)
            
            return best_text.strip()
        
        return None
        
    except Exception as e:
        logger.debug(f"BeautifulSoup extraction failed: {e}")
        return None


async def extract_text_playwright(url: str) -> Optional[str]:
    """
    Extract text using Playwright for JS-heavy sites.
    
    Args:
        url: URL to fetch and render
        
    Returns:
        Extracted text or None if extraction fails
    """
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                context = await browser.new_context(
                    user_agent=DEFAULT_HEADERS["User-Agent"],
                    locale="en-US",
                )
                
                page = await context.new_page()
                
                await page.goto(url, wait_until="networkidle", timeout=PLAYWRIGHT_TIMEOUT)
                
                # Wait a bit for any lazy-loaded content
                await page.wait_for_timeout(1000)
                
                html = await page.content()
                
                # Try readability first, then BeautifulSoup
                text = extract_text_readability(html)
                if text and len(text) >= MIN_CONFIDENCE_LENGTH:
                    return text
                
                text = extract_text_beautifulsoup(html)
                return text
                
            finally:
                await browser.close()
                
    except ImportError:
        logger.warning("Playwright not installed. Skipping JS rendering.")
        return None
    except Exception as e:
        logger.debug(f"Playwright extraction failed: {e}")
        return None


async def fetch_html(url: str) -> str:
    """
    Fetch HTML from URL with security checks.
    
    Args:
        url: URL to fetch
        
    Returns:
        HTML content
        
    Raises:
        FetchError: If fetch fails
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    
    if not hostname:
        raise FetchError("Invalid URL: missing hostname")
    
    # SSRF check
    check_ssrf(hostname)
    
    last_error = None
    
    # Try with different user agents (helps bypass basic bot detection)
    for attempt in range(len(USER_AGENTS)):
        try:
            headers = get_headers(attempt)
            
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                max_redirects=5,
            ) as client:
                response = await client.get(url, headers=headers)
                
                # Check response size
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_RESPONSE_SIZE:
                    raise FetchError(f"Response too large: {content_length} bytes (max {MAX_RESPONSE_SIZE})")
                
                response.raise_for_status()
                
                # Check content type
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    raise FetchError(f"Unexpected content type: {content_type}")
                
                # Read with size limit
                content = response.text
                if len(content) > MAX_RESPONSE_SIZE:
                    content = content[:MAX_RESPONSE_SIZE]
                
                return content
                
        except httpx.HTTPStatusError as e:
            last_error = e
            # Retry with different user agent on 403/429
            if e.response.status_code in (403, 429):
                logger.debug(f"Got {e.response.status_code}, trying different user agent (attempt {attempt + 1})")
                continue
            raise FetchError(f"HTTP error {e.response.status_code}: {e.response.reason_phrase}")
        except httpx.TimeoutException:
            raise FetchError(f"Request timed out after {REQUEST_TIMEOUT}s")
        except httpx.RequestError as e:
            raise FetchError(f"Request failed: {str(e)}")
    
    # All attempts failed
    if last_error:
        raise FetchError(f"HTTP error {last_error.response.status_code}: {last_error.response.reason_phrase} (tried {len(USER_AGENTS)} user agents)")


def is_valid_text(text: str) -> bool:
    """
    Check if extracted text is valid (not binary/garbled).
    
    Args:
        text: Text to validate
        
    Returns:
        True if text appears to be valid readable content
    """
    if not text or len(text) < 50:
        return False
    
    # Check for high ratio of printable ASCII characters
    sample = text[:1000]
    printable_count = sum(1 for c in sample if c.isprintable() or c in '\n\r\t')
    printable_ratio = printable_count / len(sample)
    
    # If less than 80% printable, likely binary/garbled
    if printable_ratio < 0.8:
        return False
    
    # Check for common HTML/text markers
    text_lower = text.lower()
    has_html_markers = any(marker in text_lower for marker in [
        '<!doctype', '<html', '<head', '<body', '<div', '<p>',
        'the ', 'and ', 'for ', 'job', 'work', 'position'
    ])
    
    return has_html_markers


async def extract_job_text_from_url(
    url: str,
    use_playwright: bool = True,
) -> dict:
    """
    Extract job description text from a URL.
    
    Tries multiple extraction strategies in order:
    1. requests + readability-lxml
    2. BeautifulSoup heuristics
    3. Meta tags (OpenGraph, JSON-LD)
    4. Playwright rendering (if enabled)
    
    Args:
        url: Job posting URL
        use_playwright: Whether to use Playwright as fallback
        
    Returns:
        Dictionary with keys: text, method, confidence, warnings
        
    Raises:
        URLValidationError: If URL is invalid
        SSRFError: If URL resolves to private IP
        FetchError: If fetch fails
        ExtractionError: If text extraction fails completely
    """
    warnings = []
    html = None
    used_playwright_for_fetch = False
    
    # Validate URL
    url = validate_url(url)
    
    # Fetch HTML
    logger.info(f"Fetching URL: {url}")
    try:
        html = await fetch_html(url)
        logger.info(f"Fetched {len(html)} bytes")
    except FetchError as e:
        # On 403/blocked, try Playwright if available
        if "403" in str(e) and use_playwright:
            logger.info("Got 403 Forbidden, trying Playwright...")
            warnings.append("Site blocked direct requests; using browser rendering")
            try:
                from playwright.async_api import async_playwright
                
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    try:
                        context = await browser.new_context(
                            user_agent=USER_AGENTS[0],
                            locale="en-US",
                        )
                        page = await context.new_page()
                        await page.goto(url, wait_until="networkidle", timeout=PLAYWRIGHT_TIMEOUT)
                        await page.wait_for_timeout(2000)  # Wait for JS to render
                        html = await page.content()
                        used_playwright_for_fetch = True
                        logger.info(f"Playwright fetched {len(html)} bytes")
                    finally:
                        await browser.close()
            except ImportError:
                logger.warning("Playwright not installed, cannot bypass 403")
                raise FetchError(
                    f"{str(e)}. This site blocks automated requests. "
                    "Install Playwright to bypass: pip install playwright && playwright install chromium"
                )
            except Exception as pw_error:
                logger.warning(f"Playwright fetch failed: {pw_error}")
                raise e
        else:
            raise
    
    if not html:
        raise FetchError("Failed to fetch page content")
    
    # Validate HTML is readable text (not binary/garbled)
    if not is_valid_text(html):
        logger.warning("Fetched content appears to be binary or garbled")
        warnings.append("Response may be improperly decoded; ensure 'brotli' package is installed")
        raise ExtractionError(
            "Failed to decode page content. The page may use Brotli compression. "
            "Install the 'brotli' package: pip install brotli"
        )
    
    # Strategy 1: Readability
    logger.debug("Trying readability extraction...")
    text = extract_text_readability(html)
    method = "readability-lxml"
    
    if text and len(text) >= MIN_CONFIDENCE_LENGTH:
        confidence = compute_confidence(text)
        if confidence >= 0.5:
            logger.info(f"Readability extraction successful: {len(text)} chars, confidence={confidence}")
            return ExtractionResult(
                text=text,
                method=method,
                confidence=confidence,
                warnings=warnings,
            ).to_dict()
    
    # Strategy 2: BeautifulSoup heuristics
    logger.debug("Trying BeautifulSoup extraction...")
    bs_text = extract_text_beautifulsoup(html)
    
    if bs_text:
        bs_confidence = compute_confidence(bs_text)
        
        # Use BS result if better than readability
        if not text or len(bs_text) > len(text) or bs_confidence > compute_confidence(text or ""):
            text = bs_text
            method = "beautifulsoup-heuristic"
            confidence = bs_confidence
            
            if confidence >= 0.4:
                logger.info(f"BeautifulSoup extraction successful: {len(text)} chars, confidence={confidence}")
                return ExtractionResult(
                    text=text,
                    method=method,
                    confidence=confidence,
                    warnings=warnings,
                ).to_dict()
    
    # Strategy 3: Meta tags (OpenGraph, JSON-LD) - useful for JS-heavy sites
    logger.debug("Trying meta tag extraction...")
    meta_text = extract_text_from_meta(html)
    
    if meta_text:
        meta_confidence = compute_confidence(meta_text)
        
        # Use meta result if better than previous attempts
        if not text or len(meta_text) > len(text) or meta_confidence > compute_confidence(text or ""):
            text = meta_text
            method = "meta-tags-opengraph"
            confidence = meta_confidence
            warnings.append("Content extracted from meta tags; page may be JavaScript-rendered")
            
            if confidence >= 0.3 and len(meta_text) >= MIN_TEXT_LENGTH:
                logger.info(f"Meta tag extraction successful: {len(text)} chars, confidence={confidence}")
                return ExtractionResult(
                    text=text,
                    method=method,
                    confidence=confidence,
                    warnings=warnings,
                ).to_dict()
    
    # Strategy 4: Playwright (for JS-heavy sites)
    if use_playwright and (not text or len(text) < MIN_CONFIDENCE_LENGTH):
        logger.debug("Trying Playwright extraction...")
        warnings.append("Possible dynamic site; using browser rendering")
        
        pw_text = await extract_text_playwright(url)
        
        if pw_text:
            pw_confidence = compute_confidence(pw_text)
            
            if not text or len(pw_text) > len(text) or pw_confidence > compute_confidence(text or ""):
                text = pw_text
                method = "playwright-rendered"
                confidence = pw_confidence
                logger.info(f"Playwright extraction successful: {len(text)} chars, confidence={confidence}")
    
    # Final result
    if text:
        confidence = compute_confidence(text)
        
        if len(text) < MIN_TEXT_LENGTH:
            warnings.append(f"Extracted text is short ({len(text)} chars); results may be unreliable")
        elif len(text) < MIN_CONFIDENCE_LENGTH:
            warnings.append(f"Extracted text is below ideal length ({len(text)} chars)")
        
        if confidence < 0.3:
            warnings.append("Low extraction confidence; may not be a job posting page")
        
        return ExtractionResult(
            text=text,
            method=method,
            confidence=confidence,
            warnings=warnings,
        ).to_dict()
    
    raise ExtractionError("Failed to extract meaningful text from the page")


def extract_job_text_from_url_sync(url: str, use_playwright: bool = True) -> dict:
    """
    Synchronous wrapper for extract_job_text_from_url.
    
    Args:
        url: Job posting URL
        use_playwright: Whether to use Playwright as fallback
        
    Returns:
        Dictionary with keys: text, method, confidence, warnings
    """
    import asyncio
    return asyncio.run(extract_job_text_from_url(url, use_playwright))


# =============================================================================
# MAIN - Test examples
# =============================================================================

if __name__ == "__main__":
    import asyncio
    import sys
    
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    async def test_extraction():
        """Test extraction with sample URLs."""
        
        # Test URLs (replace with actual job posting URLs for real testing)
        test_urls = [
            # Add test URLs here
            # "https://www.linkedin.com/jobs/view/...",
            # "https://www.indeed.com/viewjob?jk=...",
        ]
        
        if len(sys.argv) > 1:
            test_urls = sys.argv[1:]
        
        if not test_urls:
            print("Usage: python scraper.py <url1> [url2] ...")
            print("\nExample:")
            print("  python scraper.py 'https://example.com/job-posting'")
            return
        
        for url in test_urls:
            print(f"\n{'='*60}")
            print(f"Testing URL: {url}")
            print("="*60)
            
            try:
                result = await extract_job_text_from_url(url)
                
                print(f"\nMethod: {result['method']}")
                print(f"Confidence: {result['confidence']}")
                print(f"Warnings: {result['warnings']}")
                print(f"\nExtracted text ({len(result['text'])} chars):")
                print("-"*40)
                # Print first 1000 chars
                print(result['text'][:1000])
                if len(result['text']) > 1000:
                    print(f"\n... ({len(result['text']) - 1000} more chars)")
                    
            except ScraperError as e:
                print(f"\nError: {type(e).__name__}: {e}")
            except Exception as e:
                print(f"\nUnexpected error: {type(e).__name__}: {e}")
    
    # Test URL validation
    print("Testing URL validation...")
    
    # Valid URLs
    try:
        assert validate_url("https://example.com/job") == "https://example.com/job"
        assert validate_url("http://example.com/job") == "http://example.com/job"
        print("  ✓ Valid URLs accepted")
    except AssertionError as e:
        print(f"  ✗ Valid URL test failed: {e}")
    
    # Invalid URLs
    invalid_urls = [
        ("ftp://example.com", "Invalid scheme"),
        ("file:///etc/passwd", "Invalid scheme"),
        ("javascript:alert(1)", "Invalid scheme"),
        ("", "Empty URL"),
    ]
    
    for url, reason in invalid_urls:
        try:
            validate_url(url)
            print(f"  ✗ Should have rejected {reason}: {url}")
        except URLValidationError:
            print(f"  ✓ Correctly rejected {reason}")
    
    # Test confidence computation
    print("\nTesting confidence computation...")
    
    test_texts = [
        ("", 0.0),
        ("Short text", 0.03),  # Very short
        ("A" * 500, 0.15),  # Medium length, no keywords
        ("responsibilities requirements qualifications " * 50, 0.7),  # Good with keywords
    ]
    
    for text, expected_min in test_texts:
        conf = compute_confidence(text)
        status = "✓" if conf >= expected_min else "✗"
        print(f"  {status} Text len={len(text)}, confidence={conf:.2f} (expected >= {expected_min})")
    
    # Run async tests if URLs provided
    asyncio.run(test_extraction())
