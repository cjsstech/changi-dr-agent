#/agents/mcp_manager.py

import json
import uuid
import os
import urllib.request

CLOUD_ENV = os.environ.get("CLOUD_ENV", "false").lower() == "true"

# MCP MANAGER (Transport + Local Registry)
class McpManager:
    def __init__(self, mcp_api_url: str):
        self.mcp_api_url = mcp_api_url

        # Start with static tool registry
        self.tools = {}
        self.prompts = {}
        self.resources = {}

        # Try to load from MCP Lambda (overrides static tools if successful)
        self.refresh()

    def refresh(self):
        """Refresh the tool registry from the MCP server"""
        try:
            self.initialize()
            self._load_registry()
        except Exception as e:
            print(f"[MCP] Warning: Could not refresh MCP manager: {e}")

    # Internal HTTP Invoke (API Gateway)
    def _invoke(self, method: str, params: dict | None = None):
        request_id = str(uuid.uuid4())

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": request_id
        }

        req = urllib.request.Request(
            self.mcp_api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            raw_result = json.loads(response.read().decode("utf-8"))

        # JSON-RPC error handling
        if "error" in raw_result:
            raise Exception(raw_result["error"])

        return raw_result.get("result")

    # MCP Initialize
    def initialize(self):
        return self._invoke("initialize", {})

    # Load metadata from MCP
    def _load_registry(self):
        tools_data = self._invoke("tools/list", {}) or {}
        prompts_data = self._invoke("prompts/list", {}) or {}
        resources_data = self._invoke("resources/list", {}) or {}

        self.tools = {
            t["name"]: t
            for t in tools_data.get("tools", [])
        }

        self.prompts = {
            p["name"]: p
            for p in prompts_data.get("prompts", [])
        }

        self.resources = {
            r["uri"]: r
            for r in resources_data.get("resources", [])
        }

    # Check if Resource Available
    def is_resource_available(self, resource_uri: str) -> bool:
        return resource_uri in self.resources

    # Check if Resource Available
    def is_tool_enabled(self, tool_name: str) -> bool:
        return tool_name in self.tools

    # Call Tool
    def call_tool(self, tool_name: str, arguments: dict):
        if tool_name not in self.tools:
            raise Exception(f"Tool '{tool_name}' not found")

        return self._invoke(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments
            }
        )

    # Read Resource
    def read_resource(self, resource_uri: str):
        if not self.is_resource_available(resource_uri):
            raise Exception(f"Resource '{resource_uri}' not found")

        return self._invoke(
            "resources/read",
            {
                "uri": resource_uri
            }
        )

    # Get Prompt Metadata
    def get_prompt(self, prompt_name: str):
        if prompt_name not in self.prompts:
            raise Exception(f"Prompt '{prompt_name}' not found")

        return self.prompts[prompt_name]

# Initialize MCP manager: GLOBAL (Persist Across Warm Lambda Invocations)
mcp_manager = (
    McpManager(
        mcp_api_url=os.environ["MCP_API_URL"]
    )
    if CLOUD_ENV
    else McpManager(
        mcp_api_url="http://127.0.0.1:8002"
    )
)
