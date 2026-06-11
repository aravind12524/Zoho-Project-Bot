import os
import httpx
import secrets

from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()




from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from zoho_client import ZohoClient
from agents import Router, QueryAgent, ActionAgent, MemoryAgent, AgentState, IntentType
from memory import ShortTermMemory, LongTermMemory
from session_store import load_sessions, save_sessions

app = FastAPI(title="Zoho Project Chatbot")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== MODELS =====

class ChatRequest(BaseModel):
    message: str
    confirmation_response: Optional[str] = None  # For HIL confirmation
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    bot_message: str
    requires_confirmation: bool = False
    confirmation_details: Optional[dict] = None
    conversation_id: Optional[str] = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    updated_at: str


class ChatHistoryResponse(BaseModel):
    conversations: list[ConversationSummary]


class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    messages: list[ConversationMessage]


class NewConversationResponse(BaseModel):
    conversation_id: str
    welcome_message: str


class RenameConversationRequest(BaseModel):
    title: str


class RenameConversationResponse(BaseModel):
    id: str
    title: str
    updated_at: str


class LoginResponse(BaseModel):
    auth_url: str


# ===== SESSION STORAGE =====
sessions: dict = load_sessions()       # {session_id -> {user_data}}
pending_actions: dict = {}  # {user_id -> {details}}


# ===== MIDDLEWARE & DEPENDENCIES =====

async def get_current_user(request: Request):
    """Extract user from session cookie"""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return sessions[session_id]


# ===== AUTH ENDPOINTS =====

@app.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    """Validate the current session cookie."""
    return {"authenticated": True, "user_id": user["user_id"]}


@app.get("/auth/login")
async def login():
    """Initiate OAuth flow"""
    state = secrets.token_urlsafe(32)

    scopes = " ".join([
        "ZohoProjects.portals.READ",
        "ZohoProjects.projects.READ",
        "ZohoProjects.tasks.READ",
        "ZohoProjects.tasks.CREATE",
        "ZohoProjects.tasks.UPDATE",
        "ZohoProjects.tasks.DELETE",
        "ZohoProjects.users.READ",
    ])

    auth_url = (
        f"https://accounts.zoho.in/oauth/v2/auth?"
        f"client_id={settings.zoho_client_id}&"
        f"response_type=code&"
        f"scope={scopes}&"
        f"redirect_uri={settings.zoho_redirect_uri}&"
        f"state={state}"
    )

    sessions[state] = {"state": state, "step": "pending_callback"}
    return LoginResponse(auth_url=auth_url)


@app.get("/auth/callback")
async def oauth_callback(code: str, state: str):
    """Zoho redirects here with auth code"""
    if state not in sessions:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://accounts.zoho.in/oauth/v2/token",
            data={
                "client_id": settings.zoho_client_id,
                "client_secret": settings.zoho_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.zoho_redirect_uri,
            }
        )
        print(f"Token response: {response.text}")  # DEBUG
        response.raise_for_status()
        token_data = response.json()

    session_id = secrets.token_urlsafe(32)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)
    user_id = "demo_user"  # Hardcoded to persist Long-Term Memory across sessions

    sessions[session_id] = {
        "user_id": user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": (datetime.now() + timedelta(seconds=expires_in)).timestamp(),
    }
    save_sessions(sessions)

    response = RedirectResponse(url=f"{settings.frontend_url}/?session={session_id}")
    response.set_cookie(
        "session_id", session_id,
        httponly=True,
        secure=False,   # set to True in production with HTTPS
        samesite="lax"
    )
    return response


WELCOME_MESSAGE = (
    "Hi! I'm your Zoho Projects assistant.\n"
    "Ask me about your projects, tasks, or team members — I'm here to help."
)


def _get_or_create_conversation(user: dict, long_term: LongTermMemory, conversation_id: Optional[str] = None) -> str:
    if conversation_id and long_term.get_conversation(conversation_id):
        user["active_conversation_id"] = conversation_id
        return conversation_id

    active_id = user.get("active_conversation_id")
    if active_id and long_term.get_conversation(active_id):
        return active_id

    conv = long_term.create_conversation()
    user["active_conversation_id"] = conv["id"]
    long_term.add_message_to_conversation(conv["id"], "bot", WELCOME_MESSAGE)
    return conv["id"]


