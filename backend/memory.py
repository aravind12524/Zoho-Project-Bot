import json
import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime


class ShortTermMemory:
    """Session-based memory within a single conversation"""
    
    def __init__(self):
        self.context: Dict[str, Any] = {
            "current_project_id": None,
            "current_project_name": None,
            "recent_tasks": [],
            "message_history": []
        }
    
    def set(self, key: str, value: Any):
        """Store a value in session context"""
        self.context[key] = value
    
    def get(self, key: str, default=None) -> Any:
        """Retrieve a value from session context"""
        return self.context.get(key, default)
    
    def clear(self):
        """Clear session context"""
        self.context = {k: None for k in self.context.keys()}


class LongTermMemory:
    """Persistent memory across sessions — file-based for simplicity"""
    
    def __init__(self, user_id: str, db_dir: str = "./data"):
        self.user_id = user_id
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(exist_ok=True)
        self.file_path = self.db_dir / f"{user_id}_memory.json"
        self.data = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load persistent data from file"""
        if self.file_path.exists():
            with open(self.file_path, "r") as f:
                return json.load(f)
        return {
            "user_id": self.user_id,
            "preferences": {},
            "past_projects": [],
            "favorite_projects": [],
            "conversations": [],
            "created_at": datetime.now().isoformat()
        }
    
    def _save(self):
        """Save persistent data to file"""
        with open(self.file_path, "w") as f:
            json.dump(self.data, f, indent=2)
    
    def set_preference(self, key: str, value: Any):
        """Store a user preference"""
        self.data["preferences"][key] = value
        self._save()
    
    def get_preference(self, key: str, default=None) -> Any:
        """Retrieve a user preference"""
        return self.data["preferences"].get(key, default)
    
    def add_past_project(self, project_id: str, project_name: str):
        """Record a project the user has accessed"""
        project = {"id": project_id, "name": project_name, "accessed_at": datetime.now().isoformat()}
        
        # Remove if already exists to avoid duplicates
        self.data["past_projects"] = [p for p in self.data["past_projects"] if p["id"] != project_id]
        self.data["past_projects"].append(project)
        self._save()
    
    def add_favorite_project(self, project_id: str, project_name: str):
        """Mark a project as favorite"""
        if {"id": project_id, "name": project_name} not in self.data["favorite_projects"]:
            self.data["favorite_projects"].append({"id": project_id, "name": project_name})
            self._save()
    
    def get_favorite_projects(self) -> list:
        """Retrieve user's favorite projects"""
        return self.data.get("favorite_projects", [])

    def _ensure_conversations(self):
        if "conversations" not in self.data:
            self.data["conversations"] = []

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_conversations()
        for conv in self.data["conversations"]:
            if conv["id"] == conversation_id:
                return conv
        return None

    def create_conversation(self, title: str = "New conversation") -> Dict[str, Any]:
        self._ensure_conversations()
        now = datetime.now().isoformat()
        conv = {
            "id": str(uuid.uuid4()),
            "title": title,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        self.data["conversations"].insert(0, conv)
        self._save()
        return conv

    def add_message_to_conversation(self, conversation_id: str, role: str, content: str):
        conv = self.get_conversation(conversation_id)
        if not conv:
            return

        conv["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        conv["updated_at"] = datetime.now().isoformat()

        if conv["title"] == "New conversation" and role == "user":
            preview = content.strip().replace("\n", " ")
            conv["title"] = preview[:48] + ("…" if len(preview) > 48 else "")

        self._save()

    def list_conversations(self) -> List[Dict[str, Any]]:
        self._ensure_conversations()
        return sorted(
            self.data["conversations"],
            key=lambda c: c.get("updated_at", ""),
            reverse=True,
        )

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        conv = self.get_conversation(conversation_id)
        if not conv:
            return False
        cleaned = title.strip()
        if not cleaned:
            return False
        conv["title"] = cleaned[:80]
        conv["updated_at"] = datetime.now().isoformat()
        self._save()
        return True
