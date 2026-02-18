from dataclasses import dataclass, asdict
import json
from typing import Literal
from urllib.parse import urlparse
import asyncio
from pydoll.browser.tab import Tab
from pydoll.elements.web_element import WebElement

from smart_apply.llm import ask_llm
from smart_apply.page_parsers import (
    extract_emails, 
    extract_forms, 
    extract_links_to_visit, 
    html_to_plain_text, 
    infer_company_name, 
    element_outer_html
)
from smart_apply.result import Err, Ok, safe_call, safe_fn
from smart_apply.gmail import send_email_from_me
from smart_apply.captcha_solvers.recaptcha import *
from smart_apply.captcha_solvers.cloudflare_challenge import *
from smart_apply.config import settings
from smart_apply.browser_utils import script_value, wait_for_network_idle, wait_until
from smart_apply.logger import log_info, log_error, log_warning, log_sent_email, log_failed_form


type ApplyStatus = Literal['applied_via_email', 'applied_via_form', 'no_links', 'failed_attempt']

@dataclass
class Applicant:
    full_name: str
    email: str
    subject: str
    pdf_resume: str
    message: str

@dataclass
class ApplyContext:
    tab: Tab
    applicant: Applicant


@safe_fn
async def apply_on_site(ctx: ApplyContext, start_url: str) -> ApplyStatus | None:
    tab = ctx.tab
    host = hostname(start_url)

    start_url = ensure_https(start_url)

    await tab.enable_auto_solve_cloudflare_captcha()
    await tab.go_to(start_url, timeout=30)
    
    # Wait for Cloudflare challenge to be auto-solved by Pydoll if present
    try:
        await wait_until_cloudflare_resolved(tab)
    except Exception as e:
        raise ValueError(f"Failed to solve Cloudflare challenge.") from e
    
    await tab.disable_auto_solve_cloudflare_captcha()

    # Extract page links related to jobs and contact info
    links = await extract_links_to_visit(tab)
    
    if not links:
        return 'no_links'

    # Limit to first 5 links to avoid excessive navigation
    links = links[:5]
    formatted_links = json.dumps(links, indent=2, ensure_ascii=False)
    log_info(f"Extracted {len(links)} relevant links to visit:\n{formatted_links}")

    applicant = Applicant(
        full_name=settings.applicant_name,
        email=settings.applicant_email,
        subject=settings.applicant_subject,
        pdf_resume=settings.applicant_pdf,
        message=settings.applicant_message.strip()
    )

    # Replace message template placeholders with actual values
    company_name = await infer_company_name(tab)
    # Mentioning company name looks more personalized which is good 
    applicant.message = applicant.message.replace("{company_name}", company_name)

    ctx.applicant = applicant
    failed_attempt = False
    for link in links:  
        status = await apply_on_page(ctx, link)
        match status:
            case 'applied_via_email' | 'applied_via_form':
                return status
            case 'failed_attempt':
                failed_attempt = True

    return 'failed_attempt' if failed_attempt else None


async def apply_on_page(ctx: ApplyContext, url: str) -> ApplyStatus | None:
    '''Try to apply to job on the page by sending email or submitting form'''
    tab = ctx.tab

    await tab.go_to(url)

    job_emails, contact_emails = await extract_emails(tab)
    
    # Priority 1: apply via job email
    if job_emails:
        apply_via_email(ctx, job_emails[0])
        return 'applied_via_email'

    # Priority 2: apply via form
    form = await job_or_contact_form(tab)
    
    if form:
        res = await apply_via_form(ctx, form)      
        match res:
            case Ok():
                log_info(f"Applied via form at {url}")
                return 'applied_via_form'
            case Err(e):
                log_failed_form(url, e)

    # Priority 3: fallback to generic contact email
    if contact_emails:
        apply_via_email(ctx, contact_emails[0])
        return 'applied_via_email'
    
    return 'failed_attempt' if form else None


async def job_or_contact_form(tab: Tab) -> WebElement | None:
    html_forms = await extract_forms(tab)
  
    task = f"""
        You will be given a list of HTML form elements as input, like this: ["<form>...</form>", "<form>...</form>", ...]. 
        Each item in the list represents one form from a webpage, indexed starting from 0.\n\n

        The list of forms:\n\n
        {html_forms} \n\n

        Your task is to analyze each form in the list and identify the most relevant one based on the following priorities:First, look for a job-related form. 
        A job-related form typically includes fields or elements indicating it's for job applications, such as:Input fields with names, labels, placeholders, or types related to "CV", "resume", "upload file", "cover letter", "experience", "position", "salary", "references", or similar job application terms.
        File upload inputs (e.g., <input type="file">) in the context of resumes or applications.
        If multiple forms seem job-related, select the one that best matches (e.g., the one with the most relevant fields).

        If no job-related form is found, fallback to identifying a contact form. A contact form typically includes general inquiry fields like "name", "email", "message", "subject", "phone", without job-specific elements.
        If no job-related or contact form is found, output None.

        Examine the HTML structure of each form, including <input>, <label>, <select>, <textarea>, and any associated text or attributes, to determine its purpose. 
        Ignore forms that are for login, search, newsletter signup, or unrelated purposes.
                
        Your output must be strictly a single integer (the 0-based index of the selected form) or the word "None" if nothing matches. 
        Do not include any explanations, reasoning, or additional text in your response.
    """
    
    res = ask_llm(task, "smart")

    if res.isdigit():
        forms = await tab.query('form', find_all=True, raise_exc=False) or []
        idx = int(res)
        if idx < len(forms):
            return forms[idx]
    return None


