import json
import pytest

from handlers import handler


def make_event(method="GET", path="/", body=None):
    """Create fake API Gateway event"""

    return {
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body) if body else None,
        "headers": {},
        "queryStringParameters": {},
    }


def test_mcp_initialize():
    """Test MCP initialize"""

    event = make_event(
        method="POST",
        path="/mcp",
        body={
            "jsonrpc": "2.0",
            "id": "1",
            "method": "initialize"
        }
    )

    response = handler(event, None)

    assert response["statusCode"] == 200

    body = json.loads(response["body"])

    assert body["jsonrpc"] == "2.0"
    assert "result" in body
    assert "serverInfo" in body["result"]


def test_mcp_invalid_method():
    """Test unknown MCP method"""

    event = make_event(
        method="POST",
        path="/mcp",
        body={
            "jsonrpc": "2.0",
            "id": "2",
            "method": "unknown/method"
        }
    )

    response = handler(event, None)

    body = json.loads(response["body"])

    assert "error" in body


def test_chat_missing_agent():
    """Chat without agent_id"""

    event = make_event(
        method="POST",
        path="/chat",
        body={
            "message": "Hello"
        }
    )

    response = handler(event, None)

    assert response["statusCode"] == 400


def test_chat_invalid_agent():
    """Chat with invalid agent"""

    event = make_event(
        method="POST",
        path="/chat/invalid-agent",
        body={
            "message": "Hello"
        }
    )

    response = handler(event, None)

    assert response["statusCode"] in (400, 500)


def test_admin_list_agents():
    """List agents"""

    event = make_event(
        method="GET",
        path="/admin/agents"
    )

    response = handler(event, None)

    assert response["statusCode"] == 200

    body = json.loads(response["body"])

    assert "agents" in body or "success" in body


def test_admin_create_agent():
    """Create agent"""

    event = make_event(
        method="POST",
        path="/admin/agents",
        body={
            "id": "test-agent",
            "name": "Test Agent",
            "llm_provider": "openai",
            "llm_model": "gpt-4"
        }
    )

    response = handler(event, None)

    assert response["statusCode"] in (200, 201)


def test_admin_get_agent():
    """Get agent"""

    event = make_event(
        method="GET",
        path="/admin/agents/test-agent"
    )

    response = handler(event, None)

    assert response["statusCode"] in (200, 404)


def test_admin_list_prompts():
    """List prompts"""

    event = make_event(
        method="GET",
        path="/admin/prompts"
    )

    response = handler(event, None)
    assert response["statusCode"] == 200


def test_admin_create_prompt():
    """Create prompt"""

    event = make_event(
        method="POST",
        path="/admin/prompts",
        body={
            "filename": "test_prompt",
            "content": "Hello this is a test prompt"
        }
    )

    response = handler(event, None)

    assert response["statusCode"] in (200, 201, 400)


def test_admin_list_workflows():
    """List workflows"""

    event = make_event(
        method="GET",
        path="/admin/workflows"
    )

    response = handler(event, None)

    assert response["statusCode"] == 200


def test_admin_mcp_tools():
    """List MCP tools"""

    event = make_event(
        method="GET",
        path="/admin/mcp/tools"
    )

    response = handler(event, None)

    assert response["statusCode"] == 200


def test_invalid_route():
    """Unknown route"""

    event = make_event(
        method="GET",
        path="/unknown/route"
    )

    response = handler(event, None)

    assert response["statusCode"] == 404


def test_cors_preflight():
    """CORS OPTIONS"""

    event = make_event(
        method="OPTIONS",
        path="/admin/agents"
    )

    response = handler(event, None)

    assert response["statusCode"] == 200
    assert "Access-Control-Allow-Origin" in response["headers"]


def test_invalid_json():
    """Invalid JSON body"""

    event = {
        "httpMethod": "POST",
        "path": "/chat/test",
        "body": "{bad json"
    }

    response = handler(event, None)

    assert response["statusCode"] in (400, 500)
