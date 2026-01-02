from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
import json
import httpx

from sqlalchemy.orm import Session
from app.services.ollama import OllamaService
from app.database import get_db
from app.models import ChatSession, ChatMessage
from app.tools import tool_registry

router = APIRouter()


# Tool executor for LLM tool calls
async def execute_tool(name: str, arguments: dict):
    """Execute a tool by name and return the result."""
    return await tool_registry.execute(name, arguments)


@router.get("/models")
async def list_models():
    """List available Ollama models for selection."""
    ollama = OllamaService()
    try:
        models = await ollama.list_models()
        return {
            "models": [
                {
                    "name": m["name"],
                    "size": m.get("size", 0),
                    "parameter_size": m.get("details", {}).get("parameter_size", ""),
                    "quantization": m.get("details", {}).get("quantization_level", ""),
                }
                for m in models
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ChatContext(str, Enum):
    GENERAL = "general"
    MONITORING = "monitoring"
    PROJECTS = "projects"


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: str
    context: ChatContext = ChatContext.GENERAL
    history: Optional[List[ChatMessage]] = None
    model: Optional[str] = None  # Optional model override for A/B testing


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_calls: Optional[List[dict]] = None


# System prompts for different contexts
SYSTEM_PROMPTS = {
    ChatContext.GENERAL: """You are Jarvis, an AI assistant for lab monitoring and management.
You have access to tools to query real data about the lab environment:
- list_servers: Get all monitored servers
- get_server_metrics: Get current CPU, memory, GPU metrics for a server
- get_metric_history: Get historical metrics
- list_projects: Get all registered projects
- web_search: Search the web for information

IMPORTANT: When asked about servers, metrics, or lab status, ALWAYS use the appropriate tool to get real data. Never make up information.

Be concise and helpful. Format responses in markdown when appropriate.""",

    ChatContext.MONITORING: """You are Jarvis, focused on server monitoring and infrastructure.
You have access to tools to query real metrics:
- list_servers: Get all servers with their status
- get_server_metrics: Get current metrics (CPU, memory, disk, GPU, temperature)
- get_metric_history: Get historical data and averages

IMPORTANT: ALWAYS use these tools when asked about server status, metrics, or performance. Never guess or make up data.

Be technical and precise. Reference specific metrics from tool results.""",

    ChatContext.PROJECTS: """You are Jarvis, focused on project management and code analysis.
You have access to tools to query project information:
- list_projects: Get all registered projects with tech stacks
- get_project_details: Get detailed info about a specific project
- search_projects: Search projects by technology or name

IMPORTANT: ALWAYS use these tools when asked about projects. Never make up project information.

Be specific and reference actual project details from tool results.""",
}


def get_or_create_session(db: Session, session_id: str, context: str) -> ChatSession:
    """Get existing chat session or create a new one."""
    session = db.query(ChatSession).filter_by(session_id=session_id).first()
    if not session:
        session = ChatSession(session_id=session_id, context=context)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def save_message(db: Session, chat_session: ChatSession, role: str, content: str, tool_calls: dict = None):
    """Save a chat message to the database."""
    message = ChatMessage(
        session_id=chat_session.id,
        role=role,
        content=content,
        tool_calls=tool_calls
    )
    db.add(message)
    db.commit()
    return message


def get_tools_for_context(context: ChatContext) -> list:
    """Get appropriate tools based on chat context."""
    all_tools = tool_registry.to_ollama_format()

    # Define tool sets for each context
    MONITORING_TOOLS = [
        "web_search",
        "list_servers",
        "get_server_metrics",
        "get_metric_history",
    ]

    PROJECT_TOOLS = [
        "web_search",
        "list_projects",
        "get_project_details",
        "search_projects",
    ]

    if context == ChatContext.GENERAL:
        # General context gets all tools
        return all_tools
    elif context == ChatContext.MONITORING:
        # Monitoring context gets server/metrics tools
        return [t for t in all_tools if t["function"]["name"] in MONITORING_TOOLS]
    elif context == ChatContext.PROJECTS:
        # Projects context gets project tools
        return [t for t in all_tools if t["function"]["name"] in PROJECT_TOOLS]

    return all_tools


@router.post("/message")
async def send_message(request: ChatRequest, db: Session = Depends(get_db)):
    """Send a chat message and get a response with tool calling support."""
    ollama = OllamaService()

    system_prompt = SYSTEM_PROMPTS.get(request.context, SYSTEM_PROMPTS[ChatContext.GENERAL])
    tools = get_tools_for_context(request.context)

    # Build message history
    messages = [{"role": "system", "content": system_prompt}]

    if request.history:
        for msg in request.history:
            messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": request.message})

    try:
        # Use tool-enabled chat if tools are available
        if tools:
            response = await ollama.chat_with_tools(messages, tools, execute_tool)
        else:
            response = await ollama.chat(messages, model=request.model)

        # Try to save to database (non-blocking)
        try:
            chat_session = get_or_create_session(db, request.session_id, request.context.value)
            save_message(db, chat_session, "user", request.message)
            save_message(db, chat_session, "assistant", response)
        except Exception as db_error:
            print(f"Failed to save to database: {db_error}")

        return ChatResponse(
            response=response,
            session_id=request.session_id,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message/stream")
async def stream_message(request: ChatRequest, db: Session = Depends(get_db)):
    """Send a chat message and stream the response with tool support."""
    ollama = OllamaService()

    system_prompt = SYSTEM_PROMPTS.get(request.context, SYSTEM_PROMPTS[ChatContext.GENERAL])
    tools = get_tools_for_context(request.context)

    messages = [{"role": "system", "content": system_prompt}]

    if request.history:
        for msg in request.history:
            messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": request.message})

    # Track full response for saving to DB
    full_response = []

    async def generate():
        nonlocal full_response

        # If tools available, check if LLM wants to use them first
        if tools:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                    payload = {
                        "model": request.model or ollama.model,
                        "messages": messages,
                        "stream": False,
                        "tools": tools,
                    }

                    response = await client.post(
                        f"{ollama.base_url}/api/chat",
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()

                    message = data.get("message", {})
                    tool_calls = message.get("tool_calls", [])

                    if tool_calls:
                        # Execute tool calls
                        yield f"data: {json.dumps({'content': 'Checking lab data... '})}\n\n"
                        full_response.append("Checking lab data... ")

                        tool_results = []
                        for tool_call in tool_calls:
                            function = tool_call.get("function", {})
                            name = function.get("name")
                            arguments = function.get("arguments", {})

                            result = await execute_tool(name, arguments)
                            tool_results.append({
                                "role": "tool",
                                "content": json.dumps(result),
                            })

                        # Add tool results and stream final response
                        messages.append(message)
                        messages.extend(tool_results)

                        async for chunk in ollama.chat_stream(messages, model=request.model):
                            full_response.append(chunk)
                            yield f"data: {json.dumps({'content': chunk})}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    elif message.get("content"):
                        # No tools called, stream the content
                        content = message.get("content", "")
                        full_response.append(content)
                        yield f"data: {json.dumps({'content': content})}\n\n"
                        yield "data: [DONE]\n\n"
                        return
            except Exception as e:
                print(f"Tool calling failed: {e}")
                # Fall through to regular streaming

        # Regular streaming without tools
        async for chunk in ollama.chat_stream(messages, model=request.model):
            full_response.append(chunk)
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    async def stream_and_save():
        async for chunk in generate():
            yield chunk
        # Save to database after streaming completes
        try:
            chat_session = get_or_create_session(db, request.session_id, request.context.value)
            save_message(db, chat_session, "user", request.message)
            if full_response:
                save_message(db, chat_session, "assistant", "".join(full_response))
        except Exception as db_error:
            print(f"Failed to save to database: {db_error}")

    return StreamingResponse(
        stream_and_save(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/sessions")
async def list_sessions(db: Session = Depends(get_db)):
    """List all chat sessions."""
    sessions = db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()
    return {
        "sessions": [
            {
                "id": s.id,
                "session_id": s.session_id,
                "context": s.context,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "message_count": len(s.messages) if s.messages else 0,
            }
            for s in sessions
        ]
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: Session = Depends(get_db)):
    """Get chat history for a session."""
    session = db.query(ChatSession).filter_by(session_id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = db.query(ChatMessage).filter_by(session_id=session.id).order_by(ChatMessage.created_at).all()

    return {
        "session_id": session.session_id,
        "context": session.context,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "tool_calls": m.tool_calls,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete a chat session and all its messages."""
    session = db.query(ChatSession).filter_by(session_id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete all messages first
    db.query(ChatMessage).filter_by(session_id=session.id).delete()

    # Delete the session
    db.delete(session)
    db.commit()

    return {"status": "deleted", "session_id": session_id}
