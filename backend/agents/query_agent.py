import asyncio
import difflib

async def query_agent(state: ChatState) -> ChatState:
    client = ZohoClient(state["access_token"])

    msg = state["message"].lower()

    # -------------------------
    # LIST PROJECTS
    # -------------------------
    if "project" in msg:
        result = await list_projects(client)
        state["response"] = f"📁 Projects:\n{result}"
        return state

    # -------------------------
    # LIST TASKS
    # -------------------------
    if "task" in msg:
        # if project not provided, just demo response
        if state.get("project_id"):
            result = await list_tasks(client, state["project_id"])
        else:
            result = await list_projects(client)

        state["response"] = f"📌 Tasks Data:\n{result}"
        return state

    # -------------------------
    # DEFAULT
    # -------------------------
    state["response"] = "I can help you with projects and tasks. Try asking about your projects."
    return state