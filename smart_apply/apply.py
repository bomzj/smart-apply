from dataclasses import dataclass
import json
from urllib.parse import urlparse

from googleapiclient.errors import HttpError

from pydoll.browser.tab import Tab
from pydoll.elements.web_element import WebElement

from smart_apply.page_parsers import (
    extract_emails, 
    extract_contact_links, 
    infer_company_name
)
from smart_apply.result import Err, Ok, safe_fn
from smart_apply.gmail import send_email_from_me, gmail_quota_exceeded
from smart_apply.captcha_solvers.recaptcha import *
from smart_apply.captcha_solvers.cloudflare_challenge import *
from smart_apply.config import settings
from smart_apply.browser_utils import accept_cookie_consent, site_available, wait_for_network_idle
from smart_apply.logger import log_info, log_error, record_sent_email, record_failed_form
from smart_apply.form import *
from smart_apply.applicant import Applicant

@dataclass
class AppliedViaEmail:
    email: str

@dataclass
class AppliedViaForm:
    url: str

@dataclass
class NoLinksFound:
    pass

@dataclass
class FailedAttempt:
    pass

@dataclass
class NoApplicationMethod:
    pass

@dataclass
class SiteUnavailable:
    pass

type ApplyStatus = (
    AppliedViaEmail | 
    AppliedViaForm | 
    NoLinksFound | 
    FailedAttempt |
    NoApplicationMethod | 
    SiteUnavailable
)

@dataclass
class ApplyContext:
    tab: Tab
    applicant: Applicant


@safe_fn
async def apply_on_site(ctx: ApplyContext, start_url: str) -> ApplyStatus:
    tab = ctx.tab
    host = hostname(start_url)

    start_url = ensure_https(start_url)

    await tab.enable_auto_solve_cloudflare_captcha()
    await tab.go_to(start_url, timeout=30)
    
    if not await site_available(tab):
        raise ValueError("Site is not available")
     
    # Wait for Cloudflare challenge to be auto-solved by Pydoll if present
    try:
        await wait_until_cloudflare_resolved(tab)
    except Exception as e:
        raise ValueError(f"Failed to solve Cloudflare challenge.") from e
    
    await tab.disable_auto_solve_cloudflare_captcha()

    # Some site shows Accept Cookie consent after while, so we need to wait for a bit to see
    await wait_for_network_idle(tab, timeout=10, idle_time=3)

    # hide cookie banner if present to avoid interference with element detection and clicking
    await accept_cookie_consent(tab)

    # Wait a bit since some sites reload page after accepting cookies
    await wait_for_network_idle(tab, timeout=30, idle_time=3)

    # Extract page links related to jobs and contact info
    links = await extract_contact_links(tab)
    
    if not links:
        return NoLinksFound()

    # Limit to first 5 links to avoid excessive navigation
    links = links[:5]
    formatted_links = json.dumps(links, indent=2, ensure_ascii=False)
    log_info(f"Extracted {len(links)} contact links to visit:\n{formatted_links}")

    applicant = Applicant(
        full_name=settings.applicant_name,
        email=settings.applicant_email,
        subject=settings.applicant_subject,
        pdf_resume=settings.applicant_pdf,
        message=settings.applicant_message.strip(),
        country=settings.applicant_country,
        company=settings.applicant_company
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
            case AppliedViaEmail() | AppliedViaForm():
                return status
            case FailedAttempt():
                failed_attempt = True

    return FailedAttempt() if failed_attempt else NoApplicationMethod()


async def apply_on_page(ctx: ApplyContext, url: str) -> ApplyStatus:
    '''Try to apply to job on the page by sending email or submitting form'''
    tab = ctx.tab

    await tab.go_to(url)

    job_emails, contact_emails = await extract_emails(tab)
    
    # Priority 1: apply via job email
    if job_emails:
        if apply_via_email(ctx, job_emails[0]):
            return AppliedViaEmail(job_emails[0])

    # Priority 2: apply via form
    form = await application_form(tab)
    
    if form:
        res = await apply_via_form(ctx, form)      
        match res:
            case Ok():
                log_info(f"Applied via form at {url}")
                return AppliedViaForm(url)
            case Err(e):
                log_error(f"Failed to apply via form at {url}: {e}")
                record_failed_form(url)

    # Priority 3: fallback to generic contact email
    if contact_emails:
        if apply_via_email(ctx, contact_emails[0]):
            return AppliedViaEmail(contact_emails[0])
        
    attempt_failed = job_emails or contact_emails or form
    
    return FailedAttempt() if attempt_failed else NoApplicationMethod()


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
            raise ValueError(f"Failed to solve ReCaptcha.") from e

    return await submit_form(form)

    
def apply_via_email(ctx: ApplyContext, email_to: str) -> bool:
    """Send application email. Returns True on success, False on non-fatal failure.
    Re-raises HttpError when Gmail rate limit is hit so the program can exit."""
    app = ctx.applicant
    try:
        send_email_from_me(email_to, app.subject, app.message, [app.pdf_resume])
    except HttpError as e:
        if gmail_quota_exceeded(e):
            raise
        error_msg = e._get_reason() if hasattr(e, '_get_reason') else str(e)
        log_error(f"Failed to send email to {email_to}: {error_msg}")
        return False
    
    
    log_info(f"Sent email to {email_to}")
    record_sent_email(email_to)

    return True


# Url utilities
def hostname(url: str) -> str | None:
    return urlparse(url.strip() if '://' in url else f'https://{url.strip()}').hostname


def ensure_https(url: str) -> str:
    return url if url.startswith(('http://', 'https://')) else f'https://{hostname(url)}'