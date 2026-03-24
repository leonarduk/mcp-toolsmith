from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools


client = MultiServerMCPClient(
    {
        "petstore": {
            "command": "node",
            "args": ["__OUT_DIR__/dist/index.js"],
            "transport": "stdio",
        }
    }
)

tools = load_mcp_tools(client)
print(f"Loaded {len(tools)} tools from Petstore")