import httpx
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from config import settings


class ZohoClient:
    """Wrapper around Zoho Projects REST API with auto-token refresh"""
    
    def __init__(self, user_id: str, access_token: str, refresh_token: str, expires_at: float):
        """
        Initialize client with user's OAuth tokens
        
        Args:
            user_id: Unique identifier for this user
            access_token: Current access token
            refresh_token: Refresh token for getting new access tokens
            expires_at: Timestamp when access_token expires
        """
        self.user_id = user_id
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.base_url = settings.zoho_api_base_url
        self.portal_id: Optional[str] = None
    
    async def ensure_valid_token(self):
        """Check if token is expired; refresh silently if needed"""
        if datetime.now().timestamp() > self.expires_at:
            await self.refresh_access_token()
    
    async def refresh_access_token(self):
        """Exchange refresh token for new access token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://accounts.zoho.in/oauth/v2/token",
                data={
                    "client_id": settings.zoho_client_id,
                    "client_secret": settings.zoho_client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            self.access_token = data["access_token"]
            self.expires_at = datetime.now().timestamp() + data.get("expires_in", 3600) - 60
            # TODO: Save new tokens to DB for persistence
    
    async def _ensure_portal_id(self):
        """Fetch and cache the portal ID (required for all project API calls in v3)"""
        if self.portal_id:
            return
        await self.ensure_valid_token()
        url = f"{self.base_url}/portals"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            portals = response.json()
            if portals and isinstance(portals, list):
                self.portal_id = str(portals[0]["id"])
                print(f"[DEBUG] Resolved Portal ID: {self.portal_id}")

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request to Zoho API v3"""
        await self.ensure_valid_token()
        
        if endpoint == "portals":
            url = f"{self.base_url}/{endpoint}"
        else:
            try:
                await self._ensure_portal_id()
            except Exception as e:
                print(f"[WARN] Could not ensure portal ID: {e}")
                self.portal_id = None

            if self.portal_id:
                url = f"{self.base_url}/portal/{self.portal_id}/{endpoint}"
            else:
                url = f"{self.base_url}/{endpoint}"
            
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
            
            # 🔥 DEBUG: Print everything
            print(f"[DEBUG] URL: {url}")
            print(f"[DEBUG] Status: {response.status_code}")
            print(f"[DEBUG] Response: {response.text}")
            
            if not response.is_success:
                raise Exception(f"API Error {response.status_code}: {response.text}")
                
            if not response.text.strip() or response.status_code == 204:
                return {"status": "success", "status_code": response.status_code}
            try:
                return response.json()
            except (json.JSONDecodeError, ValueError):
                return {"status": "success", "message": response.text}



    
    # ===== READ OPERATIONS =====
    
    async def list_projects(self) -> Dict[str, Any]:
        """Fetch all projects for authenticated user"""
        return await self._request("GET", "projects")
    
    async def list_tasks(self, project_id: str, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Fetch tasks for a project with optional filters
        
        Args:
            project_id: Zoho project ID
            filters: Dict with optional keys: status, assignee, due_date_before, due_date_after
        """
        params = filters or {}
        return await self._request("GET", f"projects/{project_id}/tasks", params=params)
    
    async def get_task_details(self, project_id: str, task_id: str) -> Dict[str, Any]:
        """Fetch full details of a single task"""
        return await self._request("GET", f"projects/{project_id}/tasks/{task_id}")
    
    async def list_project_members(self, project_id: str) -> Dict[str, Any]:
        """Get all members of a project with their roles"""
        return await self._request("GET", f"projects/{project_id}/users")
    
    async def get_task_utilisation(self, project_id: str) -> Dict[str, Any]:
        """Summarise task load per member across a project"""
        # This endpoint may not exist; you might need to aggregate from list_tasks + list_members
        return await self._request("GET", f"projects/{project_id}/reports/task_load")
    
    # ===== WRITE OPERATIONS =====
    
    async def create_task(self, project_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new task in a project"""
        return await self._request("POST", f"projects/{project_id}/tasks", json=task_data)
    
    async def update_task(self, project_id: str, task_id: str, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update task status, assignee, due date, or priority using PATCH and standard v3 schema"""
        payload = {}
        # Fallback map for default portal statuses
        STATUS_MAP = {
            "open": "451914000000000185",
            "closed": "451914000000000188",
            "completed": "451914000000000188",  # map completed to closed
            "done": "451914000000000188"
        }
        
        for k, v in task_data.items():
            if k == "status" and isinstance(v, str):
                # Zoho Projects v3 requires the status ID, not the name
                status_key = v.lower()
                if status_key in STATUS_MAP:
                    payload["status"] = {"id": STATUS_MAP[status_key]}
                else:
                    payload["status"] = {"name": v.capitalize()} # Fallback, though likely to fail
            elif k == "priority" and isinstance(v, str):
                payload["priority"] = v.lower()
            else:
                payload[k] = v
        return await self._request("PATCH", f"projects/{project_id}/tasks/{task_id}", json=payload)
    
    async def delete_task(self, project_id: str, task_id: str) -> Dict[str, Any]:
        """Delete a task"""
        return await self._request("DELETE", f"projects/{project_id}/tasks/{task_id}")
