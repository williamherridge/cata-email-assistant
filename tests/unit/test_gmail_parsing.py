from src.gmail_ingest.parsing import extract_body_html, extract_body_text, sanitize_email_html


def test_extract_body_text_preserves_html_structure_for_html_only_payload():
    payload = {
        "mimeType": "text/html",
        "body": {
            "data": "PGRpdj48cD5DYXB0YWluIE5hbWU8L3A-PHA-SmFtaWUgTGF5PC9wPjxwPkZhY2lsaXR5PC9wPjxwPkFuZGVyc29uIEhpZ2ggU2Nob29sPC9wPjwvZGl2Pg=="
        },
    }

    body_text = extract_body_text(payload)

    assert "Captain Name\n\nJamie Lay" in body_text
    assert "Facility\n\nAnderson High School" in body_text


def test_extract_body_html_returns_decoded_html():
    payload = {
        "mimeType": "text/html",
        "body": {"data": "PHA-SGVsbG88YnI-V29ybGQ8L3A-"},
    }

    body_html = extract_body_html(payload)

    assert body_html == "<p>Hello<br>World</p>"


def test_sanitize_email_html_strips_unsafe_tags_and_keeps_basic_markup():
    html = (
        "<html><head><title>Ignore</title></head><body>"
        "<p>Hello <strong>there</strong></p>"
        "<img src='https://tracker.example/pixel.gif'>"
        "<script>alert(1)</script>"
        "<a href='mailto:test@example.com'>Email</a>"
        "</body></html>"
    )

    rendered = sanitize_email_html(html)

    assert "<p>Hello <strong>there</strong></p>" in rendered
    assert "tracker.example" not in rendered
    assert "script" not in rendered
    assert 'href="mailto:test@example.com"' in rendered
