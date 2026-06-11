import httpx
from typing import Dict, Any


# -----------------------------
# ZOHO CLIENT WRAPPER
# -----------------------------
class ZohoClient:
    def __init__(self, access_token: str):
        self.base_url = "https://www.zohoapis.in/projects/v3"
        self.headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json"
        }

    async def get(self, endpoint: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(self.base_url + endpoint, headers=self.headers)
            return response.json()

    async def post(self, endpoint: str, data: Dict[str, Any]):
        async with httpx.AsyncClient() as client:
            response = await client.post(self.base_url + endpoint, json=data, headers=self.headers)
            return response.json()

    async def put(self, endpoint: str, data: Dict[str, Any]):
        async with httpx.AsyncClient() as client:
            response = await client.put(self.base_url + endpoint, json=data, headers=self.headers)
            return response.json()

    async def delete(self, endpoint: str):
        async with httpx.AsyncClient() as client:
            response = await client.delete(self.base_url + endpoint, headers=self.headers)
            return response.json()


# -----------------------------
# TOOL 1: LIST PROJECTS
# -----------------------------
async def list_projects(client: ZohoClient):
    return await client.get("/projects/")


# -----------------------------
# TOOL 2: LIST TASKS
# -----------------------------
async def list_tasks(client: ZohoClient, project_id: str):
    return await client.get(f"/projects/{project_id}/tasks/")


# -----------------------------
# TOOL 3: GET TASK DETAILS
# -----------------------------
async def get_task_details(client: ZohoClient, task_id: str):
    return await client.get(f"/tasks/{task_id}/")


# -----------------------------
# TOOL 4: CREATE TASK
# -----------------------------
async def create_task(client: ZohoClient, project_id: str, task_data: Dict[str, Any]):
    payload = {
        "name": task_data.get("name"),
        "description": task_data.get("description", ""),
        "priority": task_data.get("priority", "medium"),
        "status": task_data.get("status", "open"),
    }
    return await client.post(f"/projects/{project_id}/tasks/", payload)


# -----------------------------
# TOOL 5: UPDATE TASK
# -----------------------------
async def update_task(client: ZohoClient, task_id: str, update_data: Dict[str, Any]):
    return await client.put(f"/tasks/{task_id}/", update_data)


# -----------------------------
# TOOL 6: DELETE TASK
# -----------------------------
async def delete_task(client: ZohoClient, task_id: str):
    return await client.delete(f"/tasks/{task_id}/")


# -----------------------------
# TOOL 7: LIST PROJECT MEMBERS
# -----------------------------
async def list_project_members(client: ZohoClient, project_id: str):
    return await client.get(f"/projects/{project_id}/users/")


# -----------------------------
# TOOL 8: TASK UTILISATION
# -----------------------------
async def get_task_utilisation(client: ZohoClient, project_id: str):
    return await client.get(f"/projects/{project_id}/taskutilization/")