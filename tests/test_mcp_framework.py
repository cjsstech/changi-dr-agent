import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Ensure the project root is in sys.path
sys.path.append(os.getcwd())

from mcp import rpc
from mcp.tools import router


class TestMCPFramework(unittest.TestCase):

    def setUp(self):
        self.context = {"user_id": "test_user"}

    def test_jsond_rpc_validation_invalid_json(self):
        """Test that invalid input (not a dict) returns proper error"""
        response = rpc.execute("not a dict", self.context)
        self.assertEqual(response["error"]["code"], -32600)
        self.assertEqual(response["error"]["message"], "Invalid Request")

    def test_json_rpc_validation_invalid_version(self):
        """Test that missing or wrong jsonrpc version returns error"""
        req = {"jsonrpc": "1.0", "method": "test", "id": "1"}
        response = rpc.execute(req, self.context)
        self.assertEqual(response["error"]["code"], -32600)
        self.assertIn("Invalid JSON-RPC version", response["error"]["message"])

    def test_method_not_found(self):
        """Test that unknown methods return Method Not Found"""
        req = {
            "jsonrpc": "2.0",
            "method": "unknown/method",
            "id": "1"
        }
        response = rpc.execute(req, self.context)
        self.assertEqual(response["error"]["code"], -32601)
        self.assertIn("Method not found", response["error"]["message"])

    def test_lifecycle_initialize(self):
        """Test the initialize handshake"""
        req = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": "init-1"
        }
        response = rpc.execute(req, self.context)
        self.assertEqual(response["id"], "init-1")
        self.assertIn("serverInfo", response["result"])
        self.assertIn("capabilities", response["result"])
        self.assertTrue(response["result"]["capabilities"]["tools"]["list"])

    def test_tools_list(self):
        """Test tools/list discovery"""
        # We'll use the real router logic but mock the TOOLS dict
        # or just rely on the fact that existing tools are registered.
        # Let's rely on the real tools since we just verified them.

        req = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": "list-1"
        }
        response = rpc.execute(req, self.context)
        self.assertEqual(response["id"], "list-1")
        tools = response["result"]["tools"]
        self.assertIsInstance(tools, list)
        # We expect at least the 5 tools we added
        tool_names = [t["name"] for t in tools]
        self.assertIn("flight.search", tool_names)
        self.assertIn("visa.check", tool_names)

    @patch("mcp.tools.router.TOOLS")
    def test_tools_call_success(self, mock_tools):
        """Test successful tool execution"""
        # Setup a mock tool
        mock_tool_instance = MagicMock()
        mock_tool_instance.execute.return_value = {"status": "success"}
        mock_tools.get.return_value = mock_tool_instance

        req = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "mock.tool",
                "arguments": {"arg1": "value1"}
            },
            "id": "call-1"
        }

        response = rpc.execute(req, self.context)

        # Verify router lookup
        mock_tools.get.assert_called_with("mock.tool")
        # Verify execution
        mock_tool_instance.execute.assert_called_with({"arg1": "value1"}, self.context)

        # Verify response
        self.assertEqual(response["id"], "call-1")
        self.assertEqual(response["result"], {"status": "success"})

    def test_tools_call_missing_name(self):
        """Test tools/call without name"""
        req = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "arguments": {}
            },
            "id": "err-1"
        }
        response = rpc.execute(req, self.context)
        self.assertEqual(response["error"]["code"], -32602)
        self.assertEqual(response["error"]["message"], "Missing tool name")

    def test_tools_call_unknown_tool(self):
        """Test tools/call with unknown tool name"""
        req = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "non.existent.tool"
            },
            "id": "err-2"
        }
        response = rpc.execute(req, self.context)
        self.assertEqual(response["error"]["code"], -32601)
        self.assertIn("Tool not found", response["error"]["message"])

    @patch("mcp.tools.router.TOOLS")
    def test_tools_call_execution_exception(self, mock_tools):
        """Test handling of exceptions during tool execution"""
        # Setup a mock tool that raises exception
        mock_tool_instance = MagicMock()
        mock_tool_instance.execute.side_effect = ValueError("Something went wrong")
        mock_tools.get.return_value = mock_tool_instance

        req = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "broken.tool"
            },
            "id": "err-3"
        }

        response = rpc.execute(req, self.context)

        self.assertEqual(response["error"]["code"], -32603)
        self.assertEqual(response["error"]["message"], "Tool execution error")
        self.assertIn("Something went wrong", response["error"]["data"])


if __name__ == "__main__":
    unittest.main()