import pytest
from smart_apply.page_parsers import html_to_plain_text, infer_company_name
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