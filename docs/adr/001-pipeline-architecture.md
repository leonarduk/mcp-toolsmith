# ADR 001: OpenAPI → OperationModel → Jinja2 → TypeScript pipeline

- Status: Accepted
- Date: 2026-03-21
- Deciders: mcp-toolsmith maintainers
- Related issues: #7, #8

## Context

`mcp-toolsmith` turns an OpenAPI document into a runnable Model Context Protocol (MCP) server template. The project needs a documented architecture contract before the loader, normalizer, scorer, and generator are implemented so downstream work can share a stable vocabulary.

This ADR defines the first-version generation pipeline:

1. Load an OpenAPI document from a local file or HTTPS URL.
2. Normalize supported operations into an internal `OperationModel` contract.
3. Score and annotate operations using deterministic linting dimensions.
4. Render a TypeScript MCP server with Jinja2 templates.

The design should optimize for:

- predictable generation behavior;
- a stable internal interface between Milestone 1 and Milestone 3;
- output that is easy to review, test, and run on current MCP/Node tooling; and
- explicit handling of security risks introduced by untrusted API descriptions.

## Decision

We will implement the pipeline as:

```text
OpenAPI 3.x document
  -> validated loader
  -> normalized OperationModel records
  -> scoring + findings
  -> Jinja2 template context
  -> TypeScript ESM MCP server project
```

### Decision 1: support OpenAPI 3.x only in v1

Version 1 accepts OpenAPI 3.x documents only.

#### Why

- OpenAPI 3.x is the target format in the project plan and covers the majority of modern machine-readable REST API descriptions.
- Restricting the input surface area keeps validation, dereferencing, schema handling, and fixture coverage manageable for the first release.
- Swagger 2.0 and AsyncAPI introduce materially different semantics, especially around request bodies, content negotiation, and component modeling, which would slow delivery of the first usable vertical slice.

#### Consequences

- The loader must reject unsupported formats early with a clear error.
- Internal models can assume OpenAPI 3.x concepts such as `requestBody`, `components`, and media types.
- Future support for Swagger 2.0 or AsyncAPI should land as a new ADR or an explicit compatibility layer rather than as implicit parser creep.

### Decision 2: generate TypeScript ESM output

Version 1 emits Node 20+ TypeScript using ECMAScript modules.

#### Why

- TypeScript improves generated code readability and maintenance by giving explicit structure to request/response helpers, generated schemas, and middleware.
- Node's current MCP ecosystem and common SDKs are well aligned with ESM-first packaging.
- ESM reduces ambiguity for imports/exports in modern Node environments and matches the direction of most new template ecosystems.
- A single output target avoids spending early effort on parallel generators for CommonJS, Python, or other runtimes.

#### Consequences

- Templates should emit `package.json`, `tsconfig.json`, and source files that assume an ESM project layout.
- Generated output should avoid CommonJS-only patterns such as `require` and `module.exports`.
- Future alternate backends can reuse `OperationModel`, but they should be separate generator implementations.

### Decision 3: use Jinja2 for code generation templates

Version 1 uses Jinja2 as the rendering layer between normalized models and TypeScript output.

#### Why

- Jinja2 is mature, well understood, and expressive enough for file templating, loops, conditionals, and small formatting helpers.
- It lets the generator keep code layout in template files instead of deeply nested Python string builders.
- Template-based generation makes golden testing practical because output structure stays stable and reviewable.
- Jinja2 is sufficient for deterministic rendering without introducing a custom DSL.

#### Consequences

- Rendering logic should stay thin; business rules belong in normalization/scoring, not in templates.
- Template context objects must be explicit and documented to avoid hidden coupling.
- Formatting-sensitive output should be kept simple enough that generated projects can be normalized by standard TypeScript tooling.

## Pipeline stages

### 1. Load and validate spec

Input sources:

- local filesystem path; or
- HTTPS URL.

Responsibilities:

- parse JSON or YAML;
- verify the document is OpenAPI 3.x;
- reject unsupported transport schemes;
- apply SSRF protections before any remote fetch; and
- produce a validated in-memory representation for extraction.

Out of scope for v1:

- arbitrary HTTP schemes;
- authenticated spec fetch flows beyond basic user-provided URL access; and
- background crawling of linked remote references.

### 2. Normalize into `OperationModel`

Each supported operation becomes one `OperationModel` record. This is the contract between ingestion, scoring, and generation.

### 3. Score and annotate

Each `OperationModel` is evaluated for generation quality and safety. The scorer produces weighted dimension scores and structured findings used by CLI reporting and generation decisions.

### 4. Render project with Jinja2

Templates receive a precomputed context built from accepted operations, project metadata, and scoring results. Templates should not interpret raw OpenAPI documents directly.

## `OperationModel` contract

`OperationModel` is the canonical normalized representation for a single OpenAPI operation that can become one MCP tool.

### Schema

