"""Regression tests for fixture edge cases in extraction and generation."""

from __future__ import annotations

from pathlib import Path

import yaml

from mcp_toolsmith.extractor import extract_operations
from mcp_toolsmith.generator import generate
from mcp_toolsmith.scorer import score_operations


FIXTURE_NAMES = [
    "bearer_auth.yaml",
    "api_key_auth.yaml",
    "enum_params.yaml",
    "allof_schema.yaml",
    "nested_params.yaml",
    "no_tags.yaml",
]


def _load_fixture(name: str) -> dict[str, object]:
    path = Path(__file__).parent / "fixtures" / name
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_regression_fixtures_generate_expected_files(tmp_path: Path) -> None:
    for fixture_name in FIXTURE_NAMES:
        spec = _load_fixture(fixture_name)
        operations = extract_operations(spec)
        scoring = score_operations(operations)

        out_dir = tmp_path / fixture_name.replace(".yaml", "")
        result = generate(operations, scoring, out_dir, spec_title=spec["info"]["title"])

        assert result.skipped_operations == []
        assert (out_dir / "package.json").exists()
        assert (out_dir / "src" / "index.ts").exists()
        assert (out_dir / "src" / "config.ts").exists()


def test_bearer_auth_fixture_generates_bearer_token_config(tmp_path: Path) -> None:
    spec = _load_fixture("bearer_auth.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)

    out_dir = tmp_path / "bearer"
    generate(operations, scoring, out_dir, spec_title=spec["info"]["title"])

    config_text = (out_dir / "src" / "config.ts").read_text(encoding="utf-8")
    tools_text = (out_dir / "src" / "tools" / "account.ts").read_text(encoding="utf-8")
    assert "BEARER_TOKEN" in config_text
    assert "getBearerToken" in tools_text
    assert "Authorization: `Bearer ${apiToken}`" in tools_text


def test_api_key_auth_fixture_uses_api_key_header_and_not_bearer(tmp_path: Path) -> None:
    spec = _load_fixture("api_key_auth.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)

    out_dir = tmp_path / "api_key"
    generate(operations, scoring, out_dir, spec_title=spec["info"]["title"])

    tools_text = (out_dir / "src" / "tools" / "widgets.ts").read_text(encoding="utf-8")
    assert '"X-API-Key": process.env.API_KEY' in tools_text
    assert "Authorization: `Bearer ${apiToken}`" not in tools_text
    assert "getBearerToken" not in tools_text


def test_enum_params_fixture_generates_union_schema_for_enum_parameter(tmp_path: Path) -> None:
    spec = _load_fixture("enum_params.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)

    out_dir = tmp_path / "enum"
    generate(operations, scoring, out_dir, spec_title=spec["info"]["title"])

    tools_text = (out_dir / "src" / "tools" / "items.ts").read_text(encoding="utf-8")
    assert "status: z.enum(['draft', 'published', 'archived'])" in tools_text


def test_no_tags_fixture_falls_back_to_default_module_name(tmp_path: Path) -> None:
    spec = _load_fixture("no_tags.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)

    out_dir = tmp_path / "no_tags"
    generate(operations, scoring, out_dir, spec_title=spec["info"]["title"])

    assert (out_dir / "src" / "tools" / "default.ts").exists()


def test_no_auth_fixture_does_not_inject_authorization_header(tmp_path: Path) -> None:
    spec = _load_fixture("no_tags.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)

    out_dir = tmp_path / "no_auth"
    generate(operations, scoring, out_dir, spec_title=spec["info"]["title"])

    tools_text = (out_dir / "src" / "tools" / "default.ts").read_text(encoding="utf-8")
    assert "Authorization" not in tools_text
    assert "getBearerToken" not in tools_text


def test_simple_no_auth_spec_has_no_bearer_helpers_or_auth_headers(tmp_path: Path) -> None:
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "Simple API", "version": "1.0.0"},
        "paths": {
            "/ping": {
                "get": {
                    "operationId": "ping",
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    operations = extract_operations(spec)
    scoring = score_operations(operations)

    out_dir = tmp_path / "simple_no_auth"
    generate(operations, scoring, out_dir, spec_title=spec["info"]["title"])

    tools_text = (out_dir / "src" / "tools" / "default.ts").read_text(encoding="utf-8")
    assert "Authorization" not in tools_text
    assert "getBearerToken" not in tools_text


def test_allof_fixture_merges_request_body_fields_into_generated_schema(tmp_path: Path) -> None:
    spec = _load_fixture("allof_schema.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)

    out_dir = tmp_path / "allof"
    generate(operations, scoring, out_dir, spec_title=spec["info"]["title"])

    tools_text = (out_dir / "src" / "tools" / "users.ts").read_text(encoding="utf-8")
    assert "body: z.object({name: z.string(), role: z.string().optional()})" in tools_text
