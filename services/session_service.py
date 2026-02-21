import uuid
import time
import os

# Load from environment with safe default
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))  # 1 hour

# Use DynamoDB only in cloud; locally use in-memory store so dev doesn't need AWS permissions
CLOUD_ENV = os.environ.get("CLOUD_ENV", "false").lower() == "true"


class _MemorySessionStore:
    """In-memory session store for local development (no DynamoDB required)."""

    def __init__(self):
        self._sessions = {}

    def create_session(self, user=None, data=None):
        session_id = str(uuid.uuid4())
        now = int(time.time())
        item = {
            "session_id": session_id,
            "created_at": now,
            "expires_at": now + SESSION_TTL_SECONDS,
            "data": data or {},
        }
        if user:
            item["user_id"] = user.get("user_id")
            item["role"] = user.get("role")
        self._sessions[session_id] = item
        return session_id

    def get_session(self, session_id: str):
        item = self._sessions.get(session_id)
        if not item:
            return None
        if item.get("expires_at", 0) < int(time.time()):
            self.delete_session(session_id)
            return None
        return item

    def save_session(self, session_id: str, data: dict):
        if session_id not in self._sessions:
            return
        now = int(time.time())
        self._sessions[session_id]["data"] = data
        self._sessions[session_id]["expires_at"] = now + SESSION_TTL_SECONDS

    def delete_session(self, session_id: str):
        self._sessions.pop(session_id, None)


class _DynamoDBSessionStore:
    """DynamoDB-backed session store for production."""

    def __init__(self):
        import boto3
        region = os.getenv("AWS_REGION", "ap-south-1")
        dynamodb = boto3.resource("dynamodb", region_name=region)
        table_name = os.getenv("DYNAMODB_TABLE", "sessions")
        self.table = dynamodb.Table(table_name)

    def create_session(self, user=None, data=None):
        session_id = str(uuid.uuid4())
        now = int(time.time())
        item = {
            "session_id": session_id,
            "created_at": now,
            "expires_at": now + SESSION_TTL_SECONDS,
            "data": data or {},
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
            if item.get("expires_at", 0) < int(time.time()):
                self.delete_session(session_id)
                return None
            return item
        except Exception as e:
            print(f"Error getting session: {e}")
            return None

    def save_session(self, session_id: str, data: dict):
        try:
            now = int(time.time())
            self.table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET #d = :data, expires_at = :exp",
                ExpressionAttributeNames={"#d": "data"},
                ExpressionAttributeValues={
                    ":data": data,
                    ":exp": now + SESSION_TTL_SECONDS,
                },
            )
        except Exception as e:
            print(f"Error saving session: {e}")

    def delete_session(self, session_id: str):
        self.table.delete_item(Key={"session_id": session_id})


class SessionService:
    def __init__(self):
        if CLOUD_ENV:
            self._store = _DynamoDBSessionStore()
        else:
            self._store = _MemorySessionStore()

    def create_session(self, user: dict = None, data: dict = None) -> str:
        return self._store.create_session(user=user, data=data)

    def get_session(self, session_id: str):
        return self._store.get_session(session_id)

    def save_session(self, session_id: str, data: dict):
        self._store.save_session(session_id, data)

    def validate_session(self, session_id: str) -> bool:
        return self.get_session(session_id) is not None

    def delete_session(self, session_id: str):
        self._store.delete_session(session_id)