# ===== CHAT ENDPOINT =====

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    """Main chat endpoint — routes through multi-agent system"""

    user_id = user["user_id"]

    # Initialize Zoho API client
    zoho_client = ZohoClient(
        user_id=user_id,
        access_token=user["access_token"],
        refresh_token=user["refresh_token"],
        expires_at=user["expires_at"],
    )

    # Initialize memory
    if "short_term" not in user:
        user["short_term"] = ShortTermMemory()
    short_term: ShortTermMemory = user["short_term"]
    long_term = LongTermMemory(user_id)
    conversation_id = _get_or_create_conversation(user, long_term, request.conversation_id)

    user_message = request.message.strip()
    if user_message and not request.confirmation_response:
        long_term.add_message_to_conversation(conversation_id, "user", user_message)
    elif request.confirmation_response:
        long_term.add_message_to_conversation(
            conversation_id,
            "user",
            f"(Confirmed: {request.confirmation_response})",
        )

    # Build agents
    router = Router()
    query_agent = QueryAgent(zoho_client, short_term)
    action_agent = ActionAgent(zoho_client, short_term)
    memory_agent = MemoryAgent(long_term)

    # Initialize agent state
    state = AgentState(
        user_id=user_id,
        message=request.message,
        intent=IntentType.UNKNOWN,
        agent_type="",
        memory=short_term,
    )

    # ── STEP 1 & 2: Route and Dispatch ────────────────────────────────────
    if request.confirmation_response:
        # Bypass router — confirmation always goes to action handler
        state.intent = IntentType.ACTION
        state.agent_type = "action"

        # Execute a previously confirmed pending action
        action = pending_actions.get(user_id)

        if not action:
            state.response = "No pending action found. Please try your request again."

        elif request.confirmation_response.strip().lower() in [
            "yes", "confirm", "yes to delete", "y"
        ]:
            details = action["details"]
            action_type = details.get("action")
            project_id = details.get("project_id")
            project_name = details.get("project_name", project_id)

            try:
                if action_type == "create_task":
                    await zoho_client.create_task(
                        project_id,
                        {"name": details["name"]}
                    )
                    state.response = (
                        f"Task '{details['name']}' created successfully "
                        f"in project '{project_name}'."
                    )
                    # Persist to long-term memory
                    long_term.add_past_project(project_id, project_name)

                elif action_type == "update_task":
                    changes = details.get("changes", {})
                    # Build payload: extract status string if present
                    payload = {}
                    if isinstance(changes, str):
                        for part in changes.split(","):
                            if "→" in part:
                                k, v = part.split("→", 1)
                                payload[k.strip()] = v.strip()
                    elif isinstance(changes, dict):
                        payload = changes
                    await zoho_client.update_task(
                        project_id,
                        details["task_id"],
                        payload
                    )
                    state.response = (
                        f"Task #{details['task_id']} updated successfully "
                        f"in project '{project_name}'."
                    )

                elif action_type == "delete_task":
                    await zoho_client.delete_task(project_id, details["task_id"])
                    state.response = (
                        f"Task #{details['task_id']} deleted from "
                        f"project '{project_name}'."
                    )

                else:
                    state.response = f"Unknown action: {action_type}"

            except Exception as e:
                state.response = f"Action failed: {str(e)}"

            pending_actions.pop(user_id, None)

        else:
            # User said no / cancelled
            pending_actions.pop(user_id, None)
            state.response = "Action cancelled. No changes were made."

    else:
        # First pass — prepare action and ask for confirmation using LangGraph
        from langgraph.graph import StateGraph, END
        from typing import TypedDict
        
        class GraphState(TypedDict):
            state: AgentState
            
        async def route_node(gstate: GraphState):
            s = await router.run(gstate["state"])
            return {"state": s}

        async def query_node(gstate: GraphState):
            s = await query_agent.run(gstate["state"])
            return {"state": s}

        async def action_node(gstate: GraphState):
            s = await action_agent.run(gstate["state"])
            return {"state": s}

        async def memory_node(gstate: GraphState):
            s = await memory_agent.run(gstate["state"])
            return {"state": s}

        def route_condition(gstate: GraphState) -> str:
            if gstate["state"].intent == IntentType.ACTION:
                return "action"
            elif gstate["state"].intent == IntentType.MEMORY:
                return "memory"
            return "query"

        workflow = StateGraph(GraphState)
        workflow.add_node("router", route_node)
        workflow.add_node("query", query_node)
        workflow.add_node("action", action_node)
        workflow.add_node("memory", memory_node)

        workflow.set_entry_point("router")
        workflow.add_conditional_edges("router", route_condition, {"query": "query", "action": "action", "memory": "memory"})
        workflow.add_edge("query", END)
        workflow.add_edge("action", END)
        workflow.add_edge("memory", END)

        app_graph = workflow.compile()
        try:
            result = await app_graph.ainvoke({"state": state})
            state = result["state"]
        except Exception:
            result = app_graph.invoke({"state": state})
            state = result["state"]

        if state.intent == IntentType.ACTION and state.requires_confirmation:
            pending_actions[user_id] = {"details": state.confirmation_details}

    # ── STEP 3: Long-term memory persistence ─────────────────────────────
    long_term.set_preference("last_chat", datetime.now().isoformat())

    # Save current project to long-term memory when it changes
    current_proj_id = short_term.get("current_project_id")
    current_proj_name = short_term.get("current_project_name")
    if current_proj_id:
        long_term.set_preference("last_project_id", current_proj_id)
        long_term.set_preference("last_project_name", current_proj_name)
        long_term.add_past_project(current_proj_id, current_proj_name or current_proj_id)

    long_term.add_message_to_conversation(conversation_id, "bot", state.response)

    return ChatResponse(
        bot_message=state.response,
        requires_confirmation=state.requires_confirmation,
        confirmation_details=state.confirmation_details,
        conversation_id=conversation_id,
    )


