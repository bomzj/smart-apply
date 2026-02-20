import json
from urllib.parse import urljoin, urlparse
import re
from pydoll.browser.tab import Tab
from pydoll.elements.web_element import WebElement
from smart_apply.llm import ask_llm
from smart_apply.browser_utils import script_value
from smart_apply.logger import log_warning


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
        
        # Take first part of domain and capitalize
        return domain.split('.')[0].capitalize()
      
    # Split LLM response into words and keep only the first 3
    words = company_name.split()
    shortened = " ".join(words[:3])

    # Truncate total character length to prevent massive strings (e.g., max 50 chars)
    return shortened[:50].strip()


async def extract_contact_links(tab: Tab) -> list[str]:
    ''' Extract links related to jobs and contact info pages'''
    
    url = await tab.current_url
    result = await tab.execute_script(
        "return Array.from(document.querySelectorAll('a')).map(el => el.href)",
        return_by_value=True
    )
    links = script_value(result)
    if not links: return []

    task = (
    f"Given the following list of URLs found on the page at {url}:\n\n"
    f"{json.dumps(links, indent=2)}\n\n"
    "Your task is to extract career/job and high-level company/contact pages with the rules below.\n"
    "IMPORTANT: Completely exclude any homepage or landing page in any language "
    "(e.g. '/', '/en', '/de', '/it-it', '/home', or the bare domain URL itself).\n\n"

    "1. Job/career pages — generic hubs only (NOT specific job postings):\n"
    "   - The path must contain at least one career-related keyword: career(s), job(s), vacanc(y|ies), "
    "     opening(s), position(s), work-with-us, join-us, hiring, opportunities, stelle(n), offerte, "
    "     emploi(s), lavora-con-noi, karriere, etc.\n"
    "   - It may be nested (e.g. '/company/careers', '/en/work-with-us/join', '/about/career').\n"
    "   - It is valid ONLY if it appears to be the final/leaf page — i.e. no additional segments after the keyword part "
    "     that look like a specific role, ID, or detail page.\n"
    "   - Valid examples:\n"
    "       '/careers', '/en/careers', '/company/careers', '/about/work-with-us', '/join-us/careers', "
    "       '/de/karriere', '/it/lavora-con-noi'\n"
    "   - Invalid examples:\n"
    "       • Specific postings: '/careers/senior-python-developer', '/jobs/12345', '/karriere/detail/abc'\n"
    "       • Deeper subpages: '/careers/open-positions', '/work-with-us/apply', '/join/team'\n"
    "       • Homepages: '/', '/en', root domain\n"
    "   - In thinking: 1-2 sentences justifying why it is a generic leaf page.\n\n"

    "2. Company / contact pages — high-level or reasonable leaf pages only:\n"
    "   - The path must contain at least one relevant keyword: about(-us), company, who-we-are, contact(-us), "
    "     ueber-uns, über-uns, chi-siamo, a-propos, kontakt, contatti, get-in-touch, reach-us, etc.\n"
    "   - Nesting is allowed (e.g. '/company/contact', '/en/about-us/contact', '/info/get-in-touch').\n"
    "   - It is valid ONLY if it is the final/leaf page — no further segments that indicate a sub-section "
    "     (form, locations, press, team, etc.).\n"
    "   - Valid examples:\n"
    "       '/contact', '/en/contact', '/company/contact-us', '/about/get-in-touch', "
    "       '/de/ueber-uns', '/it/contatti', '/info/kontakt'\n"
    "   - Invalid examples:\n"
    "       • Deeper pages: '/contact/form', '/contact/locations', '/about/team', '/company/legal/imprint'\n"
    "       • Homepages: '/', '/en', root domain\n"
    "   - In thinking: 1-2 sentences justifying why it is an acceptable leaf page.\n\n"

    "3. For both categories:\n"
    "   - Prioritize shorter/more direct paths when sorting (e.g. '/careers' > '/en/careers' > '/company/careers').\n"
    "   - Within the same length, put the most obvious/canonical keyword first "
    "     (e.g. a page with 'contact' beats one with only 'get-in-touch').\n\n"

    "4. Return STRICTLY valid JSON only (no extra text, no markdown):\n"
    "{\n"
    "  \"job_pages\": [\"https://example.com/careers\", ...],\n"
    "  \"contact_pages\": [\"https://example.com/contact\", ...]\n"
    "}\n"
    "Use full absolute URLs. Empty array if nothing valid is found."
    )

    res = ask_llm(task, "smart")
    extracted_links = json.loads(res)
    all_links = extracted_links['job_pages'] + extracted_links['contact_pages']

    # Normalize to fully qualified URLs
    full_urls = [urljoin(url, link) for link in all_links]
    return full_urls


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
    "2. 'contact_emails': Include ONLY general inquiry addresses. "
    "This is a STRICT WHITELIST. Only include: info@, contact@, hello@, hi@.\n"
    "Do NOT include variations like 'office@', 'support@', or 'customer@' here.\n\n"
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