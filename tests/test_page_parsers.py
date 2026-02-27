import pytest
import urllib.parse
from smart_apply.page_parsers import html_to_plain_text, infer_company_name, valid_email, pre_filter_links, extract_emails
from pydoll.browser.tab import Tab


def test_html_to_plain_text():
    html =  """
        <html>
        <head>
        <style>body { color: red; }</style>
        <script>alert('hi');</script>
        </head>
        <body>
        <!-- This is a comment that should be removed -->
        <p>Hello</p><p>world!</p>
        <b>This is <i>bold and italic</i> text.</b>
        <img src="blob:https://example.com/image" alt="Image">
        <img src="data:image/png;base64,iVBORw0KGgo=" alt="Base64 image">
        <svg><rect width="100" height="100"/></svg>
        <!-- Another comment -->
        <div>More text here.<br>With a line break.</div>
        </body>
        </html>
    """
    assert html_to_plain_text(html) == "Hello world! This is bold and italic text. More text here. With a line break."


@pytest.mark.parametrize(
    "url, expected_company_name",
    [
        ("https://www.google.com", "Google"),
        ("https://www.apple.com", "Apple"),
        ("https://www.microsoft.com", "Microsoft"),
        ("https://www.neweratech.com", "New Era Technology"),
        ("https://www.epam.com", "EPAM"),
        ("https://agilitymultichannel.com", "Insight Software"),
        ("https://www.qbankdam.com", "QBank"),
        ("https://www.4ng.nl/", "Conclusion Experience"),
    ]
)
async def test_infer_company_name(tab: Tab, url, expected_company_name):
    await tab.go_to(url)
    company_name = await infer_company_name(tab)
    assert company_name == expected_company_name
    await tab.close()


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("hello@example.com", True),
        ("john.doe@example.com", True),
        ("user@example-site.com", True),
        ("hello@example.com.au", True),
        ("USER+tag@sub.example.com", True),
        ("bad..dots@example.com", False),
        ("no-at-symbol.com", False),
        ("user@-invalid.com", False),
        ("user@example-.com", False),
        ("user@exa_mple.com", False),
        (f"{'a' * 65}@example.com", False),
        (f"user@{'a' * 64}.com", False),
    ],
)
def test_email_validation(email: str, expected: bool) -> None:
    assert valid_email(email) is expected


# ── pre_filter_links tests ────────────────────────────────────────────

BASE = "https://www.example.com/en"


def test_keeps_same_origin_links():
    links = [
        "https://www.example.com/careers",
        "https://example.com/about",
        "https://other-site.com/careers",
        "https://career.example.com/apply",
        "https://jobs.example.com/openings",
    ]
    result = pre_filter_links(links, BASE)
    assert "https://www.example.com/careers" in result
    assert "https://example.com/about" in result
    assert "https://career.example.com/apply" in result
    assert "https://jobs.example.com/openings" in result
    assert "https://other-site.com/careers" not in result


def test_removes_static_assets():
    links = [
        "https://www.example.com/logo.png",
        "https://www.example.com/style.css",
        "https://www.example.com/app.js",
        "https://www.example.com/doc.pdf",
        "https://www.example.com/careers",
    ]
    result = pre_filter_links(links, BASE)
    assert result == ["https://www.example.com/careers"]


def test_removes_junk_path_prefixes():
    links = [
        "https://www.example.com/cdn-cgi/trace",
        "https://www.example.com/wp-content/uploads/img.jpg",
        "https://www.example.com/wp-json/v2/posts",
        "https://www.example.com/static/bundle.js",
        "https://www.example.com/api/users",
        "https://www.example.com/contact",
    ]
    result = pre_filter_links(links, BASE)
    assert result == ["https://www.example.com/contact"]


def test_deduplicates_after_normalization():
    links = [
        "https://www.example.com/careers/",
        "https://www.example.com/careers",
        "https://www.example.com/careers#apply",
        "https://www.example.com/careers?utm_source=google",
    ]
    result = pre_filter_links(links, BASE)
    assert len(result) == 1
    assert result[0] == "https://www.example.com/careers"


def test_strips_non_http_schemes():
    links = [
        "mailto:info@example.com",
        "tel:+1234567890",
        "javascript:void(0)",
        "https://www.example.com/about",
    ]
    result = pre_filter_links(links, BASE)
    assert result == ["https://www.example.com/about"]


def test_preserves_meaningful_query_params():
    links = [
        "https://www.example.com/careers?dept=engineering",
        "https://www.example.com/careers?utm_source=google&dept=engineering",
    ]
    result = pre_filter_links(links, BASE)
    assert len(result) == 1
    assert "dept=engineering" in result[0]
    assert "utm_source" not in result[0]


def test_empty_input():
    assert pre_filter_links([], BASE) == []


def test_all_external_links():
    links = [
        "https://facebook.com/example",
        "https://twitter.com/example",
        "https://linkedin.com/company/example",
    ]
    assert pre_filter_links(links, BASE) == []


def _data_uri(html: str) -> str:
    """Encode an HTML string as a navigable data URI."""
    return f"data:text/html,{urllib.parse.quote(html)}"

async def test_extract_emails(tab: Tab):
    """All email types on one page are routed to the correct category."""
    expected_job_emails = ["careers@acme.com", "jobs@acme.com", "hr@acme.com", 
                           "recruitment@acme.com", "talent@acme.com"]
    expected_contact_emails = ["info@acme.com", "contact@acme.com", "hello@acme.com", 
                               "office@acme.com", "hi@acme.com", "mail@acme.com"]
    excluded_emails = ["support@acme.com", "noreply@acme.com", "sales@acme.com", 
        "billing@acme.com", "legal@acme.com", "webmaster@acme.com", "yourdata@acme.com", 
        "admin@acme.com"]

    html = _data_uri(f"""<!DOCTYPE html>
        <html><head><title>ACME Corp - Contact Us</title></head>
        <body>
        <h2>Job emails</h2>
        <p>{", ".join(expected_job_emails)}</p>

        <h2>Contact emails</h2>
        <p>{", ".join(expected_contact_emails)}</p>

        <h2>Excluded emails</h2>
        <p>{", ".join(excluded_emails)}</p>
        </body></html>""")

    await tab.go_to(html)
  
    job_emails, contact_emails = await extract_emails(tab)

    for email in expected_job_emails:
        assert email in job_emails, f"Expected '{email}' in job_emails"

    for email in expected_contact_emails:
        assert email in contact_emails, f"Expected '{email}' in contact_emails"

    for email in excluded_emails:
        assert email not in job_emails, f"'{email}' must not appear in job_emails"
        assert email not in contact_emails, f"'{email}' must not appear in contact_emails"

    overlap = set(job_emails) & set(contact_emails)
    assert not overlap, f"Emails appeared in both categories: {overlap}"