import io
from reportlab.pdfgen import canvas

from app import robust_parse_multiline, SCANNING_ID_REGEX, extract_text_from_pdf


def test_robust_parse_multiline_basic():
    text = """
    1234-5678 Expected Item A
    More details about item A
    99999999 | Something else
    """
    data = robust_parse_multiline(text)
    assert "1234-5678" in data
    assert any("Expected Item A" in s for s in data["1234-5678"])
    assert "99999999" in data


def test_scanning_id_regex_matches():
    samples = ["1234-5678", "12345678", "0001-2345-6"]
    for s in samples:
        assert SCANNING_ID_REGEX.search(s)


def test_extract_text_from_pdf_minimal():
    # Generate in-memory PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 750, "Hello 1234-5678 from PDF")
    p.showPage()
    p.save()
    buffer.seek(0)
    pdf_bytes = buffer.read()

    extracted = extract_text_from_pdf(pdf_bytes)
    assert extracted is not None
    assert "Hello" in extracted
    assert "1234-5678" in extracted
