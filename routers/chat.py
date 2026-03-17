"""
routers/chat.py — Handle user chat messages with streaming and skill detection.

Features:
- Streaming response via SSE
- Skill usage detection and display
- Thinking process unfold/collapse
"""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent.engine import get_agent
from typing import AsyncGenerator

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    skill_used: bool = False
    thinking: list = []


async def stream_chat_response(message: str) -> AsyncGenerator[str, None]:
    """
    Stream chat response with SSE format.

    Event types:
    - event: thinking_start  - Agent starts thinking/tool calling
    - event: thinking        - Thinking content
    - event: skill_used      - Whether web-crawler skill was invoked
    - event: token           - Response tokens (streaming)
    - event: done            - Stream complete
    - event: error           - Error occurred
    """
    if not message.strip():
        yield f"event: error\ndata: {json.dumps({'detail': 'Message cannot be empty'})}\n\n"
        return

    try:
        agent = get_agent()

        # Track if skill is used
        skill_used = False
        thinking_steps = []

        # Send initial event
        yield f"event: thinking_start\ndata: {json.dumps({'status': 'analyzing'})}\n\n"

        # Use astream for streaming response
        async for chunk in agent.astream(
            {"messages": [{"role": "user", "content": message}]},
            stream_mode=["messages", "values"]
        ):
            # Check for tool calls (skill usage)
            if isinstance(chunk, tuple) and len(chunk) == 2:
                msg, metadata = chunk

                # Check if this is a tool call
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    skill_used = True
                    for tc in msg.tool_calls:
                        thinking_steps.append({
                            'type': 'tool_call',
                            'name': tc.get('name', 'unknown'),
                            'args': tc.get('args', {})
                        })
                        yield f"event: thinking\ndata: {json.dumps({'type': 'tool_call', 'name': tc.get('name'), 'args': tc.get('args')})}\n\n"

                # Check for tool response
                if hasattr(msg, 'name') and msg.name:
                    thinking_steps.append({
                        'type': 'tool_result',
                        'name': msg.name,
                        'content': str(msg.content)[:500] if msg.content else ''
                    })
                    yield f"event: thinking\ndata: {json.dumps({'type': 'tool_result', 'name': msg.name})}\n\n"

                # Stream assistant response tokens
                if hasattr(msg, 'type') and msg.type == 'ai' and msg.content:
                    yield f"event: token\ndata: {json.dumps({'content': str(msg.content)})}\n\n"
                elif isinstance(msg, dict) and msg.get('role') == 'assistant':
                    content = msg.get('content', '')
                    if content:
                        yield f"event: token\ndata: {json.dumps({'content': str(content)})}\n\n"

        # Send skill usage info
        yield f"event: skill_used\ndata: {json.dumps({'skill_used': skill_used, 'skill_name': 'web-crawler' if skill_used else None})}\n\n"

        # Send complete thinking process
        yield f"event: thinking_complete\ndata: {json.dumps({'thinking': thinking_steps})}\n\n"

        # Stream complete
        yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"

    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Non-streaming chat endpoint for backward compatibility.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        agent = get_agent()

        skill_used = False
        thinking_steps = []
        full_response = []

        result = agent.invoke({
            "messages": [{"role": "user", "content": request.message}]
        })

        # Check if tool was called
        messages = result.get("messages", [])
        for msg in messages:
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                skill_used = True
                for tc in msg.tool_calls:
                    thinking_steps.append({
                        'type': 'tool_call',
                        'name': tc.get('name', 'unknown'),
                        'args': tc.get('args', {})
                    })
            if hasattr(msg, 'name') and msg.name:
                thinking_steps.append({
                    'type': 'tool_result',
                    'name': msg.name,
                    'content': str(msg.content)[:500] if msg.content else ''
                })

        # Extract final response
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'ai':
                return ChatResponse(
                    reply=msg.content,
                    skill_used=skill_used,
                    thinking=thinking_steps
                )
            if isinstance(msg, dict) and msg.get('role') == 'assistant':
                return ChatResponse(
                    reply=msg.get('content', ''),
                    skill_used=skill_used,
                    thinking=thinking_steps
                )

        raise HTTPException(status_code=500, detail="No reply from agent")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint with SSE.

    Returns Server-Sent Events with:
    - thinking_start: Agent starts processing
    - thinking: Tool calls and intermediate steps
    - skill_used: Whether web-crawler was invoked
    - token: Response content tokens
    - done: Stream complete
    """
    return StreamingResponse(
        stream_chat_response(request.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
