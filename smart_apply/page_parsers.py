import json
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
import re
from pydoll.browser.tab import Tab
from pydoll.elements.web_element import WebElement
from smart_apply.llm import ask_llm
from smart_apply.browser_utils import script_value
from smart_apply.logger import log_warning


def normalize_url(raw: str) -> str | None:
    """Normalize a URL: strip fragment, tracking params, trailing slash. Returns None for non-http(s) schemes."""
    _TRACKING_PARAMS = frozenset((
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'fbclid', 'gclid', 'ref', 'source',
    ))

    try:
        parsed = urlparse(raw)
    except Exception:
        return None

    if parsed.scheme not in ('http', 'https'):
        return None

    # Strip fragment
    # Strip tracking query params
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    cleaned_params = {k: v for k, v in query_params.items() if k not in _TRACKING_PARAMS}
    clean_query = urlencode(cleaned_params, doseq=True)

    # Strip trailing slash from path (but keep root '/')
    path = parsed.path.rstrip('/') or '/'

    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc.lower(),
        path,
        parsed.params,
        clean_query,
        '',  # no fragment
    ))
    return normalized


def same_origin(url_a: str, url_b: str) -> bool:
    """Check whether two URLs share the same registered domain.

    Matches exact domain, www. variants, and subdomains
    (e.g. career.site1.com is valid when visiting site1.com).
    """
    def _registered_domain(u: str) -> str:
        host = urlparse(u).netloc.lower().removeprefix('www.')
        parts = host.split('.')
        # Keep last two segments as the registered domain (e.g. site1.com)
        return '.'.join(parts[-2:]) if len(parts) >= 2 else host
    return _registered_domain(url_a) == _registered_domain(url_b)


def pre_filter_links(links: list[str], base_url: str) -> list[str]:
    """Filter and deduplicate raw href list before sending to the LLM.

    Keeps only same-origin http(s) links, removes static assets, junk paths,
    and deduplicates after normalizing.
    """
    _STATIC_EXTENSIONS = frozenset((
        '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico',
        '.pdf', '.zip', '.woff', '.woff2', '.ttf', '.eot', '.xml', '.json',
        '.mp3', '.mp4', '.avi', '.mov', '.webm',
    ))

    _JUNK_PATH_PREFIXES = (
        '/cdn-cgi/', '/wp-content/', '/wp-json/', '/wp-admin/',
        '/static/', '/assets/', '/api/', '/_next/', '/feed/',
    )

    seen: set[str] = set()
    result: list[str] = []

    for raw in links:
        normalized = normalize_url(raw)
        if not normalized:
            continue

        # Same-origin check
        if not same_origin(normalized, base_url):
            continue

        # Skip static assets by extension
        path = urlparse(normalized).path.lower()
        if any(path.endswith(ext) for ext in _STATIC_EXTENSIONS):
            continue

        # Skip junk path prefixes
        if any(path.startswith(prefix) for prefix in _JUNK_PATH_PREFIXES):
            continue

        # Deduplicate
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)

    return result


