from requests import Response

from app.extractors.content import _decode_response_content


def test_decode_response_content_prefers_cjk_readable_text_over_mojibake() -> None:
    response = Response()
    response._content = "英维克2024年年报解读".encode("utf-8")
    response.encoding = "ISO-8859-1"

    decoded = _decode_response_content(response)

    assert "英维克2024年年报解读" in decoded
