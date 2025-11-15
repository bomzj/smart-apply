import json
from typing import Literal
from llm import ask_llm
from page_parsers import extract_emails, extract_forms, html_to_plain_text
from applicant import application_template
from smolagents import tool
from result import safe_call
from playwright.sync_api import Page, expect
from gmail import send_email_from_me


type ApplyMethod = Literal['email', 'form']

def apply_on_page(ctx) -> ApplyMethod | None:
    '''Try to apply to job by sending email or submitting form'''

    page = ctx['page']

    # Priority 1: apply via job email
    job_emails, contact_emails = extract_emails(page)
    
    if job_emails:
        addr = job_emails[0]
        apply_via_email(ctx, addr)
        print(f"Sent email to {addr}\n")
        return 'email'

    # Priority 2: apply via form
    forms = extract_forms(page)
    form_index = job_or_contact_form(forms)
    
    if form_index is not None:
        # preserve current url since form submission may redirect
        url = page.url
        apply_via_form(ctx, form_index, forms[form_index])
        print(f"Submitted form at {url}\n")
        return 'form'  

    # Priority 3: fallback to generic contact email
    if contact_emails:
        apply_via_email(ctx, contact_emails[0])
        print(f"Sent email to {contact_emails[0]}\n")
        return 'email'
    
    print(f"No application method found on this page {page.url}.\n")
    
    # No valid method found
    return None


def job_or_contact_form(html_forms: list[str]) -> int | None:
  
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
  
  res = ask_llm(task)

  return int(res) if res.isdigit() else None


def apply_via_form(ctx, form_index: int, form_html: str) -> bool:
    page = ctx['page']
    # TODO: expose required fields by submitting empty form
    form_data = applicant_to_form(application_template, form_html)
    # TODO: uncheck checkboxes to avoid unwanted subscriptions
    fill_form(page, form_index, form_data)
    submit_form(page, form_index)
    

def applicant_to_form(applicant, form_html: str) -> dict[str, str]:
    """Maps applicant data to form fields based on form HTML snippet."""
    
    applicant_to_form_prompt = """
        You are an expert form-filling assistant. Map applicant data to a job/contact form from the provided HTML snippet, outputting a JSON object like { "input_name1": "value1", ... }, using exact 'name' attributes as keys and suitable string values.

        Inputs:
        - Form HTML Snippet ({form_html}): Partial <form> fragment. Parse for visible <input>, <select>, <textarea> (and labels/placeholders for context). Ignore hidden/CAPTCHA/non-interactive elements (e.g., type="hidden", display:none, aria-hidden) and ignore any non-fillable controls such as <button>, submit/reset buttons, and other elements that users do not type or select values into.
        - Applicant Data ({applicant}): JSON with fields like name, email, phone, resume URL, etc. Use only this data—no inventions.

        Internal Reasoning (Do Not Output):
        1. Parse Form: List all visible controls with 'name', type, required status (via 'required', *, or cues like "must provide"), and purpose (from name/label/placeholder, e.g., "email" → email field).
        2. Map Data:
        - Exact matches first (e.g., applicant "email" → form "email").
        - Variations: Concatenate/combine (e.g., first+last → "full_name": "John Doe").
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
    
    applicant_json = json.dumps(applicant, ensure_ascii=False)
                              
    applicant_to_form_prompt = (applicant_to_form_prompt
        .replace("{form_html}", form_html)
        .replace("{applicant}", applicant_json))

    # we will use more advanced smart since fast failed to detect required fields
    res = ask_llm(applicant_to_form_prompt, model="smart")
    form_data = json.loads(res)
    
    if not form_data: raise ValueError("Failed to map applicant data to form fields")
    
    return form_data


def fill_form(page: Page, form_index: int, form_data: dict[str, str]):
    """ Fills a specific form on the page with given form_data.  """
    forms_count = page.locator("form").count()
    if form_index >= forms_count:
        raise ValueError(f"Form index {form_index} out of range. Total forms: {forms_count}")

    form = page.locator("form").nth(form_index)

    for name, value in form_data.items():
        input_locator = form.locator(f'[name="{name}"]')

        if input_locator.count() == 0:
            raise ValueError(f"No element found for name='{name}' in form[{form_index}]")

        # if not input_locator.is_visible():
        #     continue

        tag = input_locator.evaluate("el => el.tagName.toLowerCase()")

        if tag == "input":
            input_type = input_locator.evaluate("el => el.type")
            if input_type in ("checkbox", "radio"):
                specific_locator = form.locator(f'[name="{name}"][value="{value}"]')
                if specific_locator.count() == 0:
                    raise ValueError(f"No matching value '{value}' for name='{name}' in form[{form_index}]")
                specific_locator.check()
            elif input_type == "file":
                input_locator.set_input_files(value)
            else:
                input_locator.fill(str(value))
        elif tag == "textarea":
            input_locator.fill(str(value))
        elif tag == "select":
            input_locator.select_option(str(value))
        else:
            raise ValueError(f"Unsupported element <{tag}> for name='{name}'")
    

def submit_form(page: Page, form_index: int):
    form_locator = page.locator('form').nth(form_index)

    # Capture handle to the correct form
    form_handle = form_locator.element_handle()

    # Submit the form and wait for potential form submission response
    with page.expect_response(lambda res: res.request.method == "POST"):
        form_locator.locator('button[type="submit"], input[type="submit"]').first.click()
    
    # Assume successful form submission hides the form, including redirects to thank you pages
    # if form is detached from DOM it will raise an error
    visible, err = safe_call(lambda: form_handle.is_visible(), log_exception=False) 
    if err or not visible:
        print(f"Form submission appears successful (form is no longer visible).")
        return

    # Also assume successful submission when input fields are cleared
    inputs = form_locator.locator('input[type="text"], input[type="email"]').all()    
    _, err = safe_call(lambda: [expect(inp).to_have_value("") for inp in inputs], log_exception=False)
    if not err:
        print(f"Form submission appears successful (input fields cleared).")
        return

    # As the last resort, prompt to verify submission success
    page_text = html_to_plain_text(page.content())
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
    
    res = ask_llm(submission_validation_prompt)
    res = json.loads(res)

    if res.get("error"):
        raise ValueError(f"Form submission validation error: {res['error']}")


def apply_via_email(ctx, email_to):
    app = application_template
    send_email_from_me(email_to, 
                    app['subject'], 
                    app['message'], 
                    [app['pdf_resume']])


## Agent Tools

def active_page(page: Page) -> Page:
    @tool
    def current_page() -> Page:
        """
        Retrieve the current active Playwright Page object.

        This function allows the agent to access the currently active browser page.
        The returned Page object can be used to navigate to URLs, interact with elements,
        evaluate JavaScript, extract information, or perform any Playwright-supported
        browser automation tasks.

        Returns:
            Page: The active Playwright Page instance.
        """
        return page
    return current_page