import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getApiBaseUrl } from "../config.js";

export function registerAdminTools(server: McpServer): void {
  server.tool(
    "delete_pet",
    "Delete pet",
    {
      petid: z.string(),
    },
    async (args: Record<string, unknown>) => {
      const apiBaseUrl = getApiBaseUrl();
      const url = new URL(`${apiBaseUrl}/pets/${encodeURIComponent(String(args.petid))}`);
      const response = await fetch(url, {
        method: "DELETE",
        headers: {
          "Accept": "application/json",
        },
      });
      const text = await response.text();
      return {
        content: [
          {
            type: "text" as const,
            text,
          },
        ],
      };
    },
  );
}