@safe_fn
async def apply_via_form(ctx: ApplyContext, form: WebElement):
    tab = ctx.tab
    
    # TODO: expose required fields by submitting empty form
    
    form_data = await applicant_to_form(ctx.applicant, form)
    
    # TODO: uncheck checkboxes to avoid unwanted subscriptions
    
    await fill_form(form, form_data)
    
    current_url = await tab.current_url
    recaptcha_result = await solve_recaptcha_if_present(form, tab)
    
    match recaptcha_result:
        case Ok("not_detected"):
            pass
        case Ok("solved"):
            log_info(f"ReCaptcha solved on {current_url}.")
        case Err(e):
            raise ValueError(f"Failed to solve ReCaptcha on {current_url}.") from e

    return await submit_form(tab, form)

    
async def applicant_to_form(applicant: Applicant, form: WebElement) -> dict[str, str]:
    """Maps applicant data to form fields based on form HTML snippet."""
    form_html = await element_outer_html(form)

    applicant_to_form_prompt = """
        You are an expert form-filling assistant. Map applicant data to a job/contact form from the provided HTML snippet, outputting a JSON object like { "input_name1": "value1", ... }, using exact 'name' attributes as keys and suitable string values.

        Inputs:
        - Form HTML Snippet ({form_html}): Partial <form> fragment. Parse for visible <input>, <select>, <textarea> (and labels/placeholders for context). Ignore hidden/CAPTCHA/non-interactive elements (e.g., type="hidden", display:none, aria-hidden) and ignore any non-fillable controls such as <button>, submit/reset buttons, and other elements that users do not type or select values into.
        - Applicant Data ({applicant}): JSON with fields like name, email, phone, resume URL, etc. Use only this data—no inventions.

        Internal Reasoning (Do Not Output):
        1. Parse Form: List all visible controls with 'name', type, required status (via 'required', *, or cues like "must provide"), and purpose (from name/label/placeholder, e.g., "email" → email field).
        2. Map Data:
        - Exact matches first (e.g., applicant "email" → form "email").
        - Specific Field Handling:
            • For message/comment/body textareas: Map ONLY 'applicant.message'. Do NOT prepend or include 'applicant.subject' in this field unless the form specifically labels the field as "Subject and Message".
            • If a distinct "Subject" field exists in the form, map 'applicant.subject' there. Otherwise, drop the subject.
        - Name Variations: Concatenate/combine ONLY for name fields (e.g., first+last -> "full_name": "John Doe").
        - Required/no match:
            • Try to derive from available applicant data (e.g., use experience summary as a cover-letter-style text).
            • If derivation is impossible, use type-appropriate safe placeholders:
              • phone fields → structurally valid fallback such as "+0000000000")
              • postal/zip → "00000"
              • dates → "1970-01-01" or nearest valid default
            • Do not use "N/A" for any field that is commonly validated (phone, email, postal code, URLs, dates).
            • For fields that are required but do not commonly require strict format
            (e.g., generic text fields): use "N/A".
            • Never leave a required field empty.
        - Optional/no mapping: Skip entirely.
        - Edge cases: <select> → best 'value' option; checkboxes → "on" if checked;.

        Output: Valid JSON only—no text. Empty {} if no mappable fields or parse fails. Keys as-is (e.g., "full_name"). Escape JSON specials.
        """
    
    applicant_json = json.dumps(asdict(applicant), ensure_ascii=False)
                              
    applicant_to_form_prompt = (applicant_to_form_prompt
        .replace("{form_html}", form_html)
        .replace("{applicant}", applicant_json))

    # we will use more advanced smart since fast failed to detect required fields
    res = ask_llm(applicant_to_form_prompt, model="smart")
    form_data = json.loads(res)
    
    if not form_data: raise ValueError("Failed to map applicant data to form fields")
    
    return form_data


