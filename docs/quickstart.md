# Quickstart

This guide walks from zero to a working tool call in Claude Desktop using a generated MCP server from the public Petstore OpenAPI spec.

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm (bundled with Node)

Install the CLI:

```bash
pip install mcp-toolsmith
```

## Step 1: Generate from the Petstore URL

Use the official public OAS3 endpoint:

```bash
mcp-toolsmith generate https://petstore3.swagger.io/api/v3/openapi.json --out generated-petstore
```

Expected output includes a `Generation Summary` table and file paths under `generated-petstore/`.

## Step 2: Install dependencies and run the generated server

```bash
cd generated-petstore
npm install
npm run build
npm start
```

Note: if you skip `npm run build`, `npm start` fails because `dist/index.js` will not exist yet.

## Step 3: Copy Claude Desktop config snippet

Open and copy the generated snippet:

```bash
cat snippets/claude_desktop_config.json
```

Paste the `mcpServers` entry into your Claude Desktop MCP config, and replace `__OUT_DIR__` with the absolute path to your generated directory.

Example:

```json
{
  "mcpServers": {
    "petstore": {
      "command": "node",
      "args": ["/absolute/path/to/generated-petstore/dist/index.js"]
    }
  }
}
```

## Step 4: Verify a tool call in Claude Desktop

1. Restart Claude Desktop after updating config.
2. In a Claude conversation, ask for a Petstore operation such as “list available pets”.
3. Confirm Claude can discover and call the generated Petstore MCP tools.

## Troubleshooting

### Spec validation errors

If generation fails with `Error extracting operations: Invalid OpenAPI specification.`, verify your document is OpenAPI 3.x and includes top-level `openapi`, `info`, and `paths` fields.

### Unsafe method warning

If the summary shows skipped operations with `unsafe HTTP method requires --unsafe`, regenerate with:

```bash
mcp-toolsmith generate <url> --unsafe
```

Use `--unsafe` only if you intentionally want mutating operations (DELETE/PUT/PATCH).

### SSRF block for remote specs

If loading a remote spec fails with an SSRF block message, the hostname resolved to a non-public IP address and was intentionally blocked. Use a public HTTPS URL or save the spec locally and generate from a file path.
