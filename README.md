# mcp-toolsmith
[![CI](https://github.com/leonarduk/mcp-toolsmith/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/leonarduk/mcp-toolsmith/actions/workflows/ci.yml)

Python CLI that converts OpenAPI/Swagger specifications into production-ready MCP server templates in TypeScript.

## Quick install

```bash
pip install mcp-toolsmith
```

![Terminal demo showing `mcp-toolsmith generate` against the Petstore API and resulting snippet output.](docs/demo.svg)

## Documentation

- [Architecture ADR: OpenAPI → OperationModel → Jinja2 → TypeScript pipeline](docs/adr/001-pipeline-architecture.md)
