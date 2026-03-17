"""
parse.py — Extract structured content from HTML and screenshots.

Two main responsibilities:
1. Parse HTML → extract text as Markdown, extract links, extract tables
2. Parse screenshots → extract text via OCR (fallback)

All functions return a dict with a 'status' key consistent with fetch.py.
"""

from pathlib import Path
from urllib.parse import urljoin, urlparse


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def parse_html(html: str, base_url: str) -> dict:
    """
    Parse HTML content and extract:
    - Markdown text (main readable content)
    - All links found on the page
    - Tables (as plain text representation)

    Args:
        html:     Raw HTML string (static or rendered)
        base_url: The page's URL, used to resolve relative links

    Returns:
        {
            "status": "ok" | "failed",
            "markdown": <str>,
            "links": [{"url": ..., "text": ...}, ...],
            "tables": [<str>, ...],   # each table as a markdown table string
            "error": <str>            # only present on failure
        }
    """
    try:
        from bs4 import BeautifulSoup
        import markdownify

        soup = BeautifulSoup(html, "html.parser")

        # Remove noise: scripts, styles, navbars, footers, ads
        for tag in soup(["script", "style", "nav", "footer", "aside", "noscript"]):
            tag.decompose()

        # --- Extract tables before converting to markdown ---
        tables = _extract_tables(soup)

        # --- Convert main content to Markdown ---
        # Try to isolate main content area first; fall back to full body
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id="content")
            or soup.find(class_="content")
            or soup.body
        )
        html_for_md = str(main) if main else str(soup)
        markdown = markdownify.markdownify(html_for_md, heading_style="ATX", strip=["img"])
        markdown = _clean_markdown(markdown)

        # --- Extract links ---
        links = _extract_links(soup, base_url)

        return {
            "status": "ok",
            "markdown": markdown,
            "links": links,
            "tables": tables,
        }

    except Exception as e:
        return {
            "status": "failed",
            "markdown": "",
            "links": [],
            "tables": [],
            "error": str(e),
        }


def _extract_links(soup, base_url: str) -> list:
    """
    Extract all <a href> links from the page.
    Resolves relative URLs to absolute using base_url.
    Skips anchors (#), mailto:, javascript:, and empty hrefs.
    """
    links = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()

        # Skip non-navigable hrefs
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue

        # Resolve relative URLs
        absolute = urljoin(base_url, href)

        # Normalize: strip fragment
        parsed = urlparse(absolute)
        normalized = parsed._replace(fragment="").geturl()

        if normalized not in seen:
            seen.add(normalized)
            links.append({
                "url": normalized,
                "text": tag.get_text(strip=True) or "",
                "domain": parsed.netloc,
            })

    return links


def _extract_tables(soup) -> list:
    """
    Extract all <table> elements and convert them to Markdown table strings.
    Returns a list of markdown table strings, one per table found.
    """
    tables = []

    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)

        if not rows:
            continue

        # Build markdown table
        col_count = max(len(row) for row in rows)
        # Pad rows to same width
        padded = [row + [""] * (col_count - len(row)) for row in rows]

        md_rows = []
        md_rows.append("| " + " | ".join(padded[0]) + " |")
        md_rows.append("| " + " | ".join(["---"] * col_count) + " |")
        for row in padded[1:]:
            md_rows.append("| " + " | ".join(row) + " |")

        tables.append("\n".join(md_rows))

    return tables


def _clean_markdown(text: str) -> str:
    """
    Remove excessive blank lines and leading/trailing whitespace
    from markdownify output.
    """
    import re
    # Collapse 3+ consecutive newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Link classification
# ---------------------------------------------------------------------------

def classify_links(links: list, base_url: str, intent: str) -> dict:
    """
    Split links into three buckets based on the user's crawl intent
    and basic heuristics.

    Args:
        links:    Output from _extract_links (list of dicts)
        base_url: The starting URL of this crawl session
        intent:   The user's stated crawl intent (natural language)

    Returns:
        {
            "continue":  [link, ...],   # clearly relevant, crawl these
            "skip":      [link, ...],   # clearly irrelevant, ignore
            "uncertain": [link, ...],   # needs user judgment
        }

    Note: This function applies heuristic rules only. The caller (Claude)
    should apply intent-based reasoning on top of this for the 'uncertain'
    bucket before presenting to the user.
    """
    base_domain = urlparse(base_url).netloc

    result = {"continue": [], "skip": [], "uncertain": []}

    # File extensions that are almost always worth downloading directly
    downloadable_extensions = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv",
        ".zip", ".tar", ".gz", ".mp4", ".mp3", ".png", ".jpg", ".jpeg"
    }

    # Patterns that are almost always noise
    skip_patterns = [
        "/login", "/logout", "/signin", "/signup", "/register",
        "/cart", "/checkout", "/account", "/privacy", "/terms",
        "/cookie", "/subscribe", "/newsletter", "mailto:", "tel:",
        ".css", ".js", ".ico", ".woff", ".woff2", ".ttf",
    ]

    for link in links:
        url = link["url"]
        domain = link["domain"]
        url_lower = url.lower()

        # Skip off-domain links by default (put in uncertain for user to decide)
        if domain != base_domain:
            result["uncertain"].append({**link, "reason": "different domain"})
            continue

        # Skip obvious noise
        if any(pat in url_lower for pat in skip_patterns):
            result["skip"].append(link)
            continue

        # Downloadable files — always worth following
        if any(url_lower.endswith(ext) for ext in downloadable_extensions):
            result["continue"].append(link)
            continue

        # Same domain, not obviously noisy → uncertain, let Claude + user decide
        result["uncertain"].append({**link, "reason": "relevance unclear"})

    return result


# ---------------------------------------------------------------------------
# Screenshot OCR (fallback)
# ---------------------------------------------------------------------------

def parse_screenshot(image_path: Path) -> dict:
    """
    Extract text from a screenshot using OCR (pytesseract).

    Use this when HTML extraction has failed and a screenshot was taken instead.
    Requires: tesseract-ocr system package + pytesseract Python package.

    Install:
        brew install tesseract        # macOS
        apt install tesseract-ocr     # Ubuntu
        pip install pytesseract Pillow

    Returns:
        {
            "status": "ok" | "failed",
            "text": <str>,
            "error": <str>   # only present on failure
        }
    """
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)

        return {
            "status": "ok",
            "text": text.strip(),
        }

    except ImportError:
        return {
            "status": "failed",
            "text": "",
            "error": (
                "pytesseract or Pillow not installed. "
                "Run: pip install pytesseract Pillow && brew install tesseract"
            ),
        }

    except Exception as e:
        return {
            "status": "failed",
            "text": "",
            "error": str(e),
        }
