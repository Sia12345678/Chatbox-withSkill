"""
main.py — FastAPI entry point.

This file does three things:
1. Creates the FastAPI app
2. Registers the chat router so FastAPI knows which
   functions to call for which URLs
3. Serves the frontend HTML file so the browser can load it

Skill configuration is controlled via config.json (hardcoded true/false).
Edit config.json directly to enable/disable skills.

To start the server, run:
    uvicorn main:app --reload --port 8018

Then open your browser at:
    http://localhost:8018 → chat page
"""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from routers import chat

# Create the FastAPI app instance
app = FastAPI(title="PoC Chatbox")

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

# Any request to /chat is handled by routers/chat.py
app.include_router(chat.router)

# ---------------------------------------------------------------------------
# Serve frontend HTML files
# ---------------------------------------------------------------------------

@app.get("/")
async def serve_chat():
    """
    http://localhost:8018 → send the user the chat page.
    """
    return FileResponse("frontend/chat.html")
