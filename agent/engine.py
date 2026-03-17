"""
agent/engine.py — Create and return a deepagent instance.

Reads config.json to determine which skills are enabled,
then passes the appropriate skills directory to create_deep_agent.
"""

import json
from pathlib import Path
from deepagents import create_deep_agent

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
SKILLS_DIR = str(Path(__file__).parent.parent / "skills")


def get_agent():
    """
    Create a deepagent instance with skills loaded based on config.json.

    Called once per chat request — each request gets a fresh agent
    with the latest skill config applied.
    """
    config = _read_config()

    skills = []
    if config.get("web-crawler", False):
        skills = [SKILLS_DIR]

    agent = create_deep_agent(
        model="deepseek-chat",
        skills=skills if skills else None,
        system_prompt="You are a helpful assistant.",
    )

    return agent


def _read_config() -> dict:
    """Read and return the current skill config from config.json."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"web-crawler": False}