async def extract_contact_links(tab: Tab) -> list[str]:
    '''Extract links related to jobs and contact info pages.'''

    url = await tab.current_url
    result = await tab.execute_script(
        "return Array.from(document.querySelectorAll('a')).map(el => el.href)",
        return_by_value=True
    )
    links = script_value(result)
    if not links:
        return []

    # Pre-filter: same-origin, dedup, remove static assets & junk paths
    links = pre_filter_links(links, url)
    if not links:
        return []

    task = (
        "Select URLs relevant to a job application process from the list below.\n\n"

        "INCLUDE:\n"
        "1. JOB / CAREER pages — generic hubs or listing pages only.\n"
        "   a) PATH-based: the career keyword (e.g. careers, jobs, vacancies, openings, "
        "positions, work-with-us, join-us, hiring, opportunities) must be the LAST path segment. "
        "Prefix nesting before the keyword is OK (e.g. /company/careers, /en/jobs). "
        "Any additional segment AFTER the keyword makes it invalid — no exceptions "
        "(e.g. /careers/tech-way, /careers/open-positions, /jobs/12345 are all EXCLUDED).\n"
        "   b) SUBDOMAIN-based: a career keyword in the subdomain is also valid, even with "
        "a root path (e.g. careers.example.com, jobs.example.com, careers.example.com/apply). "
        "These are standalone career portals and should be INCLUDED.\n"
        "2. CONTACT / ABOUT pages — company info or contact pages useful for outreach.\n"
        "   a) PATH-based: the relevant keyword (e.g. about, about-us, contact, contact-us, "
        "company, who-we-are, get-in-touch, reach-us) must be the LAST path segment. "
        "Prefix nesting is OK (e.g. /en/contact, /company/about-us). "
        "EXCLUDE deeper sub-sections like /contact/form, /about/team, /company/press.\n"
        "   b) SUBDOMAIN-based: a contact keyword in the subdomain is also valid "
        "(e.g. contact.example.com).\n\n"

        "EXCLUDE:\n"
        "- Homepages or locale roots: /, /en, /de, /home, bare domain.\n"
        "- Blog posts, news, legal/privacy, product, or customer-facing pages.\n\n"

        "SORTING: job/career URLs first, then contact/about URLs. "
        "Within each group prefer shorter, more canonical paths.\n\n"

        "Return at most 5 results as a plain JSON array of absolute URLs. "
        "No extra text, no markdown.\n"
        'Example: ["https://example.com/careers", "https://careers.example.com", "https://example.com/contact"]\n\n'

        "URLs:\n"
        f"{json.dumps(links, indent=2)}"
    )

    res = ask_llm(task, "smart")
    extracted_links: list[str] = json.loads(res)

    # Normalize to fully qualified URLs (safety net for relative paths)
    return [urljoin(url, link) for link in extracted_links]


async def infer_company_name(tab: Tab) -> str:
    meta = await tab.query('meta[property="og:site_name"]', raise_exc=False)
    meta_site_name = meta.get_attribute("content") if meta else None

    title = await tab.title
    url = await tab.current_url

    task = (
        f"Context: Title '{title}', OG Site Name '{meta_site_name}', URL '{url}'. "
        "Task: Infer the official short company name. "
        "Guardrails: "
        "- Output ONLY the name. "
        "- Do not include descriptions, taglines, or legal suffixes like 'Inc.' or 'LLC'. "
        "- Maximum 3 words. "
        "- If unsure, provide the most likely brand name."
    )
    
    company_name = ask_llm(task, model="smart")
    
    # Post-process to enforce guardrails
    if not company_name:
        log_warning(f"LLM returned empty company name for URL: {url}.")
        # Fallback to domain name if LLM fails to provide a name
        domain = urlparse(url).netloc
        domain = domain.removeprefix('www.')
        # Take first part of domain and capitalize
        return domain.split('.')[0].capitalize()
      
    # Split LLM response into words and keep only the first 3
    words = company_name.split()
    shortened = " ".join(words[:3])

    # Truncate total character length to prevent massive strings (e.g., max 50 chars)
    return shortened[:50].strip()


