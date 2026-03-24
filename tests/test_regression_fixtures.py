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
    assert "BEARER_TOKEN" in config_text


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