# ===== CONVERSATION ENDPOINTS =====

@app.get("/chat/history", response_model=ChatHistoryResponse)
async def chat_history(user: dict = Depends(get_current_user)):
    """List past conversations for the sidebar"""
    long_term = LongTermMemory(user["user_id"])
    conversations = [
        ConversationSummary(id=c["id"], title=c["title"], updated_at=c["updated_at"])
        for c in long_term.list_conversations()
    ]
    return ChatHistoryResponse(conversations=conversations)


@app.post("/chat/new", response_model=NewConversationResponse)
async def new_conversation(user: dict = Depends(get_current_user)):
    """Start a fresh conversation and reset session context"""
    user["short_term"] = ShortTermMemory()
    long_term = LongTermMemory(user["user_id"])
    conv = long_term.create_conversation()
    user["active_conversation_id"] = conv["id"]
    long_term.add_message_to_conversation(conv["id"], "bot", WELCOME_MESSAGE)
    return NewConversationResponse(
        conversation_id=conv["id"],
        welcome_message=WELCOME_MESSAGE,
    )


@app.get("/chat/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    """Load messages for a specific conversation"""
    long_term = LongTermMemory(user["user_id"])
    conv = long_term.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    user["active_conversation_id"] = conversation_id
    user["short_term"] = ShortTermMemory()
    return ConversationDetailResponse(
        id=conv["id"],
        title=conv["title"],
        messages=[
            ConversationMessage(
                role=m["role"],
                content=m["content"],
                timestamp=m["timestamp"],
            )
            for m in conv.get("messages", [])
        ],
    )


@app.patch("/chat/conversations/{conversation_id}", response_model=RenameConversationResponse)
async def rename_conversation(
    conversation_id: str,
    body: RenameConversationRequest,
    user: dict = Depends(get_current_user),
):
    """Rename a conversation title from the sidebar"""
    long_term = LongTermMemory(user["user_id"])
    if not long_term.rename_conversation(conversation_id, body.title):
        raise HTTPException(status_code=404, detail="Conversation not found or invalid title")

    conv = long_term.get_conversation(conversation_id)
    return RenameConversationResponse(
        id=conv["id"],
        title=conv["title"],
        updated_at=conv["updated_at"],
    )


# ===== LOGOUT ENDPOINT =====

@app.post("/auth/logout")
async def logout(request: Request):
    """Clear the session cookie but keep long-term memory intact"""
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]
        save_sessions(sessions)
    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie("session_id")
    return response


# ===== WELCOME CONTEXT ENDPOINT =====

@app.post("/chat/welcome", response_model=ChatResponse)
async def welcome():
    """Returns a generic welcome message without requiring authentication"""
    return ChatResponse(
        bot_message=WELCOME_MESSAGE,
        requires_confirmation=False,
        confirmation_details=None,
    )


# ===== HEALTH CHECK =====

@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
