import json
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database import get_db
from app.models import ChatMessage, ChatSession
from app.services.openai_service import OpenAIService
from app.services.work_notes import WorkNotesService
from app.tools import tool_registry

logger = get_logger(__name__)

router = APIRouter()


# Tool executor for LLM tool calls
async def execute_tool(name: str, arguments: dict):
    """Execute a tool by name and return the result."""
    return await tool_registry.execute(name, arguments)


@router.get("/models")
async def list_models():
    """List available OpenAI models for selection."""
    openai_service = OpenAIService()
    try:
        models = await openai_service.list_models()
        return {
            "models": [
                {
                    "name": m["name"],
                    "owned_by": m.get("owned_by", ""),
                    "created": m.get("created", 0),
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
    NETWORK = "network"
    ACTIONS = "actions"
    HOME = "home"
    JOURNAL = "journal"
    WORK = "work"


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: str
    context: ChatContext = ChatContext.GENERAL
    history: Optional[list[ChatMessage]] = None
    model: Optional[str] = None  # Optional model override for A/B testing


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_calls: Optional[list[dict]] = None


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
    ChatContext.NETWORK: """You are Jarvis, focused on network device monitoring and management.
You have access to tools for network operations:
- list_network_devices: Get all monitored network devices (switches, routers, APs)
- get_network_device_metrics: Get current metrics for a specific device
- get_port_status: Get switch port status, VLAN, and traffic info
- get_network_topology: Get network device connections
- set_port_state: Enable or disable a switch port (requires confirmation)
- set_port_vlan: Change port VLAN assignment (requires confirmation)

IMPORTANT: ALWAYS use these tools when asked about network devices. Destructive actions require user confirmation.

Be technical and precise about network information.""",
    ChatContext.ACTIONS: """You are Jarvis, focused on infrastructure automation and action management.
You have access to tools for infrastructure actions:
- restart_service: Restart a systemd service (requires confirmation)
- reboot_server: Reboot a server (requires confirmation)
- get_service_status: Check service status
- execute_command: Run read-only commands on servers

You can also schedule actions:
- schedule_action: Schedule an action for later or with conditions

IMPORTANT: Destructive actions (reboot, restart) require user confirmation before execution.
Always explain what an action will do before executing it.

Be clear about risks and affected resources.""",
    ChatContext.HOME: """You are Jarvis, your personal home automation assistant.
You have access to tools for smart home control and monitoring:

**Device Monitoring:**
- list_home_devices: Get all smart home devices (Ring, appliances, thermostats, media)
- get_home_device_status: Get detailed status of a specific device
- get_home_events: Get recent events (doorbell rings, motion alerts, cycle completions)
- get_thermostat_status: Check thermostat temperature, humidity, and mode
- get_now_playing: See what's playing on Apple TV or HomePod
- get_appliance_status: Check washer, dryer, dishwasher status

**Device Control:**
- set_thermostat: Adjust temperature or HVAC mode
- control_media: Play, pause, skip, or adjust volume on Apple TV/HomePod
- start_appliance: Start a washer/dryer/dishwasher cycle (requires confirmation)
- stop_appliance: Stop or pause a running appliance
- ring_snapshot: Get a snapshot from Ring doorbell/camera

IMPORTANT:
- ALWAYS use tools to get real device data. Never make up device states.
- Starting appliances requires user confirmation to ensure they're loaded.
- Be proactive about notifying about events like completed cycles or doorbell rings.

Be helpful and conversational. Anticipate needs based on device states.""",
    ChatContext.JOURNAL: """You are Jarvis, a personal journaling companion and life assistant.
You have access to tools to help with journaling and reflection:

**Journal Tools:**
- search_journal: Search through past journal entries using semantic similarity
- get_recent_entries: Get entries from the last N days for context

You are talking with your user who keeps a personal journal. You have access to their journal history
and can help them:
- Reflect on their experiences and feelings
- Identify patterns in their life and emotions
- Track personal growth over time
- Provide thoughtful insights based on their entries
- Ask meaningful follow-up questions
- Offer perspective and encouragement

IMPORTANT:
- Reference past journal entries when relevant to show you remember and care
- Be warm, supportive, and conversational
- Help identify patterns across entries (mood trends, recurring themes)
- Respect the personal nature of journaling - be empathetic
- At the end of meaningful conversations, offer to generate a journal summary

When users share thoughts or experiences, engage thoughtfully and help them process their feelings.""",
    ChatContext.WORK: """You are Jarvis, a professional work assistant for managing customer accounts, work notes, and the user's profile.

You help track customer interactions, meetings, calls, and activities. You have access to tools for:

**Account Management:**
- search_accounts: Find existing customer/client accounts by name
- list_accounts: See all accounts
- create_account: Create new customer accounts
- update_account: Update account info, add contacts, add aliases

**Note Taking:**
- add_work_note: Add notes about meetings, calls, tasks, etc.
- search_work_notes: Search through past notes using semantic similarity
- get_account_context: Get full history and context for an account
- get_recent_activity: See recent notes across all accounts

**User Profile Management:**
- update_user_profile: Update the user's work profile (name, role, company, skills, responsibilities, etc.)
- get_user_profile: View the user's current profile

IMPORTANT - Profile Updates:
When the user shares information about THEMSELVES (not about customers/accounts), use update_user_profile to save it:
- If they share their resume, CV, or bio - extract and save name, role, company, skills, responsibilities
- If they mention their job title, company, expertise - save it to their profile
- If they ask you to "update my profile" or "remember this about me" - use the tool

Example profile interactions:
User: "Here's my resume: John Smith, Solutions Architect at Cisco..."
-> Use update_user_profile(name="John Smith", role="Solutions Architect", company="Cisco", ...)

User: "I'm focused on enterprise networking and security"
-> Use update_user_profile(expertise_areas=["Enterprise Networking", "Security"])

User: "Add Python to my skills"
-> Use update_user_profile(add_expertise="Python")

**Smart Behavior - CRITICAL:**
When the user mentions an account name (like "notes for Covia" or "Covia meeting"), ALWAYS:
1. First use search_accounts to find the account
2. If exact match found (score > 0.9), proceed with the action
3. If partial match or ambiguous, show suggestions and ask which one they meant
4. If no match, ask "I don't see an account called 'X'. Would you like me to create it?"
5. Only create after explicit confirmation

Be professional and efficient. Help organize work information effectively. When adding notes, the system will automatically extract contacts, action items, and tags from the content.""",
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


def save_message(
    db: Session, chat_session: ChatSession, role: str, content: str, tool_calls: dict = None
):
    """Save a chat message to the database."""
    message = ChatMessage(
        session_id=chat_session.id, role=role, content=content, tool_calls=tool_calls
    )
    db.add(message)
    db.commit()
    return message


def get_tools_for_context(context: ChatContext) -> list:
    """Get appropriate tools based on chat context."""
    all_tools = tool_registry.to_openai_format()

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

    NETWORK_TOOLS = [
        "list_network_devices",
        "get_network_device_metrics",
        "get_port_status",
        "get_network_topology",
        "get_network_device_history",
        "set_port_state",
        "set_port_vlan",
    ]

    ACTION_TOOLS = [
        "list_servers",
        "get_service_status",
        "execute_command",
        "restart_service",
        "reboot_server",
    ]

    HOME_TOOLS = [
        "list_home_devices",
        "get_home_device_status",
        "get_home_events",
        "get_thermostat_status",
        "get_now_playing",
        "get_appliance_status",
        "set_thermostat",
        "control_media",
        "start_appliance",
        "stop_appliance",
        "ring_snapshot",
    ]

    JOURNAL_TOOLS = [
        "search_journal",
        "get_recent_entries",
    ]

    WORK_TOOLS = [
        "search_accounts",
        "get_account_context",
        "add_work_note",
        "create_account",
        "search_work_notes",
        "list_accounts",
        "update_account",
        "get_recent_activity",
        "update_user_profile",
        "get_user_profile",
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
    elif context == ChatContext.NETWORK:
        # Network context gets network device tools
        return [t for t in all_tools if t["function"]["name"] in NETWORK_TOOLS]
    elif context == ChatContext.ACTIONS:
        # Actions context gets infrastructure action tools
        return [t for t in all_tools if t["function"]["name"] in ACTION_TOOLS]
    elif context == ChatContext.HOME:
        # Home context gets home automation tools
        return [t for t in all_tools if t["function"]["name"] in HOME_TOOLS]
    elif context == ChatContext.JOURNAL:
        # Journal context gets journal tools
        return [t for t in all_tools if t["function"]["name"] in JOURNAL_TOOLS]
    elif context == ChatContext.WORK:
        # Work context gets work/account tools
        return [t for t in all_tools if t["function"]["name"] in WORK_TOOLS]

    return all_tools


@router.post("/message")
async def send_message(request: ChatRequest, db: Session = Depends(get_db)):
    """Send a chat message and get a response with tool calling support."""
    openai_service = OpenAIService()

    system_prompt = SYSTEM_PROMPTS.get(request.context, SYSTEM_PROMPTS[ChatContext.GENERAL])
    tools = get_tools_for_context(request.context)

    # Inject user profile for work context
    if request.context == ChatContext.WORK:
        work_service = WorkNotesService(db)
        profile_context = work_service.build_profile_context()
        if profile_context:
            system_prompt = f"{system_prompt}\n\n{profile_context}"

    # Build message history
    messages = [{"role": "system", "content": system_prompt}]

    if request.history:
        for msg in request.history:
            messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": request.message})

    try:
        # Use tool-enabled chat if tools are available
        if tools:
            response = await openai_service.chat_with_tools(
                messages, tools, execute_tool, model=request.model
            )
        else:
            response = await openai_service.chat(messages, model=request.model)

        # Try to save to database (non-blocking)
        try:
            chat_session = get_or_create_session(db, request.session_id, request.context.value)
            save_message(db, chat_session, "user", request.message)
            save_message(db, chat_session, "assistant", response)
        except Exception as db_error:
            logger.warning(
                "database_save_failed", error=str(db_error), session_id=request.session_id
            )

        return ChatResponse(
            response=response,
            session_id=request.session_id,
        )
    except Exception as e:
        logger.exception("chat_message_failed", context=request.context.value)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message/stream")
async def stream_message(request: ChatRequest, db: Session = Depends(get_db)):
    """Send a chat message and stream the response with tool support."""
    openai_service = OpenAIService()

    system_prompt = SYSTEM_PROMPTS.get(request.context, SYSTEM_PROMPTS[ChatContext.GENERAL])
    tools = get_tools_for_context(request.context)

    # Inject user profile for work context
    if request.context == ChatContext.WORK:
        work_service = WorkNotesService(db)
        profile_context = work_service.build_profile_context()
        if profile_context:
            system_prompt = f"{system_prompt}\n\n{profile_context}"

    messages = [{"role": "system", "content": system_prompt}]

    if request.history:
        for msg in request.history:
            messages.append({"role": msg.role, "content": msg.content})

    messages.append({"role": "user", "content": request.message})

    # Track full response for saving to DB
    full_response = []

    async def generate():
        nonlocal full_response

        # If tools available, use tool-enabled streaming
        if tools:
            try:
                yield f"data: {json.dumps({'content': ''})}\n\n"  # Initial connection

                async for chunk in openai_service.chat_with_tools_stream(
                    messages, tools, execute_tool, model=request.model
                ):
                    full_response.append(chunk)
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                yield "data: [DONE]\n\n"
                return
            except Exception as e:
                logger.warning("tool_calling_failed", error=str(e), context=request.context.value)
                # Fall through to regular streaming

        # Regular streaming without tools
        async for chunk in openai_service.chat_stream(messages, model=request.model):
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
            logger.warning(
                "database_save_failed", error=str(db_error), session_id=request.session_id
            )

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

    messages = (
        db.query(ChatMessage)
        .filter_by(session_id=session.id)
        .order_by(ChatMessage.created_at)
        .all()
    )

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
        ],
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
