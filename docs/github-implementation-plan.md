# MCP Toolsmith GitHub Implementation Plan

## Goal
Ship **MCP Toolsmith** as a Python CLI that converts an OpenAPI 3.x spec from a URL or local file into a production-ready TypeScript MCP server template in under five minutes, with a quality report and agent integration snippets.

## Planning assumptions
- **v1 scope:** OpenAPI 3.x input only, TypeScript ESM output only, Linux/macOS only.
- **Primary user outcome:** `pip install mcp-toolsmith` followed by one `generate` command produces a runnable MCP server plus a quality report.
- **Delivery principle:** land thin vertical slices early so the repo is always demoable.
- **Tracking model:** one milestone per delivery phase, with placeholder issue IDs showing cross-issue dependencies.

---

## Milestone 0 — Project foundation and delivery guardrails
**Objective:** establish the repository, packaging, contribution workflow, and implementation contract so feature work can land safely.

### Suggested GitHub issues
- [ ] **#100** Create Python package scaffold, CLI entrypoint, and `pyproject.toml`
- [ ] **#101** Add baseline test harness with pytest and placeholder golden tests
- [ ] **#102** Add CI workflow for lint, unit tests, and generated-output checks
- [ ] **#103** Draft architecture decision record for OpenAPI → MCP pipeline
- [ ] **#104** Add docs skeleton (`README`, quickstart, design notes, roadmap)

### Deliverables
- Installable package with `mcp-toolsmith` console script
- Basic Typer CLI stub with `generate` command placeholder
- Initial CI and contribution standards
- Docs skeleton for architecture, quickstart, and roadmap

### Dependencies
- No upstream dependencies; this milestone unblocks all others.

### Exit criteria
- New contributors can clone the repo, install dependencies, run tests, and understand the roadmap from GitHub alone.

---

## Milestone 1 — OpenAPI ingestion and normalization
**Objective:** reliably load, validate, and normalize OpenAPI 3.x specs from local files or HTTPS URLs.

### Suggested GitHub issues
- [ ] **#110** Implement spec loader for local path and HTTPS URL input
- [ ] **#111** Validate and normalize OpenAPI 3.x documents with Pydantic models
- [ ] **#112** Dereference `$ref` objects safely without unintended network side effects
- [ ] **#113** Extract normalized `OperationModel` records from paths, methods, params, and schemas
- [ ] **#114** Add fixture-driven unit tests for valid, invalid, and edge-case specs
- [ ] **#115** Add SSRF protections for remote spec loading (HTTPS-only, block RFC-1918 targets)

### Deliverables
- `loader.py`, `deref.py`, `models.py`, and `extractor.py`
- Safe remote-fetch path with explicit validation and friendly errors
- Stable internal operation model for downstream linting and code generation

### Dependencies
- Depends on **#100**, **#101**, and **#103**.
- Blocks **#120**, **#130**, and **#150**.

### Exit criteria
- The CLI can ingest representative OpenAPI specs and emit normalized operation data without crashing.

---

## Milestone 2 — Linting, scoring, and generation planning
**Objective:** score generated-tool quality before code generation so output quality is measurable and explainable.

### Suggested GitHub issues
- [ ] **#120** Implement naming rules (`snake_case`, action-object patterns, length limits)
- [ ] **#121** Implement safety rules for unsafe method detection and redaction coverage checks
- [ ] **#122** Implement validation/usability scoring for schema coverage, parameter complexity, and descriptions
- [ ] **#123** Build composite 0-100 quality scorer with weighted dimensions
- [ ] **#124** Expose lint findings in structured models consumable by reports and CLI output

### Deliverables
- Reusable lint/scoring engine covering Naming, Safety, Validation, and Usability
- Structured finding format for console and JSON report output
- Clear thresholds for warning vs failure behavior

### Dependencies
- Depends on **#113** and **#114**.
- Blocks **#140** and informs **#130** template decisions.

### Exit criteria
- A normalized spec can be scored consistently with deterministic results and actionable findings.

---

## Milestone 3 — TypeScript MCP server generation
**Objective:** generate a runnable Node 20+ TypeScript ESM MCP server template from normalized operations.

### Suggested GitHub issues
- [ ] **#130** Create Jinja2 template set for `index.ts`, tool modules, and shared config
- [ ] **#131** Implement tool grouping by tag with fallback grouping strategy
- [ ] **#132** Generate agent-friendly input schemas and descriptions for each tool
- [ ] **#133** Implement CLI writing pipeline for `--out`, `--dry-run`, and overwrite behavior
- [ ] **#134** Add generated-project smoke test to verify `npm install && npm start`

### Deliverables
- Production-oriented TypeScript ESM server scaffold
- One tool file per tag group, plus server init and registration
- Dry-run preview mode and filesystem-safe generation flow

