import boto3
import uuid
import time
import os

# Load from environment with safe default
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))  # 1 hour

class SessionService:
    def __init__(self):
        region = os.getenv("AWS_REGION", "ap-south-1")
        dynamodb = boto3.resource("dynamodb", region_name=region)
        table_name = os.getenv("DYNAMODB_TABLE", "sessions")
        self.table = dynamodb.Table(table_name)

    def create_session(self, user: dict = None, data: dict = None) -> str:
        session_id = str(uuid.uuid4())
        now = int(time.time())
        
        item = {
            "session_id": session_id,
            "created_at": now,
            "expires_at": now + SESSION_TTL_SECONDS,
            "data": data or {}
        }
        
        if user:
            item["user_id"] = user.get("user_id")
            item["role"] = user.get("role")
            
        self.table.put_item(Item=item)
        return session_id

    def get_session(self, session_id: str): 
        try:
            response = self.table.get_item(Key={"session_id": session_id})
            item = response.get("Item")
            if not item:
                return None
                
            # Check expiry
            if item.get("expires_at", 0) < int(time.time()):
                self.delete_session(session_id)
                return None
                
            return item
        except Exception as e:
            print(f"Error getting session: {e}")
            return None

    def save_session(self, session_id: str, data: dict):
        """Update session data and extend expiry"""
        try:
            now = int(time.time())
            self.table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET #d = :data, expires_at = :exp",
                ExpressionAttributeNames={"#d": "data"},
                ExpressionAttributeValues={
                    ":data": data,
                    ":exp": now + SESSION_TTL_SECONDS
                }
            )
        except Exception as e:
            print(f"Error saving session: {e}")

    def validate_session(self, session_id: str) -> bool:
        return self.get_session(session_id) is not None

    def delete_session(self, session_id: str):
        self.table.delete_item(Key={"session_id": session_id})
