import json
from pathlib import Path
from typing import Dict, Any

from memory import ShortTermMemory

SESSIONS_FILE = Path("./data/sessions.json")


def load_sessions() -> Dict[str, Any]:
    """Load persisted user sessions from disk."""
    if not SESSIONS_FILE.exists():
        return {}

    with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    sessions: Dict[str, Any] = {}
    for session_id, data in raw.items():
        if not isinstance(data, dict) or "user_id" not in data:
            continue
        data["short_term"] = ShortTermMemory()
        sessions[session_id] = data
    return sessions


def save_sessions(sessions: Dict[str, Any]) -> None:
    """Persist user sessions, excluding OAuth state and runtime objects."""
    SESSIONS_FILE.parent.mkdir(exist_ok=True)

    serializable = {}
    for session_id, data in sessions.items():
        if not isinstance(data, dict) or "user_id" not in data:
            continue
        serializable[session_id] = {
            key: value for key, value in data.items() if key != "short_term"
        }

    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)
