"""
storage.py — SQLite persistence and session directory management.

Responsibilities:
1. Initialize a crawl session (create directory structure + database)
2. CRUD operations for all tables
3. Session summary query (used by the final report)

All write functions return the inserted row's id so callers can
build foreign key relationships without extra queries.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
# --------------------------------------------------------------------------
# Session initialization
# print current folder path
print("Current folder path:", Path.cwd())
# print parent folder path
output_folder = Path.home() / "Documents/TUV/workspace/skils_output/web-crawler"

print("output folder path:", output_folder)
# ---------------------------------------------------------------------------

def init_session(start_url: str, intent: str, depth_mode: str, base_dir: Path = None) -> dict:
    """
    Create a new crawl session: directory structure + database + first DB record.

    Args:
        base_dir:   User-specified root folder for all crawl results
        start_url:  The URL this session starts from
        intent:     The user's stated crawl intent
        depth_mode: 'manual' | 'auto' | 'depth-limit'

    Returns:
        {
            "session_id":    <int>,
            "session_dir":   <Path>,   # e.g. /base_dir/crawl_20240101_120000/
            "files_dir":     <Path>,   # for downloaded raw files
            "screenshots_dir": <Path>, # for fallback screenshots
            "db_path":       <Path>,   # path to crawl.db
        }
    """
    if base_dir is None:
        base_dir = output_folder
    base_dir = Path(base_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = base_dir / f"crawl_{timestamp}"

    # Create directory structure
    files_dir = session_dir / "files"
    screenshots_dir = session_dir / "screenshots"
    files_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Initialize database
    db_path = session_dir / "crawl.db"
    conn = _connect(db_path)
    _create_tables(conn)

    # Insert session record
    cursor = conn.execute(
        """
        INSERT INTO crawl_session (start_url, intent, depth_mode, started_at)
        VALUES (?, ?, ?, ?)
        """,
        (start_url, intent, depth_mode, datetime.now().isoformat()),
    )
    conn.commit()
    session_id = cursor.lastrowid
    conn.close()

    return {
        "session_id": session_id,
        "session_dir": session_dir,
        "files_dir": files_dir,
        "screenshots_dir": screenshots_dir,
        "db_path": db_path,
    }


def close_session(db_path: Path, session_id: int) -> None:
    """Mark the session as finished by recording the end timestamp."""
    conn = _connect(db_path)
    conn.execute(
        "UPDATE crawl_session SET finished_at = ? WHERE id = ?",
        (datetime.now().isoformat(), session_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def insert_page(
    db_path: Path,
    session_id: int,
    url: str,
    depth: int,
    status: str,
    page_type: str,
) -> int:
    """
    Record a crawled page.

    Args:
        status:    'success' | 'failed' | 'restricted'
        page_type: 'static' | 'dynamic' | 'screenshot'

    Returns:
        page_id (int)
    """
    conn = _connect(db_path)
    cursor = conn.execute(
        """
        INSERT INTO pages (session_id, url, depth, status, page_type, crawled_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (session_id, url, depth, status, page_type, datetime.now().isoformat()),
    )
    conn.commit()
    page_id = cursor.lastrowid
    conn.close()
    return page_id


