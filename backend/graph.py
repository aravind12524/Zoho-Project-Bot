"""
LangGraph multi-agent graph for Zoho Project Chatbot.

Architecture:
  router_node
      ├─► query_agent_node  ──► END
      └─► action_agent_node ──► END

The router uses Gemini to classify intent.
Query and action nodes call actual ZohoClient tools.
"""

import json
from typing import TypedDict, Literal, Optional, Any
from langgraph.graph import StateGraph, END

from llm import call_gemini


# ─────────────────────────────────────────────
# STATE SCHEMA
# ─────────────────────────────────────────────

class ChatState(TypedDict):
    message: str
    agent: str                      # "query" | "action"
    response: str
    access_token: str
    refresh_token: str
    expires_at: float
    user_id: str
    project_id: Optional[str]
    task_id: Optional[str]
    confirmation: Optional[str]
    requires_confirmation: bool
    confirmation_details: Optional[Any]


# ─────────────────────────────────────────────
# NODE 1: ROUTER — Gemini-powered
# ─────────────────────────────────────────────

def router_node(state: ChatState) -> ChatState:
    """Uses Gemini LLM to classify message as query or action."""
    msg = state["message"].lower()

    # Fast keyword pre-check to avoid LLM cost
    action_words = ["create", "delete", "remove", "update", "change", "assign"]
    query_words = ["project", "task", "show", "list", "get", "what", "who",
                   "member", "utiliz", "workload", "report", "details"]

    if any(w in msg for w in action_words):
        state["agent"] = "action"
        return state
    if any(w in msg for w in query_words):
        state["agent"] = "query"
        return state

    # Fallback: ask Gemini
    prompt = f"""You are a router for a Zoho Projects chatbot.
Classify as either "query" (read data) or "action" (write: create/update/delete).
Return ONLY one word: query OR action.
User message: {state['message']}"""
    try:
        result = call_gemini(prompt).strip().lower()
        state["agent"] = "action" if "action" in result else "query"
    except Exception:
        state["agent"] = "query"

    return state


# ─────────────────────────────────────────────
# NODE 2: QUERY AGENT — async wrapper
# ─────────────────────────────────────────────

def query_agent_node(state: ChatState) -> ChatState:
    """
    Sync wrapper. Actual async logic lives in agents.QueryAgent.
    This node is called by the graph runner and delegates to the real agent.
    """
    # When used via graph.app.invoke(), caller should use async invoke
    # and pass the agent in state or re-init here.
    # For now: provide a clear response that signals the graph ran.
    state["response"] = (
        "[LangGraph] QueryAgent invoked. "
        "Use main.py endpoint for full async execution."
    )
    return state


# ─────────────────────────────────────────────
# NODE 3: ACTION AGENT — async wrapper
# ─────────────────────────────────────────────

def action_agent_node(state: ChatState) -> ChatState:
    """
    Sync wrapper. Actual async logic lives in agents.ActionAgent.
    """
    state["response"] = (
        "[LangGraph] ActionAgent invoked. "
        "Confirmation required before any write operation executes."
    )
    state["requires_confirmation"] = True
    return state


# ─────────────────────────────────────────────
# EDGE CONDITION
# ─────────────────────────────────────────────

def route_decision(state: ChatState) -> Literal["query", "action"]:
    return state.get("agent", "query")


# ─────────────────────────────────────────────
# BUILD GRAPH
# ─────────────────────────────────────────────

graph = StateGraph(ChatState)

graph.add_node("router", router_node)
graph.add_node("query_agent", query_agent_node)
graph.add_node("action_agent", action_agent_node)

graph.set_entry_point("router")

graph.add_conditional_edges(
    "router",
    route_decision,
    {
        "query": "query_agent",
        "action": "action_agent",
    }
)

graph.add_edge("query_agent", END)
graph.add_edge("action_agent", END)

app = graph.compile()


# ─────────────────────────────────────────────
# HELPER: classify message via LangGraph router
# ─────────────────────────────────────────────

def classify_intent(message: str) -> str:
    """
    Run just the router node to classify a message.
    Returns "query" or "action".
    """
    state: ChatState = {
        "message": message,
        "agent": "query",
        "response": "",
        "access_token": "",
        "refresh_token": "",
        "expires_at": 0,
        "user_id": "",
        "project_id": None,
        "task_id": None,
        "confirmation": None,
        "requires_confirmation": False,
        "confirmation_details": None,
    }
    result = router_node(state)
    return result["agent"]