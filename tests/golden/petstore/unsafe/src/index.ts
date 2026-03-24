import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createServer } from "node:http";
import type { IncomingMessage, ServerResponse } from "node:http";
import { registerAdminTools } from "./tools/admin.js";
import { registerPetsTools } from "./tools/pets.js";
const server = new McpServer({
  name: "generated-mcp-server",
  version: "0.1.0",
});

registerAdminTools(server);
registerPetsTools(server);
async function main(): Promise<void> {
  const transportMode = process.env.MCP_TRANSPORT ?? "stdio";

  if (transportMode === "http") {
    const httpTransport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
    });
    const nodeServer = createServer(async (req: IncomingMessage, res: ServerResponse) => {
      await httpTransport.handleRequest(req, res);
    });
    await server.connect(httpTransport);
    const port = Number(process.env.PORT ?? 3000);
    nodeServer.listen(port);
    return;
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

void main();