def get_crawled_urls(db_path: Path, session_id: int) -> set:
    """
    Return the set of all URLs already crawled in this session.
    Used for deduplication — never crawl the same URL twice.
    """
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT url FROM pages WHERE session_id = ?", (session_id,)
    ).fetchall()
    conn.close()
    return {row[0] for row in rows}


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def insert_content(db_path: Path, page_id: int, markdown: str) -> int:
    """
    Save extracted Markdown text for a page.
    Returns content row id.
    """
    conn = _connect(db_path)
    cursor = conn.execute(
        "INSERT INTO content (page_id, markdown) VALUES (?, ?)",
        (page_id, markdown),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def insert_file(db_path: Path, page_id: int, file_type: str, local_path: Path) -> int:
    """
    Record a downloaded file (PDF, image, screenshot, etc.).
    Returns file row id.
    """
    conn = _connect(db_path)
    cursor = conn.execute(
        "INSERT INTO files (page_id, file_type, local_path) VALUES (?, ?, ?)",
        (page_id, file_type, str(local_path)),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------

def insert_links(db_path: Path, from_page_id: int, links: list) -> None:
    """
    Bulk-insert classified links discovered on a page.

    Each link dict should have:
        {
            "url":            <str>,
            "text":           <str>,
            "classification": 'continued' | 'skipped' | 'user_confirmed' | 'user_rejected'
        }
    """
    conn = _connect(db_path)
    conn.executemany(
        """
        INSERT INTO links (from_page_id, url, text, classification)
        VALUES (?, ?, ?, ?)
        """,
        [
            (from_page_id, lnk["url"], lnk.get("text", ""), lnk["classification"])
            for lnk in links
        ],
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Session summary (for final report)
# ---------------------------------------------------------------------------

def get_session_summary(db_path: Path, session_id: int) -> dict:
    """
    Aggregate stats for the final report.

    Returns:
        {
            "start_url":      <str>,
            "intent":         <str>,
            "depth_mode":     <str>,
            "started_at":     <str>,
            "finished_at":    <str>,
            "total_pages":    <int>,
            "successful":     <int>,
            "failed":         <int>,
            "restricted":     <int>,
            "total_files":    <int>,
            "total_links":    <int>,
        }
    """
    conn = _connect(db_path)

    session = conn.execute(
        "SELECT start_url, intent, depth_mode, started_at, finished_at FROM crawl_session WHERE id = ?",
        (session_id,),
    ).fetchone()

    page_stats = conn.execute(
        """
        SELECT
            COUNT(*)                                          AS total,
            SUM(CASE WHEN status = 'success'    THEN 1 END)  AS successful,
            SUM(CASE WHEN status = 'failed'     THEN 1 END)  AS failed,
            SUM(CASE WHEN status = 'restricted' THEN 1 END)  AS restricted
        FROM pages WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()

    total_files = conn.execute(
        """
        SELECT COUNT(*) FROM files
        WHERE page_id IN (SELECT id FROM pages WHERE session_id = ?)
        """,
        (session_id,),
    ).fetchone()[0]

    total_links = conn.execute(
        """
        SELECT COUNT(*) FROM links
        WHERE from_page_id IN (SELECT id FROM pages WHERE session_id = ?)
        """,
        (session_id,),
    ).fetchone()[0]

    conn.close()

    return {
        "start_url":   session[0],
        "intent":      session[1],
        "depth_mode":  session[2],
        "started_at":  session[3],
        "finished_at": session[4],
        "total_pages":  page_stats[0] or 0,
        "successful":   page_stats[1] or 0,
        "failed":       page_stats[2] or 0,
        "restricted":   page_stats[3] or 0,
        "total_files":  total_files or 0,
        "total_links":  total_links or 0,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS crawl_session (
            id          INTEGER PRIMARY KEY,
            start_url   TEXT,
            intent      TEXT,
            depth_mode  TEXT,
            started_at  TIMESTAMP,
            finished_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pages (
            id          INTEGER PRIMARY KEY,
            session_id  INTEGER REFERENCES crawl_session(id),
            url         TEXT,
            depth       INTEGER,
            status      TEXT,
            page_type   TEXT,
            crawled_at  TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS content (
            id          INTEGER PRIMARY KEY,
            page_id     INTEGER REFERENCES pages(id),
            markdown    TEXT
        );

        CREATE TABLE IF NOT EXISTS files (
            id          INTEGER PRIMARY KEY,
            page_id     INTEGER REFERENCES pages(id),
            file_type   TEXT,
            local_path  TEXT
        );

        CREATE TABLE IF NOT EXISTS links (
            id              INTEGER PRIMARY KEY,
            from_page_id    INTEGER REFERENCES pages(id),
            url             TEXT,
            text            TEXT,
            classification  TEXT
        );
    """)
    conn.commit()
