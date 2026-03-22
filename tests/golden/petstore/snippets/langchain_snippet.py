"""Minimal LangChain wiring for the generated MCP server."""

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools


async def build_tools():
    client = MultiServerMCPClient(
        {
            "petstore": {
                "command": "node",
                "args": ["__SERVER_PATH__/dist/index.js"],
                "env": {"API_BASE_URL": "https://api.example.com"},
                "transport": "stdio",
            }
        }
    )
    return await load_mcp_tools(client)