"""
fetch.py — Download HTML and take screenshots.

Two main responsibilities:
1. Fetch page content (static HTML or JS-rendered DOM via Playwright)
2. Take full-page screenshots as fallback

All functions return a dict with a 'status' key so the caller can
decide how to handle failures without catching exceptions everywhere.
"""

import requests
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Static fetch
# ---------------------------------------------------------------------------

def fetch_html(url: str, timeout: int = 15) -> dict:
    """
    Fetch a URL with requests.

    Returns:
        {
            "status": "html" | "file" | "failed",
            "content": <bytes>,
            "content_type": <str>,
            "url": <str>,           # final URL after redirects
            "error": <str>          # only present on failure
        }
    """
    try:
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()

        # Determine if this is an HTML page or a direct file download
        if "text/html" in content_type:
            status = "html"
        else:
            status = "file"

        return {
            "status": status,
            "content": response.content,
            "content_type": content_type,
            "url": response.url,
        }

    except requests.RequestException as e:
        return {
            "status": "failed",
            "content": None,
            "content_type": None,
            "url": url,
            "error": str(e),
        }


def save_file(content: bytes, dest_dir: Path, filename: str) -> Path:
    """
    Save raw bytes to dest_dir/filename.
    Creates dest_dir if it doesn't exist.
    Returns the full path of the saved file.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / filename
    path.write_bytes(content)
    return path


# ---------------------------------------------------------------------------
# Dynamic fetch (JS-rendered pages)
# ---------------------------------------------------------------------------

def fetch_rendered_html(url: str, wait_seconds: int = 2) -> dict:
    """
    Use Playwright to render a JS-heavy page and return the final DOM.

    Call this when fetch_html returns HTML that appears to be an empty shell
    (i.e. BeautifulSoup finds little or no meaningful text content).

    Returns:
        {
            "status": "rendered" | "failed",
            "content": <str>,   # full rendered HTML
            "url": <str>,
            "error": <str>      # only present on failure
        }
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Extra wait for pages with delayed rendering
            if wait_seconds > 0:
                page.wait_for_timeout(wait_seconds * 1000)

            html = page.content()
            browser.close()

        return {
            "status": "rendered",
            "content": html,
            "url": url,
        }

    except Exception as e:
        return {
            "status": "failed",
            "content": None,
            "url": url,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Screenshot (fallback)
# ---------------------------------------------------------------------------

def take_screenshot(url: str, dest_dir: Path) -> dict:
    """
    Take a full-page screenshot using Playwright.

    Use this as a last resort when:
    - fetch_html returns an empty shell AND
    - fetch_rendered_html also fails or still yields no useful content
    - Or when content is canvas/image-rendered and can't be extracted as text

    Returns:
        {
            "status": "screenshot" | "failed",
            "path": <Path>,     # where the screenshot was saved
            "url": <str>,
            "error": <str>      # only present on failure
        }
    """
    try:
        from playwright.sync_api import sync_playwright

        dest_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        path = dest_dir / filename

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.screenshot(path=str(path), full_page=True)
            browser.close()

        return {
            "status": "screenshot",
            "path": path,
            "url": url,
        }

    except Exception as e:
        return {
            "status": "failed",
            "path": None,
            "url": url,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Helper: detect empty shell
# ---------------------------------------------------------------------------

def is_empty_shell(html: str, min_words: int = 50) -> bool:
    """
    Heuristic to detect whether an HTML page is a JS-rendered empty shell.

    Returns True if visible text content is below min_words threshold,
    suggesting the real content is loaded dynamically by JavaScript.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style tags before counting words
    for tag in soup(["script", "style", "meta", "link"]):
        tag.decompose()

    text = soup.get_text(separator=" ")
    word_count = len(text.split())
    return word_count < min_words