### Dependencies
- Depends on **#113**, **#123**, and **#124**.
- Blocks **#135**, **#136**, **#140**, and **#141**.

### Exit criteria
- A supported spec produces a runnable server template with valid project structure and startup path.

---

## Milestone 4 — Runtime safety and reliability middleware
**Objective:** make generated servers safe enough to demo publicly and robust enough for portfolio-grade usage.

### Suggested GitHub issues
- [ ] **#135** Generate auth middleware for env-based API key and bearer token support
- [ ] **#136** Generate safety guards for HTTP method allow-list and `--unsafe` override
- [ ] **#137** Implement timeout middleware with `AbortController`
- [ ] **#138** Implement retry middleware with exponential backoff and jitter
- [ ] **#139** Implement token-bucket rate limiter with sensible defaults
- [ ] **#140** Implement Ajv validation, structured logging, metrics, and PII redaction hook

### Deliverables
- Middleware modules for auth, timeout, retry, rate limiting, validation, logging, redaction, and metrics
- Safe default behavior for GET/POST-only generation unless `--unsafe` is explicitly enabled
- Generated transport support for HTTP and stdio modes

### Dependencies
- Depends on **#130** through **#133**.
- **#136** depends on **#121**.
- **#140** depends on **#122** and **#124**.
- Blocks **#141**, **#150**, and **#160**.

### Exit criteria
- Generated servers enforce the advertised safety/reliability guarantees and have test coverage for their defaults.

---

## Milestone 5 — Reporting, filtering, and CLI UX
**Objective:** make the generator understandable and controllable from the CLI for real user workflows.

### Suggested GitHub issues
- [ ] **#141** Emit `report.json` with score, findings, and generation summary
- [ ] **#142** Render Rich console summary table for score and warnings
- [ ] **#143** Implement `--include`, `--exclude`, and `--max-tools` selection logic
- [ ] **#144** Improve CLI progress feedback, friendly errors, and command help text
- [ ] **#145** Add dry-run preview output summarizing planned files and skipped operations

### Deliverables
- Machine-readable quality report plus concise console rendering
- Filtering controls by tag and operation ID
- UX improvements that reduce confusion during first run

### Dependencies
- Depends on **#123**, **#124**, **#133**, and **#140**.
- Blocks **#150**, **#160**, and release readiness in **#190**.

### Exit criteria
- Users can understand why a server was generated the way it was, what was skipped, and how to refine the result.

---

## Milestone 6 — Agent integration outputs and demos
**Objective:** make generated projects immediately demonstrable with mainstream agent tooling.

### Suggested GitHub issues
- [ ] **#150** Generate Claude Desktop configuration snippet
- [ ] **#151** Generate GitHub Copilot / VS Code MCP configuration snippet
- [ ] **#152** Generate LangChain integration snippet and sample wiring
- [ ] **#153** Add end-to-end example using GitHub or Petstore spec with bearer auth
- [ ] **#154** Add runnable LangChain demo script that performs a real tool call

### Deliverables
- Copy-paste-ready configuration snippets for target agent ecosystems
- At least one polished end-to-end example repo output under version control
- Demo script proving the generator can support an actual agent workflow

### Dependencies
- Depends on **#130**, **#140**, **#141**, and **#143**.
- **#154** depends on **#152** and **#153**.
- Blocks final marketing/demo work in **#180** and release in **#190**.

### Exit criteria
- A reviewer can generate a server and connect it to Claude, Copilot, or LangChain with minimal manual editing.

---

## Milestone 7 — Hardening, golden tests, and docs
**Objective:** ensure the generator is stable, explainable, and easy for hiring managers or OSS users to evaluate.

### Suggested GitHub issues
- [ ] **#160** Build golden test suite for generated TypeScript output
- [ ] **#161** Add regression fixtures for auth variants, tags, enums, and schema edge cases
- [ ] **#162** Write `design.md` covering pipeline, threat model, and scoring rationale
- [ ] **#163** Write and validate `quickstart.md` with a clean-room install path
- [ ] **#164** Add FAQ/troubleshooting for spec validation, auth setup, and unsafe methods

### Deliverables
- Golden snapshot coverage for generated project structure and key files
- Durable docs for architecture, quickstart, and troubleshooting
- Stronger signal that the project is maintained and trustworthy

### Dependencies
- Depends on **#140**, **#141**, **#143**, and **#153**.
- **#163** should be validated against outputs from **#153**.
- Blocks **#180** and **#190**.

### Exit criteria
- The project has reproducible output verification and documentation that supports both demos and outside contributors.

---

## Milestone 8 — Portfolio assets, launch prep, and release
**Objective:** package the work as an open-source launch and job-search portfolio asset.