async def extract_emails(tab: Tab) -> tuple[list[str], list[str]]:
    ''' Extract emails related to career and generic contacts'''
    url = await tab.current_url
    content = await tab.page_source
    html_text = html_to_plain_text(content)

    task = (
    f"Given the following text from {url}:\n\n"
    f"{html_text}\n\n"
    "Your task is to extract and categorize emails with high precision:\n\n"
    "1. 'job_emails': ONLY addresses specifically intended for submitting resumes or contacting recruiters (e.g., careers@, jobs@, recruitment@, hr@, talent@, join@). "
    "EXCLUDE administrative HR functions like 'verifications@', 'benefits@', or 'payroll@'.\n"
    "2. 'contact_emails': General-purpose addresses suitable for sending a job inquiry or introduction. "
    "Good examples: info@, contact@, hello@, hi@, office@, team@, general@, enquiries@, mail@. "
    "Use your judgement — include any prefix that a real person would read and that is appropriate for a job-related email.\n"
    "Do NOT include: support@, help@, customer@, sales@, billing@, noreply@, or other clearly non-human / transactional addresses.\n\n"
    "STRICT EXCLUSIONS (Do not include these in any category):\n"
    "- Technical/Automated: support@, help@, webmaster@, noreply@, dev@, admin@\n"
    "- Functional/Transactional: sales@, marketing@, billing@, privacy@, verifications@, media@, press@, legal@\n\n"
    "3. Return a valid JSON object:\n"
    "{\n"
    "  'job_emails': [],\n"
    "  'contact_emails': []\n"
    "}\n"
    "Sort by relevance. If no emails match a category, return an empty array."
    )
    
    res = ask_llm(task, model="smart")
    emails = json.loads(res)
    
    # filter out invalid emails that don't match a basic email pattern (as a safety check against LLM hallucinations)
    emails['job_emails'] = [email for email in emails['job_emails'] if email_valid(email)]
    emails['contact_emails'] = [email for email in emails['contact_emails'] if email_valid(email)]

    return emails['job_emails'], emails['contact_emails']  


async def extract_forms(tab: Tab) -> list[str]:
    ''' Extract all forms on the current page as list of html snippets'''
    result = await tab.execute_script(
        "return Array.from(document.querySelectorAll('form')).map(el => el.outerHTML)",
        return_by_value=True
    )
    # TODO: maybe we should scan iframes containing forms as well?
    return script_value(result) or []


async def element_outer_html(element: WebElement) -> str:
    result = await element.execute_script("return this.outerHTML", return_by_value=True)
    return script_value(result) or ''


def html_to_plain_text(html):
    """
    Converts HTML to plain text by removing all tags (replacing them with a space to prevent word concatenation)
    and excluding content from scripts, styles, images, and vector images (SVGs).
    This function uses regex for speed and has no external dependencies.
    Multiple whitespaces are collapsed into a single space at the end.
    
    Args:
    html (str): The input HTML string.
    
    Returns:
    str: The plain text extracted from the HTML.
    """
    # Remove <script> tags and their content, replace with space
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove <style> tags and their content, replace with space
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove <svg> tags and their content (vector images), replace with space
    html = re.sub(r'<svg[^>]*>.*?</svg>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove <img> tags (images, including those with blob: or data: URIs), replace with space
    html = re.sub(r'<img[^>]*>', ' ', html, flags=re.IGNORECASE)
    
    # Remove all remaining HTML tags (including comments), replace with space
    html = re.sub(r'<[^>]*>', ' ', html)
    
    # Normalize whitespace: replace multiple spaces/newlines with single space and strip
    html = re.sub(r'\s+', ' ', html).strip()
    
    return html


def email_valid(email: str) -> bool:

    _MAX_EMAIL_LENGTH = 254
    _MAX_LOCAL_LENGTH = 64
    _MAX_DOMAIN_LABEL_LENGTH = 63

    # Compiled once at module level
    _EMAIL_PATTERN = re.compile(
        r"""
        ^
        (?P<local>
            [a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+
            (?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*
        )
        @
        (?P<domain>
            (?:
                [a-zA-Z0-9]
                (?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?
                \.
            )+
            [a-zA-Z]{2,63}
        )
        $
        """,
        re.VERBOSE,
    )

    if not email or len(email) > _MAX_EMAIL_LENGTH:
        return False

    match = _EMAIL_PATTERN.fullmatch(email)
    if not match:
        return False

    local = match.group("local")
    if len(local) > _MAX_LOCAL_LENGTH:
        return False

    domain = match.group("domain")
    return all(len(label) <= _MAX_DOMAIN_LABEL_LENGTH for label in domain.split("."))