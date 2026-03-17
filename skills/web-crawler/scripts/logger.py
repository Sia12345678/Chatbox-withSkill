"""
logger.py — Crawl session logging.

Writes structured logs to a file in the session directory so the user
can review what happened after a crawl, and Claude can diagnose failures.

Two output targets:
1. crawl_<timestamp>/crawl.log  — human-readable file log
2. console (stdout)             — real-time progress during crawl

Usage:
    from scripts.logger import get_logger
    log = get_logger(session_dir)

    log.info("Starting crawl", url="https://example.com")
    log.success("Page crawled", url="...", depth=1)
    log.warning("Empty shell detected, switching to Playwright", url="...")
    log.error("Failed to fetch page", url="...", error="timeout")
    log.skip("Link skipped", url="...", reason="different domain")
"""

import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Log levels
# ---------------------------------------------------------------------------

LEVELS = {
    "INFO":    {"prefix": "[ INFO    ]", "color": "\033[0m"},      # default
    "SUCCESS": {"prefix": "[ SUCCESS ]", "color": "\033[92m"},     # green
    "WARNING": {"prefix": "[ WARNING ]", "color": "\033[93m"},     # yellow
    "ERROR":   {"prefix": "[ ERROR   ]", "color": "\033[91m"},     # red
    "SKIP":    {"prefix": "[ SKIP    ]", "color": "\033[90m"},     # grey
    "USER":    {"prefix": "[ USER    ]", "color": "\033[94m"},     # blue — awaiting user input
}

RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

class CrawlLogger:
    """
    Simple structured logger for a single crawl session.

    Writes every event to:
    - A log file (always plain text, no color codes)
    - stdout (with color if terminal supports it)
    """

    def __init__(self, session_dir: Path):
        self.log_path = session_dir / "crawl.log"
        self.use_color = sys.stdout.isatty()
        self._write_to_file(f"=== Crawl session started at {datetime.now().isoformat()} ===\n")

    # --- Public log methods ---

    def info(self, message: str, **kwargs):
        self._log("INFO", message, **kwargs)

    def success(self, message: str, **kwargs):
        self._log("SUCCESS", message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log("ERROR", message, **kwargs)

    def skip(self, message: str, **kwargs):
        self._log("SKIP", message, **kwargs)

    def user(self, message: str, **kwargs):
        """Use this when Claude is about to pause and ask the user something."""
        self._log("USER", message, **kwargs)

    def section(self, title: str):
        """Print a visual separator for a new crawl phase."""
        line = f"\n--- {title} ---"
        self._write_to_file(line + "\n")
        print(line)

    def finalize(self):
        """Write closing line to log file."""
        self._write_to_file(f"\n=== Crawl session ended at {datetime.now().isoformat()} ===\n")

    # --- Internal ---

    def _log(self, level: str, message: str, **kwargs):
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_info = LEVELS[level]

        # Build the extra fields string (e.g. url=... depth=... error=...)
        extras = "  ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        plain = f"{timestamp} {level_info['prefix']} {message}"
        if extras:
            plain += f"  |  {extras}"

        # File: plain text
        self._write_to_file(plain + "\n")

        # Console: with color if supported
        if self.use_color:
            colored = f"{level_info['color']}{plain}{RESET}"
        else:
            colored = plain
        print(colored)

    def _write_to_file(self, text: str):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(text)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_logger(session_dir: Path) -> CrawlLogger:
    """
    Create and return a CrawlLogger for the given session directory.
    The log file will be created at session_dir/crawl.log.

    Call this once at the start of a session and pass the logger
    instance to all functions that need it.
    """
    return CrawlLogger(session_dir)
