#/core/agents/mcp_manager.py
# Static tool registry (fallback when MCP Lambda is unavailable)

import json
import uuid
import os
import requests

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
    def __init__(self, mcp_api_url: str, api_key: str):
        # AWS API Gateway with /mcp/{proxy+} requires a path suffix.
        # If the URL ends in /mcp or /mcp/, append /rpc to prevent 403 Forbidden mapping errors.
        if mcp_api_url.endswith('/mcp'):
            mcp_api_url += '/rpc'
        elif mcp_api_url.endswith('/mcp/'):
            mcp_api_url += 'rpc'
            
        self.mcp_api_url = mcp_api_url
        self.api_key = api_key

        # Start with static tool registry
        self.tools = {}
        self.prompts = {}
        self.resources = {}

        # Try to load from MCP Lambda (overrides static tools if successful)
        try:
            self.initialize()
            self._load_registry()
        except Exception as e:
            print(f"[MCP] Warning: Could not initialize MCP manager: {e}")

    # Internal HTTP Invoke (API Gateway)
    def _invoke(self, method: str, params: dict | None = None):
        request_id = str(uuid.uuid4())

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": request_id
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "User-Agent": "McpManager/1.0"
        }

        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[MCP Manager] 🔌 Calling MCP method: {method} at {self.mcp_api_url}")
            logger.info(f"[MCP Manager] 📤 Request params: {params}")
            
            response = requests.post(
                self.mcp_api_url,
                json=payload,
                headers=headers,
                timeout=45,
                verify=False # Bypass strict SSL for development environments
            )
            response.raise_for_status()
            raw_result = response.json()
            logger.info(f"[MCP Manager] 📥 Response: {raw_result}")
        except requests.exceptions.RequestException as e:
            # Parse error specifically if there's a response
            if getattr(e, 'response', None) is not None:
                try:
                    error_json = e.response.json()
                    raise Exception(f"HTTP Error {e.response.status_code}: {json.dumps(error_json)}")
                except json.JSONDecodeError:
                    raise Exception(f"HTTP Error {e.response.status_code}: {e.response.text}")
            raise Exception(f"Request failed: {e}")

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

    # Call Tool
    def call_tool(self, tool_name: str, input_data: dict):
        if tool_name not in self.tools:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Tool '{tool_name}' not found in registry, attempting call anyway.")

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

    # Check if Resource Available
    def is_resource_available(self, resource_uri: str) -> bool:
        return resource_uri in self.resources

    def is_tool_enabled(self, tool_id: str) -> bool:
        mapping = {
            'flight_api': 'flights.manage',
            'nowboarding': 'nowboarding.articles',
            'maps': 'maps.manage',
            'travel_content': 'travel.generate-links',
        }
        return mapping.get(tool_id, tool_id) in self.tools

    def get_enabled_tools(self) -> list:
        # Returns old-style tool_ids that the agent is expecting
        return ['flight_api', 'nowboarding', 'maps', 'travel_content']

    def get_tool_definitions_for_llm(self) -> list:
        # Provide the hardcoded legacy LLM schema expected by the old agent executor, mapping internally
        return [
            {
                "name": "flight_api_search",
                "description": "search function for flight_api",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "destination": {"type": "string", "description": "Destination city code or name"},
                        "scheduled_dates": {"type": "array", "items": {"type": "string"}, "description": "Dates to search"},
                        "preferred_times": {"type": "array", "items": {"type": "string"}, "description": "Morning, etc"},
                        "limit": {"type": "integer", "description": "Limit flights"}
                    },
                    "required": ["destination", "scheduled_dates"]
                }
            },
            {
                "name": "nowboarding_fetch_articles",
                "description": "fetch_articles function for nowboarding",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "destination": {"type": "string", "description": "Destination name to fetch articles for"},
                        "limit": {"type": "integer", "description": "Number of articles"}
                    },
                    "required": ["destination"]
                }
            }
        ]

    def execute_tool(self, tool_id: str, tool_name: str, arguments: dict):
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[MCP Manager] 🚀 Execute tool mapped request: {tool_id}.{tool_name}")
        
        try:
            if tool_id == 'flight_api':
                return self.call_tool('flights.manage', {**arguments, 'request_type': tool_name})
            elif tool_id == 'nowboarding' and tool_name == 'fetch_articles':
                return self.call_tool('nowboarding.articles', arguments)
            elif tool_id == 'maps':
                return self.call_tool('maps.manage', {**arguments, 'request_type': tool_name})
            elif tool_id == 'travel_content':
                # Map old specific URL type logic to new clean types if they have _url
                mapped_type = tool_name
                if mapped_type == 'lonely_planet_url':
                    mapped_type = 'lonely_planet'
                elif mapped_type == 'trip_com_url':
                    mapped_type = 'trip_com'
                return self.call_tool('travel.generate-links', {**arguments, 'type': mapped_type})
            return self.call_tool(tool_id, arguments)
        except Exception as e:
            logger.error(f"[MCP Manager] ❌ Error executing tool {tool_id}.{tool_name}: {e}")
            return {'success': False, 'error': str(e), 'tool_id': tool_id, 'tool_name': tool_name}

# Initialize MCP manager: GLOBAL (Persist Across Warm Lambda Invocations)
mcp_manager = McpManager(mcp_api_url=os.environ["MCP_API_URL"],  api_key=os.environ["MCP_API_KEY"])