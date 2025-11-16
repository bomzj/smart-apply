from dataclasses import dataclass
import json
from urllib.parse import urljoin
from llm import ask_llm
import re
from playwright.sync_api import Page

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
    "Your task:\n"
    "1. Extract all links related to job applications or career opportunities. Look for paths containing keywords like 'career', 'job', 'vacancies', 'work-with-us', 'opportunities', 'hiring', or localized equivalents (e.g., 'stellen', 'emplois').\n"
    "   - Focus ONLY on generic, top-level pages (not specific job postings). A page is 'generic' if:\n"
    "     - The path contains the keywords but lacks segments indicating a specific role, title, ID, or detail (e.g., no 'frontend', 'developer', '123', 'apply/abc', or similar).\n"
    "     - It's a high-level hub for browsing/open roles, even if nested under a parent like '/who-we-are' or '/about'.\n"
    "   - Valid examples: '/careers', '/jobs', '/en/vacancies', '/de-de/work-with-us', '/who-we-are/culture-and-careers', '/culture/jobs', '/en/opportunities'.\n"
    "   - Invalid examples: '/careers/frontend-developer', '/jobs/detail/123', '/en/careers/web-developer-role', '/hiring/senior-engineer/abc'.\n"
    "   - Include localized/variant forms with language prefixes (e.g., '/en/careers', '/de-de/jobs').\n"
    "   - For each candidate link, briefly reason if it's generic (1-2 sentences) in your thinking, then include only valid ones.\n"
    "2. Extract only generic contact or company information page links that represent high-level pages about the company itself.\n"
    "   These typically include paths like:\n"
    "   - '/contact', '/contact-us', '/about', '/about-us', '/company'.\n"
    "   - Or localized/variant forms with a language prefix (e.g., '/en/contact', '/de-de/about-us', '/fr/company').\n"
    "   - Or localized equivalents containing translated words such as 'kontakt', 'ueber-uns', 'a-propos', 'entreprise', etc.\n"
    "   - Valid examples: '/contact', '/en/contact', '/de-de/about-us', '/company/about', '/who-we-are'.\n"
    "   - Invalid examples: '/about/team', '/contact/form', '/de/contact/support', '/company/about/history', '/ueber-uns/gmbh-details'.\n"
    "   - Exclude any clearly nested subpages (i.e., those with additional segments beyond the main company/contact page).\n"
    "   - For each candidate link, briefly reason if it's high-level/generic (1-2 sentences) in your thinking, then include only valid ones.\n"
    "3. Sort each array by relevancy: most direct/central matches first (e.g., '/careers' before '/who-we-are/careers').\n"
    "4. Return the result strictly in valid JSON format with the following keys:\n"
    "   - 'job_pages': array of full URLs (strings).\n"
    "   - 'contact_pages': array of full URLs (strings).\n"
    "Do not include any other text, explanations, or keys outside this JSON."
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
        f"Given the following plain text extracted from the page at {url} (all HTML tags, scripts, styles, images, and other non-text content have been removed):\n\n"
        f"{html_text}\n\n"
        "Your task:\n"
        "1. Identify and classify emails as:\n"
        "   * 'job_emails': emails likely related to job applications (e.g., containing 'hr', 'career', 'job', 'recruit')\n"
        "   * 'contact_emails': approachable, human-oriented general contact emails intended for broad enquiries (e.g., 'hello@', 'contact@', 'info@')."
        "   Exclude any departmental, functional, or technical addresses such as 'support@', 'help@', 'service@', 'sales@', 'marketing@', 'webmaster@', 'admin@', 'postmaster@', 'noreply@'."
        "2. Sort emails within each category by relevancy (most relevant first).\n"
        "3. Return the result strictly in valid JSON format with the following keys:\n"
        "   - 'job_emails': array of email addresses (sorted by relevancy)\n"
        "   - 'contact_emails': array of email addresses (sorted by relevancy)\n"
    )
    res = ask_llm(task, model="fast")
    emails = json.loads(res)

    return emails['job_emails'], emails['contact_emails']  


def extract_forms(page: Page) -> list[str]:
    ''' Extract all forms on the current page as list of html snippets'''
    forms = page.locator("form").evaluate_all("elements => elements.map(el => el.outerHTML)")
    # TODO: maybe we should scan iframes containing forms as well?
    #page.frames[0].eval_on_selector_all('form', 'els => els.map(el => el.outerHTML)')
    return forms

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