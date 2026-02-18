import os

# Configuration file for the Travel Inspiration Hub

# OpenAI API Configuration - Required: set OPENAI_API_KEY environment variable
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# Flask Configuration
DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '5008'))

# Agent Foundation Configuration
if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    AGENTS_STORAGE_PATH = '/tmp/agents.json'
    USERS_STORAGE_PATH = '/tmp/users.json'
else:
    AGENTS_STORAGE_PATH = os.getenv('AGENTS_STORAGE_PATH', 'storage/agents.json')
    USERS_STORAGE_PATH = os.getenv('USERS_STORAGE_PATH', 'storage/users.json')

DEFAULT_AGENT_ID = os.getenv('DEFAULT_AGENT_ID', 'travel-bot-default')

# Gemini API Configuration - Optional: set GEMINI_API_KEY environment variable
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# MCP Server Configuration
MCP_SERVER_URL = os.getenv('MCP_SERVER_URL', 'http://localhost:8001')

# Default LLM provider
DEFAULT_LLM_PROVIDER = os.getenv('DEFAULT_LLM_PROVIDER', 'gemini')

# Default LLM model
DEFAULT_LLM_MODEL = os.getenv('DEFAULT_LLM_MODEL', 'gemini-2.5-flash')

# You can override these settings by creating a .env file with:
# OPENAI_API_KEY=your_api_key_here
# GEMINI_API_KEY=your_gemini_key_here
# DEFAULT_AGENT_ID=your_default_agent_id
# MCP_SERVER_URL=http://localhost:8001

