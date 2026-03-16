import re
import unicodedata
from urllib.parse import urlparse

import requests
import trafilatura

from app.core.config import settings
from app.schemas.extract import ExtractResponse


def extract_content(url: str) -> ExtractResponse:
    try:
        downloaded = _download_url(url)
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to fetch URL: {exc}") from exc

    metadata = trafilatura.extract_metadata(downloaded)
    markdown = trafilatura.extract(
        downloaded,
        url=url,
        output_format="markdown",
        include_links=True,
        include_images=False,
        favor_recall=True,
    )

    if not markdown:
        raise RuntimeError("Failed to extract readable content from the page.")

    markdown = _clean_markdown(markdown)

    title = metadata.title if metadata and metadata.title else None
    published_date = metadata.date if metadata and metadata.date else None
    domain = urlparse(url).netloc

    return ExtractResponse(
        title=title,
        url=url,
        markdown=markdown,
        published_date=published_date,
        domain=domain,
    )


def _download_url(url: str) -> str:
    session = requests.Session()

    # First try the minimal request; some sites work fine without browser-like headers.
    primary_headers = {"User-Agent": settings.user_agent}
    response = session.get(url, headers=primary_headers, timeout=settings.request_timeout)

    if response.status_code == 403:
        fallback_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        response = session.get(url, headers=fallback_headers, timeout=settings.request_timeout)

    response.raise_for_status()
    return _decode_response_content(response)


def _decode_response_content(response: requests.Response) -> str:
    encodings = [
        response.encoding,
        response.apparent_encoding,
        "utf-8",
        "gb18030",
        "gbk",
        "big5",
    ]

    content = response.content
    best_text = ""
    best_score = float("-inf")
    seen: set[str] = set()

    for encoding in encodings:
        if not encoding:
            continue
        normalized = encoding.lower()
        if normalized in seen:
            continue
        seen.add(normalized)

        try:
            decoded = content.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            continue

        score = _score_decoded_text(decoded)
        if score > best_score:
            best_score = score
            best_text = decoded

    if best_text:
        return best_text

    return content.decode("utf-8", errors="replace")


def _score_decoded_text(text: str) -> float:
    if not text:
        return float("-inf")

    replacement_count = text.count("\ufffd")
    mojibake_markers = (
        text.count("Ã")
        + text.count("å")
        + text.count("æ")
        + text.count("ç")
        + text.count("ï¼")
        + text.count("â")
    )
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")

    return (cjk_count * 2) - (replacement_count * 10) - (mojibake_markers * 3)


def _clean_markdown(markdown: str) -> str:
    # Remove common terminal escape sequences and other control characters while
    # preserving tabs and line breaks so markdown structure stays readable.
    markdown = re.sub(r"\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)", "", markdown)
    markdown = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", markdown)
    markdown = re.sub(r"\x1B[@-Z\\-_]", "", markdown)
    markdown = markdown.replace("\x1b", "")
    markdown = "".join(
        char
        for char in markdown
        if char in {"\n", "\t"} or not unicodedata.category(char).startswith("C")
    )
    markdown = re.sub(r"\[[0-9:;]{2,}[A-Za-z]", "", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip()
