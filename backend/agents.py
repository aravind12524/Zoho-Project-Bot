import json
import re
import traceback
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field
from zoho_client import ZohoClient
from memory import ShortTermMemory, LongTermMemory
from llm import call_grok, call_gemini, get_response


class IntentType(str, Enum):
    """Intent classification for routing"""
    QUERY = "query"
    ACTION = "action"
    MEMORY = "memory"
    UNKNOWN = "unknown"


@dataclass
class AgentState:
    """State passed between agent nodes"""
    user_id: str
    message: str
    intent: IntentType
    agent_type: str  # "query", "action", "router"
    response: str = ""
    requires_confirmation: bool = False
    confirmation_details: Optional[Dict[str, Any]] = None
    memory: Optional[ShortTermMemory] = None


# ===========================
# ROUTER — Grok-powered LLM (with Gemini fallback)
# ===========================

class Router:
    """Uses Grok to classify intent as QUERY or ACTION (falls back to Gemini)"""

    def __init__(self):
        self.name = "Router"

    async def run(self, state: AgentState) -> AgentState:
        prompt = f"""✅ SYSTEM PROMPT (Router Agent)
You are an intelligent routing engine for a Zoho Projects chatbot.
Your job is to classify the user's message into exactly ONE intent category and route it correctly in a LangGraph workflow.

🎯 INTENT CATEGORIES
Choose only one:
1. memory_write
User is providing new personal preference or storing information. Examples: "My favorite project is Zoho Chatbot", "Remember that I prefer SQL"
2. memory_recall
User is asking about stored personal information. Examples: "What is my favorite project?", "What do you remember about me?", "My preference?"
3. project_action
User is asking about projects (list, activate, switch, details). Examples: "show my projects", "open Zoho Chatbot project", "list projects"
4. task_action
User is asking about tasks (create, delete, view tasks). Examples: "create task fix bug", "show tasks", "delete task 123"
5. general_chat
Greeting or unrelated queries. Examples: "hi", "hello", "how are you"

⚠️ CRITICAL RULES
NEVER confuse memory questions with project queries.
If the user asks "what is my favorite X", always classify as memory_recall unless it explicitly asks for project listing.
"project" keyword alone does NOT mean project_action. Context meaning is more important than keywords.
Always pick the most specific intent.

🧠 OUTPUT FORMAT (STRICT JSON ONLY)
Return ONLY this format:
{{
  "intent": "memory_recall",
  "confidence": 0.95
}}
No explanations. No extra text.

🔥 PRIORITY RULES (VERY IMPORTANT)
memory_recall / memory_write (highest priority)
task_action
project_action
general_chat

User message: {state.message}"""

        try:
            import json
            import re
            result_str = get_response(prompt)  # ✅ Uses Grok first, falls back to Gemini
            
            # Clean markdown JSON formatting
            json_str = result_str
            if "```" in json_str:
                match = re.search(r'```(?:json)?(.*?)```', json_str, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()
            else:
                # Try to extract from first { to last }
                match = re.search(r'(\{.*\})', json_str, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()
                    
            data = json.loads(json_str)
            raw_intent = data.get("intent", "")
            confidence = float(data.get("confidence", 1.0))
            
            if confidence < 0.7:
                state.intent = IntentType.QUERY
                state.agent_type = "query"
                state.response = "I'm not entirely sure what you mean. Could you clarify?"
                return state

            # Map the exact JSON intent back to our Agent structure
            if raw_intent in ["memory_write", "memory_recall"]:
                state.intent = IntentType.MEMORY
                state.agent_type = raw_intent  # pass raw intent for MemoryAgent
            elif raw_intent == "project_action":
                state.intent = IntentType.QUERY
                state.agent_type = "query"
            elif raw_intent == "task_action":
                # Check if it's a mutation (action) or a read (query)
                action_words = ["create", "delete", "remove", "update", "change", "add"]
                if any(w in state.message.lower() for w in action_words):
                    state.intent = IntentType.ACTION
                    state.agent_type = "action"
                else:
                    state.intent = IntentType.QUERY
                    state.agent_type = "query"
            elif raw_intent == "general_chat":
                state.intent = IntentType.QUERY
                state.agent_type = "query"
            else:
                state.intent = IntentType.QUERY
                
        except Exception as e:
            print(f"[DEBUG] Router Error: {e}")
            state.intent = IntentType.QUERY
            state.agent_type = "query"

        return state


# ===========================
# QUERY AGENT — All READ ops
# ===========================

class QueryAgent:
    """Handles all read operations — list projects, tasks, members, utilization"""

    def __init__(self, zoho_client: ZohoClient, short_term_memory: ShortTermMemory):
        self.client = zoho_client
        self.memory = short_term_memory
        self.name = "QueryAgent"

    async def run(self, state: AgentState) -> AgentState:
        message = state.message.lower()
        project_id = self.memory.get("current_project_id")

        try:
            # ── CASE 1: LIST PROJECTS ──────────────────────────────────────
            if "project" in message:
                raw = await self.client.list_projects()
                print(f"[DEBUG] list_projects raw type={type(raw).__name__} value={str(raw)[:200]}")
                projects_list = self._normalize_list(raw, ["projects", "data"])
                if projects_list:
                    first = projects_list[0]
                    self.memory.set("current_project_id", str(first.get("id", "")))
                    self.memory.set("current_project_name", first.get("name", ""))
                state.response = self._compose_response(
                    state.message,
                    "project_list",
                    {
                        "projects": [
                            {
                                "name": p.get("name", "Unnamed"),
                                "id": p.get("id", "?"),
                                "status": (
                                    p.get("status", {}).get("name", "")
                                    if isinstance(p.get("status"), dict)
                                    else p.get("status", "")
                                ),
                            }
                            for p in projects_list[:10]
                        ],
                        "active_project": projects_list[0].get("name") if projects_list else None,
                    },
                )

            # ── CASE 2: PROJECT MEMBERS ────────────────────────────────────
            elif any(w in message for w in ["member", "team", "who is", "who's on"]):
                if not project_id:
                    project_id = await self._auto_select_project()
                if not project_id:
                    state.response = "No active project. Ask about your projects first."
                    return state
                raw = await self.client.list_project_members(project_id)
                print(f"[DEBUG] list_members raw={str(raw)[:200]}")
                members_list = self._normalize_list(raw, ["users", "members", "data"])
                state.response = self._compose_response(
                    state.message,
                    "team_members",
                    {
                        "project_name": self.memory.get("current_project_name") or project_id,
                        "members": [
                            {
                                "name": m.get("name", m.get("full_name", "Unknown")),
                                "email": m.get("email", ""),
                                "role": (
                                    m.get("role", {}).get("name", "Member")
                                    if isinstance(m.get("role"), dict)
                                    else m.get("role", m.get("role_details", {}).get("name", "Member"))
                                ),
                            }
                            for m in members_list
                        ],
                    },
                )

            # ── CASE 3: TASK UTILIZATION / WORKLOAD ───────────────────────
            elif any(w in message for w in ["utiliz", "workload", "who has", "task load", "report"]):
                if not project_id:
                    project_id = await self._auto_select_project()
                if not project_id:
                    state.response = "No active project. Ask about your projects first."
                    return state
                # Aggregate from tasks list: group by owner/assignee
                raw_tasks = await self.client.list_tasks(project_id)
                tasks_list = self._normalize_list(raw_tasks, ["tasks", "data"])
                project_name = self.memory.get("current_project_name") or project_id
                workload = self._build_workload(tasks_list)
                state.response = self._compose_response(
                    state.message,
                    "task_utilization",
                    {
                        "project_name": project_name,
                        "total_tasks": len(tasks_list),
                        "workload": workload,
                    },
                )

            # ── CASE 4: TASK DETAILS ───────────────────────────────────────
            elif any(w in message for w in ["detail", "info about task", "task #", "task id"]):
                if not project_id:
                    project_id = await self._auto_select_project()
                if not project_id:
                    state.response = "No active project. Ask about your projects first."
                    return state
                task_id = self._extract_task_id(message)
                if not task_id:
                    state.response = "Please specify a task ID (e.g. 'details of task 123')."
                    return state
                raw = await self.client.get_task_details(project_id, task_id)
                task = raw if isinstance(raw, dict) else {}
                state.response = self._compose_response(
                    state.message,
                    "task_detail",
                    {
                        "task": {
                            "name": task.get("name", "Unknown"),
                            "status": (
                                task.get("status", {}).get("name", "Unknown")
                                if isinstance(task.get("status"), dict)
                                else task.get("status", "Unknown")
                            ),
                            "assignees": ", ".join(
                                n
                                for n in (
                                    self._owner_name(a)
                                    for a in self._get_task_owners(task)
                                )
                                if n
                            )
                            or "Unassigned",
                            "due_date": task.get("end_date", task.get("due_date", "Not set")),
                            "description": task.get("description", "No description"),
                        },
                    },
                )

            # ── CASE 5: LIST TASKS ────────────────────────────────────────
            elif "task" in message:
                if not project_id:
                    project_id = await self._auto_select_project()
                if not project_id:
                    state.response = "No active project. Ask about your projects first."
                    return state
                raw = await self.client.list_tasks(project_id)
                print(f"[DEBUG] list_tasks raw type={type(raw).__name__} value={str(raw)[:200]}")
                tasks_list = self._normalize_list(raw, ["tasks", "data"])
                # Store for follow-up
                if tasks_list:
                    self.memory.set("recent_tasks", tasks_list[:10])
                project_name = self.memory.get("current_project_name") or project_id
                state.response = self._compose_response(
                    state.message,
                    "task_list",
                    {
                        "project_name": project_name,
                        "tasks": [
                            {
                                "name": t.get("name", "Unnamed"),
                                "id": t.get("id", "?"),
                                "status": (
                                    t.get("status", {}).get("name", "Open")
                                    if isinstance(t.get("status"), dict)
                                    else t.get("status", "Open")
                                ),
                                "assignee": self._assignee_label(t).replace(
                                    "no one assigned yet", "Unassigned"
                                ).replace("assigned to ", ""),
                            }
                            for t in tasks_list[:10]
                        ],
                        "total_shown": min(len(tasks_list), 10),
                        "total_count": len(tasks_list),
                    },
                )

            # ── FALLBACK: Grok AI (with Gemini fallback) ───────────────────
            else:
                ctx_parts = []
                if self.memory.get("current_project_name"):
                    ctx_parts.append(f"Active project: {self.memory.get('current_project_name')}")
                tasks = self.memory.get("recent_tasks") or []
                if tasks:
                    task_names = [t.get("name", "") for t in tasks[:3]]
                    ctx_parts.append(f"Recent tasks: {', '.join(task_names)}")
                context = "\n".join(ctx_parts) if ctx_parts else "No active project selected yet."
                prompt = f"""You are a helpful Zoho Projects assistant.

Context:
{context}

User asked: {state.message}

Give a short, helpful response. Suggest commands like 'projects', 'tasks', 
'members', 'create task <name>', or 'delete task <id>' if appropriate.
Keep the response under 5 sentences."""
                state.response = get_response(prompt)  # ✅ Uses Grok first, falls back to Gemini

        except Exception as e:
            print(f"[ERROR] QueryAgent: {traceback.format_exc()}")
            state.response = f"Error: {str(e)}"

        return state

    async def _auto_select_project(self) -> Optional[str]:
        """Try to auto-fetch first project if none selected"""
        try:
            raw = await self.client.list_projects()
            pl = self._normalize_list(raw, ["projects", "data"])
            if pl:
                first = pl[0]
                pid = str(first.get("id", ""))
                self.memory.set("current_project_id", pid)
                self.memory.set("current_project_name", first.get("name", ""))
                return pid
        except Exception:
            pass
        return None

    def _normalize_list(self, raw, keys: list) -> list:
        """Extract a list from API response regardless of wrapper structure"""
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            for k in keys:
                val = raw.get(k)
                if isinstance(val, list):
                    return val
        return []

    def _compose_response(self, user_message: str, response_type: str, facts: dict) -> str:
        """Use Grok/Gemini to generate a natural, conversational, and professional response using the facts retrieved from Zoho."""
        prompt = f"""You are a highly professional, natural, and helpful AI assistant for Zoho Projects.
The user asked: "{user_message}"
We retrieved the following data from the Zoho Projects API (type: {response_type}):
{json.dumps(facts, indent=2)}

Please write a natural, engaging, and professional response that directly answers the user's request using this data.

Guidelines:
1. **Be conversational and natural**: Do NOT sound like a rigid rule-based template. Write as if you are a smart human team member or a premium AI assistant.
2. **Never use rigid ASCII bar charts, progress indicators, or raw symbols** (like "▪▪▪▪▪▪" or excessive line separators).
3. **Format beautifully**: Use clean and modern markdown formatting (e.g., bolding important names, clear headings if needed, clean lists).
4. **Be helpful and proactive**: Suggest what the user can do next (e.g. asking for details, updating/creating/deleting tasks, checking members, switching projects) in a friendly, context-appropriate way.
5. **Keep the tone polished**: Avoid childish formatting or robotic language. Keep the response concise but comprehensive enough to answer the question.
"""
        return get_response(prompt).strip()

    def _get_task_owners(self, task: dict) -> list:
        """Read assignees from Zoho v3 task payload."""
        owners = task.get("owners_and_work", {}).get("owners")
        if not owners:
            owners = task.get("details", {}).get("owners", [])
        return owners if isinstance(owners, list) else []

    def _owner_name(self, owner: dict) -> Optional[str]:
        """Return a display name, or None for placeholder unassigned owners."""
        if not owner:
            return None
        if owner.get("zuid") == 0:
            return None
        name = (owner.get("name") or owner.get("full_name") or "").strip()
        if not name or "unassigned" in name.lower():
            return None
        return name

    def _assignee_label(self, task: dict) -> str:
        names = [
            n for n in (self._owner_name(o) for o in self._get_task_owners(task)) if n
        ]
        if not names:
            return "no one assigned yet"
        if len(names) == 1:
            return f"assigned to {names[0]}"
        return f"assigned to {', '.join(names)}"

    def _build_workload(self, tasks: list) -> List[dict]:
        counts: Dict[str, int] = {}
        for t in tasks:
            owners = self._get_task_owners(t)
            names = [n for n in (self._owner_name(o) for o in owners) if n]
            if not names:
                counts["Unassigned"] = counts.get("Unassigned", 0) + 1
            else:
                for name in names:
                    counts[name] = counts.get(name, 0) + 1
        total = len(tasks) or 1
        return [
            {
                "person": person,
                "task_count": count,
                "percentage": round(count / total * 100),
            }
            for person, count in sorted(counts.items(), key=lambda x: -x[1])
        ]

    def _extract_task_id(self, message: str) -> Optional[str]:
        match = re.search(r'#?(\d+)', message)
        if match:
            val = match.group(1)
            if val != self.memory.get("current_project_id"):
                return val
        return None


# ===========================
# ACTION AGENT — All WRITE ops
# ===========================

class ActionAgent:
    """Handles all write operations with HIL confirmation"""

    def __init__(self, zoho_client: ZohoClient, short_term_memory: ShortTermMemory):
        self.client = zoho_client
        self.memory = short_term_memory
        self.name = "ActionAgent"

    async def run(self, state: AgentState) -> AgentState:
        message = state.message.lower()
        try:
            if "create" in message or "new task" in message or "add task" in message:
                state = await self._prepare_create_task(state, state.message)
            elif "update" in message or "change" in message or "mark" in message:
                state = await self._prepare_update_task(state, state.message)
            elif "delete" in message or "remove" in message:
                state = await self._prepare_delete_task(state, state.message)
            else:
                state.response = (
                    "I didn't understand that action. Try:\n"
                    "- Create task <name>\n"
                    "- Update task <name or id> status to done\n"
                    "- Delete task <name or id>"
                )
        except Exception as e:
            state.response = f"Error preparing action: {str(e)}"
        return state

    async def _prepare_create_task(self, state: AgentState, message: str) -> AgentState:
        project_id = self.memory.get("current_project_id")
        project_name = self.memory.get("current_project_name")
        if not project_id:
            state.requires_confirmation = False
            state.response = (
                "No active project selected.\n"
                "Please type 'projects' first to load your projects, then try creating a task."
            )
            return state
        task_name = self._extract_task_name(message)
        
        # Alphanumeric check to reject symbol-only names (e.g., "\")
        import re
        if not task_name or task_name == "Untitled Task" or len(task_name.strip()) < 2 or not re.search(r'[a-zA-Z0-9]', task_name):
            state.requires_confirmation = False
            state.response = (
                "Could you please specify a clear title for the new task?\n"
                "For example: 'create task Review homepage'"
            )
            return state
        state.requires_confirmation = True
        state.confirmation_details = {
            "action": "create_task",
            "name": task_name,
            "project_id": project_id,
            "project_name": project_name,
        }
        state.response = (
            f"Ready to create a new task:\n"
            f"Title: {task_name}\n"
            f"Project: {project_name}\n\n"
            "Please confirm if you want to proceed."
        )
        return state

    async def _prepare_update_task(self, state: AgentState, message: str) -> AgentState:
        project_id = self.memory.get("current_project_id")
        project_name = self.memory.get("current_project_name")
        if not project_id:
            state.requires_confirmation = False
            state.response = (
                "No active project selected.\n"
                "Please type 'projects' first to load your projects, then try updating a task."
            )
            return state
        task_id = self._extract_task_id(message)
        changes = self._extract_updates(message)
        if not task_id:
            recent_tasks = self.memory.get("recent_tasks") or []
            prompt = f"""You are a helpful Zoho Projects AI assistant.
The user wants to update a task, but they didn't specify which task (ID or name) they want to update.

Here is a list of recent tasks in the active project:
{json.dumps(recent_tasks[:8], indent=2) if recent_tasks else "No recent tasks loaded."}

Please write a natural, conversational response asking the user which task they want to update.
If recent tasks are available, list them in a clean, user-friendly format (without raw brackets or ID symbols) so they can easily choose one. If no tasks are loaded, kindly suggest they type 'tasks' to see the list first.
"""
            state.response = get_response(prompt).strip()
            state.requires_confirmation = False
            return state
            
        task_name = self._find_task_name(task_id)
        state.requires_confirmation = True
        state.confirmation_details = {
            "action": "update_task",
            "task_id": task_id,
            "project_id": project_id,
            "project_name": project_name,
            "changes": changes,
        }
        state.response = (
            f"Ready to update task:\n"
            f"Task: {task_name or f'#{task_id}'}\n"
            f"Project: {project_name}\n"
            f"Changes: {changes}\n\n"
            "Please confirm if you want to proceed."
        )
        return state

    async def _prepare_delete_task(self, state: AgentState, message: str) -> AgentState:
        project_id = self.memory.get("current_project_id")
        project_name = self.memory.get("current_project_name")
        if not project_id:
            state.requires_confirmation = False
            state.response = (
                "No active project selected.\n"
                "Please type 'projects' first to load your projects, then try deleting a task."
            )
            return state
        task_id = self._extract_task_id(message)
        if not task_id:
            recent_tasks = self.memory.get("recent_tasks") or []
            prompt = f"""You are a helpful Zoho Projects AI assistant.
The user wants to delete a task, but they didn't specify which task (ID or name) they want to delete.

Here is a list of recent tasks in the active project:
{json.dumps(recent_tasks[:8], indent=2) if recent_tasks else "No recent tasks loaded."}

Please write a natural, conversational response asking the user which task they want to delete.
If recent tasks are available, list them in a clean, user-friendly format (without raw brackets or ID symbols) so they can easily choose one. If no tasks are loaded, kindly suggest they type 'tasks' to see the list first.
"""
            state.response = get_response(prompt).strip()
            state.requires_confirmation = False
            return state
            
        task_name = self._find_task_name(task_id)
        state.requires_confirmation = True
        state.confirmation_details = {
            "action": "delete_task",
            "task_id": task_id,
            "project_id": project_id,
            "project_name": project_name,
        }
        state.response = (
            f"Are you sure you want to delete this task?\n"
            f"Task: {task_name or f'#{task_id}'}\n"
            f"Project: {project_name}\n\n"
            "Please confirm if you want to proceed."
        )
        return state

    def _find_task_name(self, task_id: str) -> Optional[str]:
        """Look up a task name from recently fetched tasks"""
        recent_tasks = self.memory.get("recent_tasks") or []
        for t in recent_tasks:
            if str(t.get("id", "")) == task_id:
                return t.get("name", None)
        return None

    def _extract_task_name(self, message: str) -> str:
        # Try to extract name after "task", "called", "named"
        patterns = [
            r'(?:create|add|new)\s+task\s+(?:called\s+|named\s+)?["\']?(.+?)["\']?\s*$',
            r'(?:create|add|new)\s+["\'](.+?)["\']',
        ]
        for pat in patterns:
            match = re.search(pat, message, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        # Fallback: take everything after "task"
        match = re.search(r'task\s+(.+)', message, re.IGNORECASE)
        return match.group(1).strip() if match else "Untitled Task"

    def _extract_task_id(self, message: str) -> Optional[str]:
        recent_tasks = self.memory.get("recent_tasks") or []
        msg = message.lower()
        
        # 1. Look for a long database ID (usually 15-22 digits)
        match_long = re.search(r'\b(\d{15,22})\b', message)
        if match_long:
            val = match_long.group(1)
            # Make sure it isn't the project ID
            if val != self.memory.get("current_project_id"):
                return val
            
        # 2. Look for task prefix key like ZC1-T1 or T1 or T2
        for t in recent_tasks:
            prefix = t.get("prefix", "").lower()
            if prefix and prefix in msg:
                return str(t.get("id"))
            if prefix and "-" in prefix:
                part = prefix.split("-")[-1] # "t1"
                if part in msg.split() or f"task {part}" in msg or f"task#{part}" in msg or f"task {part.replace('t', '')}" in msg:
                    return str(t.get("id"))
                    
        # 3. Look for a name match
        for t in recent_tasks:
            name = t.get("name", "").lower()
            if name and len(name) > 3 and name in msg:
                return str(t.get("id"))
                
        # 4. Fallback: match any digit sequence
        match_any = re.search(r'#?(\d+)', message)
        if match_any:
            val = match_any.group(1)
            if val != self.memory.get("current_project_id"):
                return val
            
        return None

    def _extract_updates(self, message: str) -> str:
        updates = {}
        # Name/Title
        name_match = re.search(
            r'(?:name|title)\s+(?:to\s+)?(.+)$', message, re.IGNORECASE
        )
        if name_match:
            updates["name"] = name_match.group(1).strip()
        # Status
        status_match = re.search(
            r'status\s+(?:to\s+)?["\']?(\w[\w\s]*?)["\']?(?:\s|$)', message, re.IGNORECASE
        )
        if status_match:
            updates["status"] = status_match.group(1).strip()
        # Priority
        priority_match = re.search(
            r'priority\s+(?:to\s+)?["\']?(\w+)["\']?', message, re.IGNORECASE
        )
        if priority_match:
            updates["priority"] = priority_match.group(1).strip()
        # Due date
        due_match = re.search(
            r'due\s+(?:date\s+)?(?:to\s+)?["\']?([0-9\-/]+)["\']?', message, re.IGNORECASE
        )
        if due_match:
            updates["due_date"] = due_match.group(1).strip()
        if not updates:
            return "No specific fields detected — please confirm what should change."
        return ", ".join(f"{k} → {v}" for k, v in updates.items())


# ===========================
# MEMORY AGENT — Personal Preferences
# ===========================

class MemoryAgent:
    """Handles storing and recalling personal user preferences via LongTermMemory"""

    def __init__(self, long_term_memory: LongTermMemory):
        self.memory = long_term_memory
        self.name = "MemoryAgent"

    async def run(self, state: AgentState) -> AgentState:
        msg = state.message.lower()

        if state.agent_type == "memory_write":
            # Very simple regex extraction for preferences like "my favorite project is X"
            import re
            match = re.search(r'my favorite (project|task|thing) is (.+)', msg, re.IGNORECASE)
            if match:
                pref_key = f"favorite_{match.group(1).strip()}"
                pref_value = match.group(2).strip()
                self.memory.set_preference(pref_key, pref_value)
                state.response = f"Got it! I've remembered that your favorite {match.group(1).strip()} is {pref_value}."
            elif "prefer" in msg:
                match = re.search(r'i prefer (.+)', msg, re.IGNORECASE)
                if match:
                    self.memory.set_preference("general_preference", match.group(1).strip())
                    state.response = f"Noted! I'll remember that you prefer {match.group(1).strip()}."
                else:
                    self.memory.set_preference("last_stated_preference", state.message)
                    state.response = "I have noted your preference."
            else:
                self.memory.set_preference("general_note", state.message)
                state.response = "I have saved that to your memory."

        elif state.agent_type == "memory_recall":
            prefs = self.memory.data.get("preferences", {})
            if prefs:
                prompt = f"""
                You are a helpful assistant for Zoho Projects.
                The user asked a question about their preferences/memory: "{state.message}"
                
                Here is everything you remember about them:
                {prefs}
                
                Based ONLY on the memory above, answer the user's question clearly and concisely.
                Do not output the raw dictionary or bullet points of everything you know.
                If the answer is not in the memory, politely say you don't know it yet.
                """
                from llm import get_response
                try:
                    response = get_response(prompt).strip()
                    state.response = response
                except Exception as e:
                    state.response = f"I had trouble recalling that right now: {e}"
            else:
                state.response = "I don't remember anything specific about you yet."

        else:
            state.response = "I couldn't process your memory request."

        return state