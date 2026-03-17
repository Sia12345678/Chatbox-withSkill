---
name: web-crawler
description: >
  A skill for crawling websites and extracting content. Use this skill whenever
  the user wants to scrape a webpage, crawl a site, extract content from URLs,
  download web pages, collect links, or gather data from the internet. Trigger
  this skill even if the user doesn't say "crawl" explicitly — phrases like
  "get me the content from this URL", "scrape this site", "download this page",
  or "find something on the web..." warrant using this skill.
compatibility: "requires bash tool; python packages: requests, playwright, beautifulsoup4, markdownify, Pillow, pytesseract; system: tesseract-ocr (optional, for screenshot fallback)"
---

# Web Crawler Skill

A skill for crawling websites: downloading content, extracting structure, following links intelligently, and storing everything locally with a clean final report.

## Scripts overview

All executable logic lives in `scripts/`. Read the relevant script before calling it.

| Script | Responsibility |
|--------|---------------|
| `scripts/fetch.py` | Fetch HTML (static + Playwright-rendered), download files, take screenshots |
| `scripts/parse.py` | Parse HTML → Markdown + links + tables; OCR screenshots; classify links |
| `scripts/storage.py` | Initialize session directory + SQLite DB; all read/write operations |
| `scripts/logger.py` | Structured logging to file + console throughout the crawl |

For expected output formats by content type, see `references/output_examples.md`.

---

## Step 1: Activation & Intent Capture

When this skill triggers, extract the following from the user's message before doing anything else:

- **Starting URL**: the page to begin crawling
- **Intent**: what the user is actually looking for (e.g. "all PDF reports", "product prices", "article text", "all links about topic X")
- **Save directory**: where to store all crawl results — follow the definition in init_session, save the middle output into the middle folder, and final output into the final folder. if base_dir is not specified, ask the user to specify.

- **Depth mode**: if not specified, ask the user to choose one:
  - `manual` — you present links for user approval at every level
  - `auto` — user approves only the first level; you decide autonomously after that
  - `depth-limit` — user sets a max depth (e.g. 2), you decide autonomously within that limit

If any of these are unclear, ask before proceeding.

Once confirmed, initialize the session:

```python
from scripts.storage import init_session
from scripts.logger import get_logger

session = init_session(start_url, intent, depth_mode, base_dir)
log = get_logger(session["session_dir"])
log.section("Session initialized")
log.info("Starting crawl", url=start_url, mode=depth_mode)
```

---

## Step 2: Crawling a Single Page

For each URL, follow this decision tree. Log every transition so failures are traceable.

### 2a. Try direct fetch

```python
from scripts.fetch import fetch_html, save_file

result = fetch_html(url)
```

- If `result["status"] == "file"` → save it and record in DB, done for this URL:

```python
from scripts.storage import insert_page, insert_file

page_id = insert_page(db_path, session_id, url, depth, status="success", page_type="file")
path = save_file(result["content"], session["files_dir"], filename)
insert_file(db_path, page_id, file_type, path)
log.success("File downloaded", url=url, path=str(path))
```

- If `result["status"] == "html"` → proceed to 2b.
- If `result["status"] == "failed"` → log error, record as failed, move to next URL.

### 2b. Check if HTML is a shell

```python
from scripts.fetch import is_empty_shell, fetch_rendered_html

if is_empty_shell(result["content"].decode("utf-8", errors="ignore")):
    log.warning("Empty shell detected, switching to Playwright", url=url)
    result = fetch_rendered_html(url)
    page_type = "dynamic"
else:
    page_type = "static"
```

If `fetch_rendered_html` also fails → fall through to 2d.

### 2c. Extract content

```python
from scripts.parse import parse_html
from scripts.storage import insert_content, insert_links

html = result["content"] if isinstance(result["content"], str) else result["content"].decode("utf-8", errors="ignore")
parsed = parse_html(html, base_url=url)

page_id = insert_page(db_path, session_id, url, depth, status="success", page_type=page_type)
insert_content(db_path, page_id, parsed["markdown"])
log.success("Page parsed", url=url, words=len(parsed["markdown"].split()))
```

Tables are included in `parsed["tables"]` — append them to the markdown or save separately depending on content type. See `references/output_examples.md` for expected formats.

