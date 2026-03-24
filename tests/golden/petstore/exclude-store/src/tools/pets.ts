import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getApiBaseUrl, getApiToken } from "../config.js";

export function registerPetsTools(server: McpServer): void {
  server.tool(
    "create_pet",
    "Create pet",
    {
      body: z.object({name: z.string()}),
    },
    async (args: Record<string, unknown>) => {
      const apiBaseUrl = getApiBaseUrl();
      const apiToken = getApiToken();
      const url = new URL(`${apiBaseUrl}/pets`);
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Accept": "application/json",
          ...(apiToken ? { Authorization: `Bearer ${apiToken}` } : {}),
          "Content-Type": "application/json",
        },
        body: JSON.stringify(args.body ?? {}),
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
  server.tool(
    "get_pet",
    "Get pet",
    {
      petid: z.string(),
    },
    async (args: Record<string, unknown>) => {
      const apiBaseUrl = getApiBaseUrl();
      const apiToken = getApiToken();
      const url = new URL(`${apiBaseUrl}/pets/${encodeURIComponent(String(args.petid))}`);
      const response = await fetch(url, {
        method: "GET",
        headers: {
          "Accept": "application/json",
          ...(apiToken ? { Authorization: `Bearer ${apiToken}` } : {}),
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
  server.tool(
    "list_pets",
    "List pets",
    {
      limit: z.number().int(),
    },
    async (args: Record<string, unknown>) => {
      const apiBaseUrl = getApiBaseUrl();
      const apiToken = getApiToken();
      const url = new URL(`${apiBaseUrl}/pets`);
      if (args.limit !== undefined) {
        url.searchParams.set("limit", String(args.limit));
      }
      const response = await fetch(url, {
        method: "GET",
        headers: {
          "Accept": "application/json",
          ...(apiToken ? { Authorization: `Bearer ${apiToken}` } : {}),
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