async def fill_form(form: WebElement, form_data: dict[str, str]):
    """ Fills a specific form on the page with given form_data.  """

    for name, value in form_data.items():
        input_element = await form.query(f'[name="{name}"]', raise_exc=False)

        if not input_element:
            raise ValueError(f"No element found for name='{name}' in the form.")

        tag = (input_element.tag_name or '').lower()
        
        await input_element.scroll_into_view()  # Ensure the element is in view before interacting

        if tag == "input":
            input_type = input_element.get_attribute('type') or 'text'
            if input_type in ("checkbox", "radio"):
                # For radios and checkbox groups, select the specific option by value
                specific = await form.query(f'[name="{name}"][value="{value}"]', raise_exc=False)
                if specific:
                    result = await specific.execute_script("return this.checked", return_by_value=True)
                    if not script_value(result):
                        # Use JS click to avoid Pydoll issues with visibility (e.g. width/height=0)
                        await specific.execute_script("this.click()")
                # Treat single checkbox differently
                elif input_type == "checkbox":
                    # Handle boolean toggles (allows unchecking!)
                    should_check = str(value).lower() in ["true", "1", "yes", "on"]
                    result = await input_element.execute_script("return this.checked", return_by_value=True)
                    currently_checked = script_value(result)
                    if bool(currently_checked) != should_check:
                        await input_element.execute_script("this.click()")
                else:
                    # Raise error for radios so you don't accidentally select the wrong one
                    raise ValueError(f"Radio option '{value}' not found for name='{name}'")
            elif input_type == "file":
                await input_element.set_input_files(value)
            else:
                # Ensure element is focused, since email inputs might fail without focus
                await input_element.click()
                await input_element.type_text(value, True)
        elif tag == "textarea":
            await input_element.clear()
            await input_element.insert_text(str(value))
        elif tag == "select":
            # Select option by value using JavaScript
            escaped = str(value).replace("'", "\\'")
            await input_element.execute_script(
                f"this.value = '{escaped}'; "
                "this.dispatchEvent(new Event('change', {bubbles: true}))",
                return_by_value=True
            )
        else:
            raise ValueError(f"Unsupported element <{tag}> for name='{name}'")
    
@safe_fn
async def submit_form(tab: Tab, form: WebElement):
    # Find submit button
    submit_btn = await form.query(
        'button[type="submit"], input[type="submit"]', raise_exc=False
    )
    if not submit_btn:
        submit_btn = await form.query('button', raise_exc=False)

    if not submit_btn:
        raise ValueError("No submit button found in form.")

    # Click submit and wait for potential form submission response
    await submit_btn.click()
    await asyncio.sleep(10)

    # Assume successful form submission hides the form, including redirects to thank you pages
    # if form is detached from DOM is_visible will raise or return False
    await form.scroll_into_view()  # Ensure the form is in view to get accurate visibility status
    if not await form.is_visible():
        log_info("Form submission appears successful (form is no longer visible).")
        return

    # Also assume successful submission when input fields are cleared
    inputs = await form.query(
        'input[type="text"], input[type="email"]', find_all=True, raise_exc=False
    ) or []
    
    all_cleared = True
    for inp in inputs:
        result = await inp.execute_script("return this.value", return_by_value=True)
        if script_value(result):
            all_cleared = False
            break

    if all_cleared and inputs:
        log_info("Form submission appears successful (input fields cleared).")
        return

    # As the last resort, prompt to verify submission success
    page_text = html_to_plain_text(await tab.page_source)
    submission_validation_prompt = """
        You are a validation assistant. You will be provided with the full text content (`innerText`) of a web page **after a form submission**. Your task is to determine if the form was successfully submitted.

        - If the page contains a clear confirmation message such as "Thank you", "Submission successful", "Your request has been received", or anything that indicates success, return:
        {
            "submitted": true
        }

        - If the page contains error messages, warnings, or anything indicating the submission failed, return:
        {
            "submitted": false,
            "error": "<brief error message extracted from the page>"
        }

        - If it is unclear whether the submission succeeded, return:
        {
            "submitted": false,
            "error": "Unable to determine submission status"
        }

        **Do not provide any explanation, only return the JSON object.**

        Here is the page text:
        {page_text}
        """.replace("{page_text}", page_text)
    
    res = ask_llm(submission_validation_prompt, model="smart")
    res = json.loads(res)

    if res.get("error"):
        raise ValueError(res['error'])


def apply_via_email(ctx: ApplyContext, email_to: str):
    app = ctx.applicant
    send_email_from_me(email_to, app.subject, app.message, [app.pdf_resume])
    log_sent_email(email_to)


# Url utilities
def hostname(url: str) -> str | None:
    return urlparse(url.strip() if '://' in url else f'https://{url.strip()}').hostname


def ensure_https(url: str) -> str:
    return url if url.startswith(('http://', 'https://')) else f'https://{hostname(url)}'