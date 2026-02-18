import boto3
import os

class UserService:
    def __init__(self):
        region = os.getenv("AWS_REGION", "ap-south-1")
        dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = dynamodb.Table("users")

    def get_user(self, user_id: str):
        response = self.table.get_item(Key={"user_id": user_id})
        return response.get("Item")

    def authenticate(self, user_id: str, password: str):
        user = self.get_user(user_id)
        if not user:
            return None

        # ⚠️ POC ONLY – replace with hashed passwords in prod
        if user["password"] != password:
            return None

        return {
            "user_id": user["user_id"],
            "name": user["name"],
            "role": user["role"]
        }
