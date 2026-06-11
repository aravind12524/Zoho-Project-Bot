from zoho_tools import create_task, delete_task
from zoho_client import ZohoClient


class ActionAgent:
    def __init__(self, access_token: str):
        self.client = ZohoClient(access_token)

    async def run(self, message: str):
        return {
            "requires_confirmation": True,
            "message": f"Confirm action: {message}"
        }