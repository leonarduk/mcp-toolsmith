# Troubleshooting

## `Error loading spec: Remote specs must use an https:// URL`

`mcp-toolsmith` only fetches remote specs over HTTPS. Use an `https://` URL, or download the file and pass a local path.

## `Error loading spec` with SSRF block details

Remote hosts resolving to non-public IP ranges are blocked to prevent SSRF. Use a publicly reachable host, or run against a local file instead.

## `Error extracting operations: Invalid OpenAPI specification.`

Your spec is missing required OpenAPI 3.x structure. Ensure these top-level fields exist and are valid:

- `openapi` (must start with `3.`)
- `info` (object)
- `paths` (object)

## `unsafe HTTP method requires --unsafe`

By default, mutating operations (DELETE/PUT/PATCH) are excluded. If you need them:

```bash
mcp-toolsmith generate <url-or-path> --unsafe
```

## `npm start` fails with missing `dist/index.js`

Run build once before starting:

```bash
npm run build
npm start
```

## Claude Desktop does not see generated server

- Confirm the snippet was copied from `snippets/claude_desktop_config.json`.
- Replace `__OUT_DIR__` with an absolute path.
- Restart Claude Desktop after saving the config.
