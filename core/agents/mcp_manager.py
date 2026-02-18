#/core/agents/mcp_orchestrator.py
import boto3
import json
import uuid

# Static tool registry (fallback when MCP Lambda is unavailable)
DEFAULT_TOOLS = {
    'flight_api': {
        'name': 'Flight API',
        'description': 'Search flights from Changi Airport API',
        'enabled': True,
        'endpoint_base': 'http://localhost:8001/flights'
    },
    'travel_content': {
        'name': 'Travel Content',
        'description': 'Generate links for Lonely Planet and Trip.com',
        'enabled': True,
        'endpoint_base': 'http://localhost:8001/travel'
    },
    'nowboarding': {
        'name': 'Now Boarding Articles',
        'description': 'Fetch articles from Now Boarding API',
        'enabled': True,
        'endpoint_base': 'http://localhost:8001/nowboarding'
    },
    'maps': {
        'name': 'Maps & Geocoding',
        'description': 'Geocode locations and generate map URLs',
        'enabled': True,
        'endpoint_base': 'http://localhost:8001/maps'
    },
    'browser': {
        'name': 'Browser',
        'description': 'Web navigation, screenshots, and page interaction',
        'enabled': False
    },
    'filesystem': {
        'name': 'File System',
        'description': 'Read and write files',
        'enabled': False
    },
    'database': {
        'name': 'Database',
        'description': 'Query databases',
        'enabled': False
    }
}

# MCP MANAGER (Transport + Local Registry)
class McpManager:
    def __init__(self, mcp_lambda_name: str, region: str = "ap-south-1"):
        self.mcp_lambda_name = mcp_lambda_name
        self.lambda_client = boto3.client("lambda", region_name=region)

        # Start with static tool registry
        self.tools = dict(DEFAULT_TOOLS)
        self.prompts = {}
        self.resources = {}

        # Try to load from MCP Lambda (overrides static tools if successful)
        try:
            self.initialize()
            self._load_registry()
            # Only use Lambda results if they returned tools
            if not self.tools:
                print("[MCP] Lambda returned no tools, keeping static registry")
                self.tools = dict(DEFAULT_TOOLS)
        except Exception as e:
            print(f"[MCP] Warning: Could not initialize MCP manager: {e}")
            print(f"[MCP] Using static tool registry as fallback")
            self.tools = dict(DEFAULT_TOOLS)

    # Internal Lambda Invoke
    def _invoke(self, method: str, params: dict | None = None):
        request_id = str(uuid.uuid4())

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": request_id
        }

        response = self.lambda_client.invoke(
            FunctionName=self.mcp_lambda_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        raw_result = json.loads(response["Payload"].read())

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
    def call_tool(self, tool_name: str, input_data: dict):
        if tool_name not in self.tools:
            raise Exception(f"Tool '{tool_name}' not found")

        return self._invoke(
            "tools/call",
            {
                "name": tool_name,
                "arguments": input_data
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
mcp_manager = McpManager(mcp_lambda_name="changi-dr-mcp", region="ap-south-1")