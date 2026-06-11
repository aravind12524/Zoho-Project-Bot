import json
from llm import call_gemini
from agents import IntentType


class Router:

    async def classify_intent(self, message: str) -> IntentType:
    msg = message.lower().strip()

    # ACTION
    action_words = ["create", "delete", "update", "assign", "change", "add", "remove", "make"]
    if any(word in msg for word in action_words):
        return IntentType.ACTION

    # QUERY (expanded heavily)
    query_words = [
        "project", "projects",
        "task", "tasks",
        "show", "list", "get",
        "what", "tell", "details",
        "who", "how many",
        "my work", "summary"
    ]

    if any(word in msg for word in query_words):
        return IntentType.QUERY

    return IntentType.QUERY  # 👈 IMPORTANT fallback