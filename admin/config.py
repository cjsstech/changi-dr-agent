"""
Configuration for Admin Console
"""
import os

APP_NAME = "Admin Console"
APP_VERSION = "1.0.0"

S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_REGION = os.environ.get("S3_REGION", "ap-south-1")

S3_PREFIX_AGENTS = os.environ.get("S3_PREFIX_AGENTS", "agents/")
S3_PREFIX_WORKFLOWS = os.environ.get("S3_PREFIX_WORKFLOWS", "workflows/")
S3_PREFIX_PROMPTS = os.environ.get("S3_PREFIX_PROMPTS", "prompts/")
S3_PREFIX_FILES = os.environ.get("S3_PREFIX_FILES", "files/")

MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL","http://localhost:8002/mcp")


DEFAULT_LLM_PROVIDER = os.environ.get("DEFAULT_LLM_PROVIDER","openai")
DEFAULT_LLM_MODEL = os.environ.get("DEFAULT_LLM_MODEL","gpt-4o")


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
