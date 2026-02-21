# /core/web/app_tools.py
import os
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape


session = {}
request = None

# API Gateway stage prefix (set per-request by the handler)
_stage_prefix = ""

def set_stage_prefix(stage: str):
    """Set the API Gateway stage prefix (e.g., 'Prod') for URL generation."""
    global _stage_prefix
    _stage_prefix = f"/{stage}" if stage else ""


# Jinja2 setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "../../chat/templates")

_jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"])
)


def render_template(template_name, **context):
    """
    Flask-compatible render_template replacement.
    Returns a Lambda-compatible HTTP response.
    """
    template = _jinja_env.get_template(template_name)
    html = template.render(**context)

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/html; charset=utf-8"
        },
        "body": html
    }


# HTTP helpers (Flask-compatible)
def jsonify(obj, status=200):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(obj)
    }


def redirect(location):
    return {
        "statusCode": 302,
        "headers": {
            "Location": location
        },
        "body": ""
    }


def url_for(endpoint, **values):
    """
    Minimal Flask url_for compatibility.
    Maps Flask endpoint names to actual route paths and includes
    API Gateway stage prefix in generated URLs.
    """

    # Handle static files
    if endpoint == "static":
        filename = values.get("filename", "")
        return f"{_stage_prefix}/static/{filename}"

    # Flask endpoint name → actual route path mapping
    _route_map = {
        "index": "/",
        "login": "/login",
        "logout": "/logout",
        "agent_chat": "/agent",
        "agent_chat_api": "/agent/chat",
        "agent_chat_stream_api": "/agent/chat/stream",
        "workflow_chat": "/workflow",
        "workflow_chat_api": "/workflow/chat",
        "workflow_chat_stream_api": "/workflow/chat/stream",
        "api_reset": "/api/reset",
        "admin": "/admin",
        "admin_agents": "/admin/agents",
        "admin_agent": "/admin/agent",
        "admin_prompts": "/admin/prompts",
        "admin_prompt": "/admin/prompt",
        "admin_mcp_tools": "/admin/mcp/tools",
        "admin_workflows": "/admin/workflows",
        "admin_workflow": "/admin/workflow",
    }

    path = _route_map.get(endpoint)
    if path is None:
        # Fallback: treat as literal path
        path = endpoint if endpoint.startswith("/") else f"/{endpoint}"

    # Path parameters: agent_chat with agent_id → /agent/<agent_id>
    if endpoint == "agent_chat" and "agent_id" in values:
        v = dict(values)
        agent_id = v.pop("agent_id")
        path = f"/agent/{agent_id}"
        return f"{_stage_prefix}{path}" if not v else f"{_stage_prefix}{path}?{__urlencode(v)}"

    # workflow_chat with workflow_id → /workflow/<workflow_id>
    if endpoint == "workflow_chat" and "workflow_id" in values:
        v = dict(values)
        workflow_id = v.pop("workflow_id")
        path = f"/workflow/{workflow_id}"
        return f"{_stage_prefix}{path}" if not v else f"{_stage_prefix}{path}?{__urlencode(v)}"

    # Build query string from remaining values
    query_params = dict(values)
    if query_params:
        return f"{_stage_prefix}{path}?{__urlencode(query_params)}"

    return f"{_stage_prefix}{path}"


def __urlencode(params):
    from urllib.parse import urlencode
    return urlencode(params)



# Register url_for in Jinja globals
_jinja_env.globals["url_for"] = url_for


class Response(dict):
    """
    Minimal Flask Response compatibility.
    Used mainly for SSE endpoints.
    """
    def __init__(self, body, mimetype=None, headers=None, status=200):
        super().__init__()
        self["statusCode"] = status
        self["headers"] = headers or {}

        if mimetype:
            self["headers"]["Content-Type"] = mimetype

        self["body"] = body