### Suggested GitHub issues
- [ ] **#180** Record 60-second terminal demo using the polished example flow
- [ ] **#181** Draft blog post: *Building MCP Servers from OpenAPI Specs*
- [ ] **#182** Final README pass with GIF, feature matrix, and comparison framing
- [ ] **#190** Publish v0.1.0 to PyPI and create GitHub Release notes
- [ ] **#191** Announce launch on LinkedIn / portfolio channels with links to demo and docs

### Deliverables
- Release-ready README and release notes
- Demo video or terminal capture for GitHub and blog embedding
- Blog/article draft tied to the repo narrative and technical decisions
- PyPI package and GitHub Release for `v0.1.0`

### Dependencies
- Depends on **#154**, **#160**, **#162**, **#163**, and **#164**.
- **#190** depends on all milestones being complete.

### Exit criteria
- External users can install the package, follow docs, run the demo, and evaluate the project as production-minded OSS work.

---

## Dependency map (placeholder issue IDs)
Use this section in GitHub issues or a project board to show sequencing explicitly.

```text
#100 -> #110 -> #120 -> #130 -> #135 -> #141 -> #150 -> #160 -> #180 -> #190
#101 -> #114 -> #123 -> #141
#103 -> #113 -> #130
#121 -> #136
#122 -> #140
#153 -> #163, #180
#154 -> #180, #190
```

---

## Recommended GitHub milestone setup
| Milestone | Target outcome | Suggested linked issues |
| --- | --- | --- |
| M0 Foundation | Repo is buildable and contributor-ready | #100-#104 |
| M1 Ingestion | OpenAPI specs load and normalize safely | #110-#115 |
| M2 Scoring | Quality model is implemented and testable | #120-#124 |
| M3 Generation | Runnable TS MCP server is generated | #130-#134 |
| M4 Runtime Safety | Middleware and safe defaults are in place | #135-#140 |
| M5 CLI UX | Reports, filters, and polished CLI flow ship | #141-#145 |
| M6 Integrations | Agent config snippets and demos work | #150-#154 |
| M7 Hardening | Golden tests and docs are complete | #160-#164 |
| M8 Launch | Demo, blog, PyPI, and release are published | #180-#191 |

---

## GitHub-friendly issue template examples

### Epic issue template
```md
## Summary
Implement Milestone M3: TypeScript MCP server generation.

## Scope
- [ ] #130 Create Jinja2 templates for server scaffold
- [ ] #131 Group tools by tag
- [ ] #132 Generate input schemas and descriptions
- [ ] #133 Support --out and --dry-run behavior
- [ ] #134 Add generated-project smoke test

## Dependencies
- Depends on #113, #123, #124
- Blocks #135, #136, #140, #141

## Definition of done
- A supported OpenAPI 3.x spec generates a runnable Node 20+ TypeScript MCP server.
- Generated output passes smoke tests and matches expected project structure.
```

### Feature issue template
```md
## Summary
Add report.json output for generated server quality and findings.

## Why
Users need a machine-readable artifact that explains generation quality, skipped operations, and safety warnings.

## Tasks
- [ ] Define report schema
- [ ] Serialize score and lint findings
- [ ] Include generation metadata and skipped operations
- [ ] Add fixture-based tests
- [ ] Document the report in README/quickstart

## Dependencies
- Depends on #123, #124, #133, #140
- Related to #142 and #145

## Definition of done
- `mcp-toolsmith generate ...` writes `report.json` by default.
- Report contents are covered by tests and documented for users.
```

---

## Success metrics to track in GitHub
- **Time to first tool call:** under 5 minutes from install to successful generated-server call
- **Generated tool error rate on demo tasks:** under 5%
- **Schema reduction vs raw OpenAPI input:** 30-50% reduction where simplification is applied
- **Adoption signal:** 50+ GitHub stars within 60 days of release
- **Content reach:** 500+ reads on the launch article

## Suggested labels
- `milestone:m0-foundation`
- `milestone:m1-ingestion`
- `milestone:m2-scoring`
- `milestone:m3-generation`
- `milestone:m4-runtime-safety`
- `milestone:m5-cli-ux`
- `milestone:m6-integrations`
- `milestone:m7-hardening`
- `milestone:m8-launch`
- `type:epic`
- `type:feature`
- `type:docs`
- `type:test`
- `risk:security`
- `risk:reliability`

## Suggested project board columns
- Backlog
- Ready
- In Progress
- In Review
- Blocked
- Done

## Notes for execution
- Prefer shipping **one thin end-to-end path early** (Petstore or GitHub spec) so the project is demoable before every middleware feature is complete.
- Treat **safe defaults** as a release blocker: no unsafe mutation methods unless `--unsafe` is explicit.
- Keep **generated output deterministic** so golden tests remain stable and reviewable.
- Optimize for **portfolio clarity** as well as functionality: every milestone should improve the repo’s ability to explain itself on GitHub.
