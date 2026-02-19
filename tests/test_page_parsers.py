import pytest
from smart_apply.page_parsers import html_to_plain_text, infer_company_name, email_valid
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
    assert email_valid(email) is expected