| Field | Type | Required | Constraints / meaning |
| --- | --- | --- | --- |
| `source_path` | `str` | Yes | Original OpenAPI path template, must begin with `/`. |
| `http_method` | `Literal["get", "post", "put", "patch", "delete", "options", "head"]` | Yes | Lowercase HTTP method from the spec. |
| `operation_id` | `str` | Yes | Stable unique identifier after normalization; unique across the whole spec. |
| `tool_name` | `str` | Yes | Generated MCP tool identifier, `snake_case`, ASCII letters/numbers/underscores only, max 64 chars. |
| `summary` | `str | None` | No | Short human-readable summary, trimmed if present. |
| `description` | `str | None` | No | Longer description in plain text or Markdown; may be collapsed for generation. |
| `tags` | `list[str]` | Yes | Ordered tag list from the spec; empty list allowed. |
| `primary_tag` | `str | None` | No | First tag or chosen fallback grouping key. |
| `deprecated` | `bool` | Yes | Mirrors OpenAPI `deprecated`. |
| `unsafe` | `bool` | Yes | True when the HTTP method is considered state changing or otherwise non-safe for default generation. |
| `servers` | `list[str]` | Yes | Resolved absolute server base URLs applicable to the operation. |
| `path_params` | `list[ParameterModel]` | Yes | Parameters declared in path scope or operation scope with location `path`. |
| `query_params` | `list[ParameterModel]` | Yes | Parameters with location `query`. |
| `header_params` | `list[ParameterModel]` | Yes | Parameters with location `header`, excluding auth headers handled separately when possible. |
| `cookie_params` | `list[ParameterModel]` | Yes | Parameters with location `cookie`. |
| `request_body` | `RequestBodyModel | None` | No | Normalized body payload contract if the operation accepts a request body. |
| `responses` | `list[ResponseModel]` | Yes | At least one normalized response entry if the spec defines any responses; may be empty only when the source operation is malformed and a finding is emitted. |
| `security_requirements` | `list[SecurityRequirementModel]` | Yes | Ordered list of OpenAPI security requirement alternatives. |
| `auth_schemes` | `list[str]` | Yes | Distinct referenced security scheme names after normalization. |
| `quality` | `QualityScoreModel` | Yes | Weighted scoring breakdown attached after lint/scoring. |
| `findings` | `list[FindingModel]` | Yes | Structured warnings/errors relevant to this operation. |
| `extensions` | `dict[str, Any]` | Yes | Supported vendor extensions preserved for future generator features; keys must begin with `x-`. |
|

### `ParameterModel`

| Field | Type | Required | Constraints / meaning |
| --- | --- | --- | --- |
| `name` | `str` | Yes | Original parameter name. |
| `location` | `Literal["path", "query", "header", "cookie"]` | Yes | OpenAPI parameter location. |
| `required` | `bool` | Yes | Path parameters must always normalize to `true`. |
| `description` | `str | None` | No | Human-facing explanation. |
| `schema_type` | `str | None` | No | Top-level normalized schema type, such as `string`, `integer`, `object`, or `array`. |
| `format` | `str | None` | No | OpenAPI schema format if present. |
| `style` | `str | None` | No | Serialization style. |
| `explode` | `bool | None` | No | OpenAPI explode flag if specified. |
| `default` | `Any | None` | No | Default value if declared. |
| `enum_values` | `list[Any]` | Yes | Enumerated allowed values, if any. |
| `json_schema` | `dict[str, Any] | None` | No | JSON-Schema-like shape used for validation/generation after dereferencing and normalization. |

### `RequestBodyModel`

| Field | Type | Required | Constraints / meaning |
| --- | --- | --- | --- |
| `required` | `bool` | Yes | Whether the body is required. |
| `content_type` | `str` | Yes | Selected primary media type for generation. |
| `alternate_content_types` | `list[str]` | Yes | Additional supported media types retained for reporting. |
| `description` | `str | None` | No | Request body description. |
| `json_schema` | `dict[str, Any] | None` | No | Normalized schema for the chosen media type. |

### `ResponseModel`

| Field | Type | Required | Constraints / meaning |
| --- | --- | --- | --- |
| `status_code` | `str` | Yes | Literal response key such as `200`, `201`, or `default`. |
| `description` | `str` | Yes | Response description; fallback text allowed only when the source omits it. |
| `content_types` | `list[str]` | Yes | Sorted list of available media types. |
| `json_schema` | `dict[str, Any] | None` | No | Preferred schema used for documentation/reporting. |

### `SecurityRequirementModel`

| Field | Type | Required | Constraints / meaning |
| --- | --- | --- | --- |
| `scheme_name` | `str` | Yes | Referenced security scheme key. |
| `scopes` | `list[str]` | Yes | OAuth scopes required for that scheme entry. |

### `QualityScoreModel`

