import asyncio
from dataclasses import asdict
import json

from pydoll.browser.tab import Tab
from pydoll.elements.web_element import WebElement

from smart_apply.applicant import Applicant
from smart_apply.browser_utils import script_value
from smart_apply.llm import ask_llm
from smart_apply.logger import log_debug, log_warning, log_warning
from smart_apply.page_parsers import outer_html
from smart_apply.result import Err, safe_fn


async def application_form(tab: Tab) -> WebElement | None:
    # Extract regular and iframe forms
    forms = await tab.query('form', find_all=True, raise_exc=False)
    iframes = await tab.query('iframe', find_all=True, raise_exc=False)
    for iframe in iframes:
        forms += await iframe.query('form', find_all=True, raise_exc=False)
    
    if not forms:
        return

    form_htmls = [await outer_html(form) for form in forms]
    
    task = f"""
    You are an HTML parsing assistant. Your task is to analyze a provided list of HTML forms and identify the most relevant one based on specific priorities. 
    
    The input data provided at the end of this prompt is a list of HTML form elements formattted as: ["<form>...</form>", "<form>...</form>", ...]. Each form in the list is indexed starting from 0.

    ### PRIORITIES:
    1.  **Job-Related Form (Highest Priority):** Look for fields or elements clearly indicating a job application. 
		This includes input fields with names, labels, placeholders, or types related to "CV", "resume", "upload file", "cover letter", "experience", "position", "salary", "references". 
		Look specifically for file upload inputs (e.g., <input type="file">) in the context of resumes. 
		If multiple forms match, select the best match.
    2.  **Contact Form (Fallback):** If no dedicated job form is found, look for a generic contact form. 
		**CRITICAL REQUIREMENT: To qualify as a valid fallback, this contact form MUST contain either a file upload input (for a CV/attachment) OR a <textarea> input (for a message).** 
		It should also contain general inquiry fields like "name", "email", or "phone".
    3.  **None:** Ignore forms for login, search, newsletter signup, or unrelated purposes. 
		If no form meets the criteria for Priority 1 or Priority 2, the result is None.

    ### INSTRUCTIONS:
    Examine the HTML structure of each form (including <input>, <label>, <select>, <textarea>, and associated text/attributes) to determine its purpose.

    ### OUTPUT FORMAT:
    Respond with strictly a single integer (the 0-based index of the selected form) or the word "None". 
    Do not include any explanations, reasoning, markdown, or additional text.

    ### DATA:
    <forms>
    {form_htmls}
    </forms>
    """
    
    res = ask_llm(task, "smart", reasoning="high")

    if not res.isdigit():
        return None
    
    idx = int(res)
    if idx >= 0 and idx < len(forms):
        return forms[idx]
    
    log_warning(f"LLM returned an out-of-range form index: {idx}. Response: {res}")
    return None


async def applicant_to_form(applicant: Applicant, form: WebElement) -> dict[str, str]:
    """Maps applicant data to form fields based on form HTML snippet."""
    form_html = await outer_html(form)

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
    res = ask_llm(applicant_to_form_prompt, model="smart", reasoning="high")
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
async def submit_form(form: WebElement):
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
    await form.scroll_into_view()  # Ensure the form is in view to get accurate visibility status
    if not await form.is_visible():
        log_debug("Form submission appears successful (form is no longer visible).")
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
        log_debug("Form submission appears successful (input fields cleared).")
        return

    return Err('form is still visible and input fields not cleared after submission, cannot confirm success')