### 2d. Fallback: screenshot + OCR (nice to have)

If content extraction fails or yields nothing useful:

```python
from scripts.fetch import take_screenshot
from scripts.parse import parse_screenshot

shot = take_screenshot(url, session["screenshots_dir"])
if shot["status"] == "screenshot":
    page_id = insert_page(db_path, session_id, url, depth, status="restricted", page_type="screenshot")
    insert_file(db_path, page_id, "screenshot", shot["path"])
    ocr = parse_screenshot(shot["path"])
    if ocr["status"] == "ok":
        insert_content(db_path, page_id, ocr["text"])
    log.warning("Fallback screenshot used", url=url)
```

---

## Step 3: Link Handling & User Verification

After each page is parsed, classify the discovered links:

```python
from scripts.parse import classify_links

classified = classify_links(parsed["links"], base_url=start_url, intent=intent)
```

`classify_links` applies heuristic rules (domain, noise patterns, file extensions). You then apply **intent-based reasoning** on top: review `classified["uncertain"]` and move links to `continue` or `skip` based on whether they match the user's crawl intent.

Present the uncertain links to the user in this format:

```
Found X links. Classifying based on your intent: "[intent]"

Auto-continuing (Y links): [urls]
Auto-skipping (Z links): [urls]

Please confirm which of these to crawl:
| # | URL | Reason |
|---|-----|--------|
| 1 | ... | ...    |
```

After user confirms, record all links with their final classification:

```python
all_links = (
    [{**lnk, "classification": "continued"}  for lnk in classified["continue"]] +
    [{**lnk, "classification": "skipped"}    for lnk in classified["skip"]] +
    [{**lnk, "classification": "user_confirmed"} for lnk in user_confirmed] +
    [{**lnk, "classification": "user_rejected"}  for lnk in user_rejected]
)
insert_links(db_path, page_id, all_links)
```

---

## Step 4: Depth Control

Deduplicate before queuing any new URL:

```python
from scripts.storage import get_crawled_urls

crawled = get_crawled_urls(db_path, session_id)
queue = [lnk["url"] for lnk in to_continue if lnk["url"] not in crawled]
```

Apply the chosen depth mode:

**`manual`** — before crawling each new level, present the queued URLs and wait for user approval. Do not crawl anything without explicit confirmation.

**`auto`** — after the first-level verification, apply intent-based classification autonomously on all subsequent levels. Only interrupt the user if something is genuinely ambiguous.

**`depth-limit`** — track current depth. At each level classify autonomously. When `current_depth >= max_depth`, stop following links entirely.

---

## Step 5: Storage

Session directory structure (created automatically by `scripts/storage.py/init_session`, find or create the base_dir by the definition of `base_dir` in `storage.py`):

```
<base_dir>/
└── crawl_<timestamp>/
    ├── files/          # downloaded raw files (PDFs, images, etc.)
    ├── screenshots/    # fallback screenshots
    ├── crawl.db        # SQLite database
    └── crawl.log       # full session log
```

All DB operations are in `scripts/storage.py`. Save content incrementally as each page is crawled — don't batch at the end.

---

## Step 6: Final Report

When crawling is complete, close the session and generate the report:

```python
from scripts.storage import close_session, get_session_summary

close_session(db_path, session_id)
log.finalize()
summary = get_session_summary(db_path, session_id)
```

Present to the user in this format:

```
## Crawl Complete ✓

**Session directory**: <base_dir>/crawl_<timestamp>/
**Database**:          <base_dir>/crawl_<timestamp>/crawl.db
**Files**:             <base_dir>/crawl_<timestamp>/files/
**Log**:               <base_dir>/crawl_<timestamp>/crawl.log

### Stats
- Pages crawled:              X
- Successful:                 X
- Failed:                     X
- Restricted (fallback used): X
- Files downloaded:           X
- Total links found:          X

### What was saved
- [list key files or content highlights if noteworthy]
```

---

## Dependencies

Install before first use:

```bash
pip install requests playwright beautifulsoup4 markdownify Pillow pytesseract
playwright install chromium

# OCR engine (only needed for screenshot fallback):
brew install tesseract        # macOS
apt install tesseract-ocr     # Ubuntu/Debian
```

`sqlite3` is part of Python's standard library — no install needed.
