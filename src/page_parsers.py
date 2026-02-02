from dataclasses import dataclass
import json
from urllib.parse import urljoin
from llm import ask_llm
import re
from playwright.sync_api import Page, Locator

from result import safe_call


def infer_company_name(page: Page) -> str:
    meta_site_name = safe_call(lambda: page
      .locator('meta[property="og:site_name"]')
      .get_attribute("content", timeout=1)
    )
    title = page.title()
    url = page.url
    task = (
        f"Given the website with title '{title}' and meta og:site_name '{meta_site_name}', " 
        f"infer the company name for {url}."
    )
    return ask_llm(task)


def extract_links_to_visit(page: Page) -> list[str]:
    ''' Extract links related to jobs and contact info pages'''
    
    url = page.url
    links = page.locator("a").evaluate_all("elements => elements.map(el => el.href)")
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


def extract_emails(page: Page) -> tuple[list[str], list[str]]:
    ''' Extract emails related to career and generic contacts'''
    url = page.url
    content = page.content()
    html_text = html_to_plain_text(content)
    task = (
    f"Given the following text from {url}:\n\n"
    f"{html_text}\n\n"
    "Your task is to extract and categorize emails with high precision:\n\n"
    "1. 'job_emails': ONLY addresses specifically intended for submitting resumes or contacting recruiters (e.g., careers@, jobs@, recruitment@, hr@, talent@, join@). "
    "EXCLUDE administrative HR functions like 'verifications@', 'benefits@', or 'payroll@'.\n"
    "2. 'contact_emails': Include ONLY general inquiry addresses. "
    "This is a STRICT WHITELIST. Only include: info@, contact@, hello@.\n"
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

    return emails['job_emails'], emails['contact_emails']  


def extract_forms(page: Page) -> list[str]:
    ''' Extract all forms on the current page as list of html snippets'''
    forms = page.locator("form").evaluate_all("elements => elements.map(el => el.outerHTML)")
    # TODO: maybe we should scan iframes containing forms as well?
    #page.frames[0].eval_on_selector_all('form', 'els => els.map(el => el.outerHTML)')
    return forms


def locator_to_html(loc: Locator) -> str:
    return loc.evaluate("el => el.outerHTML")


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