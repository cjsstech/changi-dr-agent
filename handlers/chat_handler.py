#/handlers/chat_handler.py
"""
Lambda Request Handler cum request path router
"""
import traceback
from core.web.lambda_request import build_lambda_request
import chat.app as app
import core.web.app_tools as app_tools # for session/request injection
import os
import mimetypes
import base64


from http.cookies import SimpleCookie
from services.session_service import SessionService

# Global service instance overrides (to reuse connection)
session_service = SessionService()

def normalize_response(response):
    """
    Convert Flask-style responses to Lambda proxy integration format.
    Handles: tuple (body, status), bare strings, and already-correct dicts.
    """
    if isinstance(response, tuple):
        body, status = response
        if isinstance(body, dict) and "statusCode" in body:
            # jsonify() already returns a Lambda dict; just override status
            body["statusCode"] = status
            return body
        elif isinstance(body, dict):
            import json
            return {"statusCode": status, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}
        else:
            return {"statusCode": status, "headers": {"Content-Type": "text/html; charset=utf-8"}, "body": str(body)}
    elif isinstance(response, str):
        return {"statusCode": 200, "headers": {"Content-Type": "text/html; charset=utf-8"}, "body": response}
    elif isinstance(response, dict) and "statusCode" in response:
        return response
    else:
        return {"statusCode": 500, "body": "Invalid response format"}


def process(event, context):
    session_id = None
    try:
        lm_request = build_lambda_request(event)
        path = lm_request.path
        method = lm_request.method

        # Set stage prefix for URL generation (e.g., /Prod)
        app_tools.set_stage_prefix(lm_request.stage)

        # Initialize mock globals for auth_service compatibility
        app_tools.request = lm_request
        app_tools.session.clear() # Reset session
        
        # 1. Load Session
        cookie_header = lm_request.headers.get("Cookie", "") or lm_request.headers.get("cookie", "")
        cookie = SimpleCookie(cookie_header)
        
        session_data = None
        if "session_id" in cookie:
            session_id = cookie["session_id"].value
            session_data = session_service.get_session(session_id)
            
        if session_data:
            # Populate session dict
            app_tools.session.update(session_data.get("data", {}))
        else:
            # Create new session
            session_id = session_service.create_session()
            
        # 2. Route Request
        result = _route_request(path, method, lm_request)
        
        # 3. Save Session
        # We save the session back to DynamoDB
        session_service.save_session(session_id, dict(app_tools.session))

        # Normalize response
        normalized = normalize_response(result)
        
        # 4. Set Cookie
        # We need to ensure headers dict exists
        if "headers" not in normalized:
            normalized["headers"] = {}
            
        # Add Set-Cookie header
        # Note: API Gateway might need case-sensitive header handling or specific configuration for multiple cookies
        # For simple session cookie:
        normalized["headers"]["Set-Cookie"] = f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax; Max-Age=3600"
        
        return normalized

    except Exception as e:
        print(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": str(e)
        }


def _route_request(path, method, lm_request):
    """Route the request to the appropriate app handler."""
    # Public routes
    if path == "/" and method == "GET":
        return app.index(lm_request)

    if path == "/login":
        return app.login(lm_request)

    if path == "/logout":
        return app.logout(lm_request)

    if path == "/agent" and method == "GET":
        return app.agent_chat(lm_request)

    # Handle /agent/<agent_id> path-based URLs
    if path.startswith("/agent/") and not path.startswith("/agent/chat") and method == "GET":
        agent_id = path.split("/agent/", 1)[1].split("/")[0]
        if agent_id:
            lm_request.args['agent_id'] = agent_id
            return app.agent_chat(lm_request)

    if path == "/agent/chat" and method == "POST":
        return app.agent_chat_api(lm_request)

    if path == "/agent/chat/stream" and method == "POST":
        return app.agent_chat_stream_api(lm_request)

    if path == "/workflow" and method == "GET":
        return app.workflow_chat(lm_request)

    if path == "/workflow/chat" and method == "POST":
        return app.workflow_chat_api(lm_request)

    if path == "/workflow/chat/stream" and method == "POST":
        return app.workflow_chat_stream_api(lm_request)

    if path == "/api/reset" and method == "POST":
        return app.reset_session(lm_request)

    # -------------------------
    # Admin routes
    # -------------------------
    if path == "/admin":
        return app.admin(lm_request)

    if path == "/admin/agents":
        return app.admin_agents(lm_request)

    # Handle /admin/agents/<agent_id> (frontend uses path param, backend expects query param)
    if path.startswith("/admin/agents/"):
        agent_id = path.split("/")[-1]
        if agent_id:
            lm_request.args['agent_id'] = agent_id
            return app.admin_agent(lm_request)

    if path == "/admin/agent":
        return app.admin_agent(lm_request)

    if path == "/admin/prompts":
        return app.admin_prompts(lm_request)

    if path == "/admin/prompt":
        return app.admin_prompt(lm_request)

    if path == "/admin/mcp/tools":
        return app.admin_mcp_tools(lm_request)

    if path == "/admin/workflows":
        return app.admin_workflows(lm_request)

    if path == "/admin/workflow":
        return app.admin_workflow(lm_request)

    if path == "/admin/workflow/validate":
        return app.validate_workflow(lm_request)

    if path == "/admin/workflow/compile":
        return app.compile_workflow(lm_request)

    # Favicon handler (browsers always request this)
    if path == "/favicon.ico":
        return {"statusCode": 204, "body": ""}

    # -------------------------
    # Static Files (Lambda-served for POC)
    # -------------------------
    if path.startswith("/static/"):
        # Security: Prevent directory traversal
        if ".." in path:
             return {"statusCode": 403, "body": "Forbidden"}

        relative_path = path[len("/static/"):]
        # Assuming typical Lambda CWD is task root
        static_file_path = os.path.join(os.getcwd(), "chat", "static", relative_path)

        if os.path.exists(static_file_path) and os.path.isfile(static_file_path):
            mime_type, _ = mimetypes.guess_type(static_file_path)
            if not mime_type:
                mime_type = "application/octet-stream"

            with open(static_file_path, "rb") as f:
                content = f.read()

            # Determine if text or binary for response format
            is_text = mime_type.startswith("text/") or mime_type in ["application/javascript", "application/json", "application/xml"]
            
            if is_text:
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": mime_type},
                    "body": content.decode("utf-8")
                }
            else:
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": mime_type},
                    "body": base64.b64encode(content).decode("utf-8"),
                    "isBase64Encoded": True
                }
        else:
            return {"statusCode": 404, "body": "File not found"}

    return {
        "statusCode": 404,
        "body": "Chat route not found"
    }