| Field | Type | Required | Constraints / meaning |
| --- | --- | --- | --- |
| `total` | `int` | Yes | Composite score from 0 to 100. |
| `dimension_scores` | `dict[str, int]` | Yes | Per-dimension integer scores from 0 to 100. |
| `weighted_contributions` | `dict[str, float]` | Yes | Contribution of each dimension to the composite score. |
| `eligible` | `bool` | Yes | Whether the operation should be generated by default. |

### `FindingModel`

| Field | Type | Required | Constraints / meaning |
| --- | --- | --- | --- |
| `code` | `str` | Yes | Stable machine-readable rule identifier. |
| `severity` | `Literal["info", "warning", "error"]` | Yes | Finding severity. |
| `message` | `str` | Yes | Human-readable explanation. |
| `field` | `str | None` | No | Optional dotted path into the normalized model. |

### Normalization rules

- `operation_id` must be deterministic. If the source omits it, generate one from method + path using a documented normalization rule.
- `tool_name` must be unique after applying naming rules; collisions require deterministic suffixing and a finding.
- Parameters from path-item scope and operation scope must merge according to OpenAPI override rules.
- `$ref` values must be resolved before `OperationModel` emission where possible; unresolved references must produce findings instead of silent omission.
- Unknown vendor extensions may be preserved in `extensions`, but unknown core fields must not expand the contract implicitly.
- `unsafe` defaults to `true` for `post`, `put`, `patch`, and `delete`; `get`, `head`, and `options` default to `false`. Any future overrides should be explicitly documented.

## Threat model

The generator handles untrusted input. The primary risks for this milestone are remote spec loading and generation of tools that can trigger unsafe side effects.

### SSRF and remote loading risks

Threats:

- remote URLs could target loopback, link-local, RFC1918, or metadata service addresses;
- redirects could bounce an apparently safe URL to a prohibited destination;
- `$ref` resolution could create hidden network fetches; and
- very large or malicious documents could cause resource exhaustion.

Mitigations:

- allow only HTTPS URLs for remote root documents in v1;
- resolve DNS and reject private, local, multicast, and reserved IP ranges before connecting;
- re-check each redirect target with the same policy;
- disable implicit remote `$ref` fetching unless explicitly designed and reviewed later;
- apply request timeout and response size limits; and
- surface a clear error when remote loading is blocked.

### Unsafe HTTP methods and side-effecting tools

Threats:

- generated tools for `post`, `put`, `patch`, or `delete` may mutate external systems;
- poorly described operations can hide destructive behavior behind generic summaries; and
- agents may invoke dangerous tools more readily if names and descriptions understate risk.

Mitigations:

- mark non-safe methods as `unsafe=true` during normalization;
- include safety scoring and findings that can block default generation or require explicit opt-in;
- preserve method and path context in descriptions available to templates and reports; and
- design later CLI behavior around safe defaults, such as generating only safe methods unless the user passes an explicit override.

## Scoring dimensions and weighting rationale

The composite quality score is a 0-100 weighted score across four dimensions.

| Dimension | Weight | Why it matters |
| --- | --- | --- |
| Naming | 20% | Good tool names and operation IDs improve discoverability and reduce ambiguity for agents. |
| Safety | 35% | Unsafe methods, missing auth context, or redaction gaps can create outsized real-world risk, so safety carries the heaviest weight. |
| Validation | 25% | Strong parameter/body schemas improve reliability of generated tool calls and future runtime validation. |
| Usability | 20% | Helpful summaries, descriptions, and manageable input complexity improve agent success rates. |

### Rationale

- **Safety (35%)** is highest because an incorrect but harmless tool is usually easier to recover from than a destructive tool exposed without guardrails.
- **Validation (25%)** is next because schema quality directly affects runtime correctness, generated input schemas, and user trust.
- **Naming (20%)** and **Usability (20%)** remain important but should not outweigh fundamental safety and correctness concerns.

### Scoring guidance

- Each dimension produces a 0-100 score plus supporting findings.
- The weighted total is rounded to an integer from 0 to 100.
- `eligible=true` means the operation meets the minimum bar for default generation; this should depend on both total score and presence of blocking safety/error findings.
- Dimension formulas should remain deterministic and explainable in reports.

## Alternatives considered

### Support Swagger 2.0 immediately

Rejected for v1 because it would broaden the parser and normalization surface before the core pipeline is proven.

### Generate code with Python string builders

Rejected because it obscures template intent, complicates golden tests, and tends to mix formatting with business logic.

### Generate JavaScript CommonJS

Rejected because it is less aligned with current Node-first MCP tooling and would add compatibility complexity without a clear v1 benefit.

## Implementation notes

- Milestone 1 should treat this ADR as the contract for extraction and scoring inputs.
- Milestone 3 templates should consume pre-normalized structures only.
- If any required `OperationModel` field proves insufficient during implementation, update this ADR before changing the contract silently.

## README linkage

The repository README should link to this ADR so reviewers can find the architecture contract quickly.
