"""
routers/chat.py — Handle user chat messages.

Receives a message from the frontend, passes it to the agent,
and returns the agent's response.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agent.engine import get_agent

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Receive a user message, run it through the deepagent, return the reply.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        agent = get_agent()
        result = agent.invoke({
            "messages": [
                {"role": "user", "content": request.message}
            ]
        })

        # Extract the last assistant message from the result
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai":
                return ChatResponse(reply=msg.content)
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                return ChatResponse(reply=msg["content"])

        raise HTTPException(status_code=500, detail="No reply from agent")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
