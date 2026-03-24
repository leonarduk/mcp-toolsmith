# mcp-toolsmith

[![PyPI](https://img.shields.io/pypi/v/mcp-toolsmith)](https://pypi.org/project/mcp-toolsmith/)
[![CI](https://github.com/leonarduk/mcp-toolsmith/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/leonarduk/mcp-toolsmith/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/mcp-toolsmith)](https://pypi.org/project/mcp-toolsmith/)

Generate production-ready TypeScript MCP server templates directly from OpenAPI 3.x specs.

## Install

```bash
pip install mcp-toolsmith
```

## Quick usage

```bash
mcp-toolsmith generate https://petstore3.swagger.io/api/v3/openapi.json --out generated-petstore
```

Then run the generated server:

```bash
cd generated-petstore
npm install
npm run build
npm start
```

For a complete walkthrough (including Claude Desktop setup), see [Quickstart](docs/quickstart.md).

## Features

| Capability | Status | Notes |
| --- | --- | --- |
| OpenAPI 3.x ingestion | ✅ | Validates and extracts operations from OpenAPI 3.x documents. |
| TypeScript ESM output | ✅ | Generates a Node 20+ ESM MCP server scaffold. |
| Quality score report | ✅ | Emits scoring dimensions and findings in CLI output/report.json. |
| Agent integration snippets | ✅ | Generates Claude Desktop, VS Code, and LangChain snippets. |

## Documentation

- [Quickstart](docs/quickstart.md)
- [Troubleshooting FAQ](docs/troubleshooting.md)
- [Architecture ADRs](docs/adr/)
- [Petstore golden example output](tests/golden/petstore/default/)
