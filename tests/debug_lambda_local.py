import sys
import os
import traceback
import json

sys.path.append(os.getcwd())
os.environ['AWS_LAMBDA_FUNCTION_NAME'] = 'test-function'
os.environ['DEMO_MODE'] = 'true'
os.environ['OPENAI_API_KEY'] = 'test-key'

print("--- Starting Debug Script ---")

try:
    from handlers import chat_handler
    print("SUCCESS: handlers.chat_handler imported")
except Exception:
    print("CRITICAL FAILURE: Could not import chat_handler")
    traceback.print_exc()
    sys.exit(1)

def create_event(path, method="GET", stage="Prod", body=None):
    return {
        "path": path,
        "httpMethod": method,
        "headers": {"Content-Type": "application/json"},
        "queryStringParameters": {},
        "body": json.dumps(body) if body else None,
        "isBase64Encoded": False,
        "requestContext": {"stage": stage}
    }

# Test 1: Hit /agent?agent_id=travel-bot-default
print("\n--- Test 1: GET /agent?agent_id=travel-bot-default ---")
event = create_event("/agent", stage="Prod")
event["queryStringParameters"] = {"agent_id": "travel-bot-default"}
response = chat_handler.process(event, None)
print(f"Status: {response['statusCode']}")
if response['statusCode'] == 200:
    body = response.get('body', '')
    if 'MCP_SERVER_URL' in body:
        print("SUCCESS: MCP_SERVER_URL injected into template")
    else:
        print("FAIL: MCP_SERVER_URL NOT found in template")
else:
    print(f"FAIL: Status {response['statusCode']}")

# Test 2: /api/reset
print("\n--- Test 2: POST /api/reset ---")
event = create_event("/api/reset", method="POST", stage="Prod")
response = chat_handler.process(event, None)
print(f"Status: {response['statusCode']}")
print(f"Body: {response.get('body')}")

# Test 3: Admin Agent (Path Param Injection)
print("\n--- Test 3: GET /admin/agents/travel-bot-default ---")
event = create_event("/admin/agents/travel-bot-default", stage="Prod")
# Mock auth for this test (since we can't easily login in script)
# We'll just check if the handler routes it correctly to app.admin_agent 
# which might return 401 or data depending on mock auth
try:
    from core.web import app_tools
    app_tools.session['logged_in'] = True
    app_tools.session['username'] = 'admin'
    
    response = chat_handler.process(event, None)
    print(f"Status: {response['statusCode']}")
    # 200 means it hit the endpoint and returned data
    # 404 means route not matched or agent not found
    if response['statusCode'] == 200:
          print("SUCCESS: Admin agent route working")
    else:
          print(f"CHECK: {response.get('body')}")

except Exception as e:
    print(f"Error mocking auth: {e}")

# Test 4: Static File with Stage Prefix
print("\n--- Test 4: GET /Prod/static/logo-light.png ---")
# Simulate API Gateway passing path WITH stage (common in some configs)
event = create_event("/Prod/static/logo-light.png", stage="Prod")
response = chat_handler.process(event, None)
print(f"Status: {response['statusCode']}")
if response['statusCode'] == 200:
    print("SUCCESS: Static file served via stage-prefixed path")
else:
    print(f"FAIL: {response.get('statusCode')} - {str(response.get('body'))[:100]}")
