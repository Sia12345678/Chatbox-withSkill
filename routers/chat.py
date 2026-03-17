"""
routers/chat.py — Handle user chat messages with skill detection.

Features:
- Skill usage detection and display
- Thinking process tracking
"""

import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from agent.engine import get_agent

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    skill_used: bool = False
    thinking: list = []


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Receive a user message, run it through the deepagent, return the reply.
    Includes skill usage detection and thinking process.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        agent = get_agent()

        skill_used = False
        thinking_steps = []

        # Use the agent's invoke method with callbacks to track tool usage
        result = agent.invoke({
            "messages": [{"role": "user", "content": request.message}]
        })

        # Analyze the message history to detect skill usage
        messages = result.get("messages", [])

        for msg in messages:
            # Check for tool calls (indicates skill usage)
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                skill_used = True
                for tc in msg.tool_calls:
                    thinking_steps.append({
                        'type': 'tool_call',
                        'name': tc.get('name', 'unknown'),
                        'args': tc.get('args', {})
                    })

            # Check for tool responses
            if hasattr(msg, 'name') and msg.name:
                thinking_steps.append({
                    'type': 'tool_result',
                    'name': msg.name,
                    'content': str(msg.content)[:500] if msg.content else ''
                })

        # Extract final response
        reply = ""
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'ai':
                reply = msg.content
                break
            if isinstance(msg, dict) and msg.get('role') == 'assistant':
                reply = msg.get('content', '')
                break

        if not reply:
            raise HTTPException(status_code=500, detail="No reply from agent")

        return ChatResponse(
            reply=reply,
            skill_used=skill_used,
            thinking=thinking_steps
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming endpoint - currently falls back to non-streaming.
    """
    return await chat(request)
