"""Tests for TypeScript project generation."""

from __future__ import annotations

import subprocess
from pathlib import Path
import shutil

import yaml

from mcp_toolsmith.extractor import extract_operations
from mcp_toolsmith.models import SchemaModel
from mcp_toolsmith.generator import _typescript_schema_expression, generate, group_by_tag
from mcp_toolsmith.report import build_report
from mcp_toolsmith.scorer import score_operations


def _load_fixture(name: str) -> dict[str, object]:
    path = Path(__file__).parent / "fixtures" / name
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _golden_text(name: str) -> str:
    return (Path(__file__).parent / "golden" / "petstore" / "snippets" / name).read_text(encoding="utf-8")


def test_group_by_tag_uses_first_tag_and_default_fallback() -> None:
    operations = extract_operations(
        {
            "openapi": "3.0.3",
            "info": {"title": "Spec", "version": "1.0.0"},
            "paths": {
                "/ping": {"get": {"operationId": "ping_default", "responses": {"200": {"description": "ok"}}}},
                "/pets": {"get": {"operationId": "list_pets", "tags": ["pets", "animals"], "responses": {"200": {"description": "ok"}}}},
            },
        }
    )

    grouped = group_by_tag(operations)

    assert sorted(grouped) == ["default", "pets"]
    assert [op.operation_id for op in grouped["default"]] == ["ping_default"]
    assert [op.operation_id for op in grouped["pets"]] == ["list_pets"]


def test_typescript_schema_expression_handles_primitive_and_fallback_types() -> None:
    assert _typescript_schema_expression(None) == "z.string()"
    assert _typescript_schema_expression(SchemaModel(type="string")) == "z.string()"
    assert _typescript_schema_expression(SchemaModel(type="integer")) == "z.number().int()"
    assert _typescript_schema_expression(SchemaModel(type="number")) == "z.number()"
    assert _typescript_schema_expression(SchemaModel(type="boolean")) == "z.boolean()"
    assert _typescript_schema_expression(SchemaModel(type="null")) == "z.unknown()"


def test_typescript_schema_expression_handles_arrays_and_nested_arrays() -> None:
    string_array = SchemaModel(type="array", items=SchemaModel(type="string"))
    nested_array = SchemaModel(type="array", items=string_array)

    assert _typescript_schema_expression(string_array) == "z.array(z.string())"
    assert _typescript_schema_expression(nested_array) == "z.array(z.array(z.string()))"


def test_typescript_schema_expression_handles_required_optional_and_quoted_object_keys() -> None:
    schema = SchemaModel(
        type="object",
        required=["name", "x-api-key"],
        properties={
            "name": SchemaModel(type="string"),
            "nickname": SchemaModel(type="string"),
            "my-field": SchemaModel(type="boolean"),
            "x-api-key": SchemaModel(type="string"),
        },
    )

    assert _typescript_schema_expression(schema) == (
        'z.object({"my-field": z.boolean().optional(), "name": z.string(), '
        '"nickname": z.string().optional(), "x-api-key": z.string()})'
    )


def test_typescript_schema_expression_handles_string_and_mixed_type_enums() -> None:
    assert _typescript_schema_expression(SchemaModel(enum=["small", "medium", "large"])) == (
        "z.enum(['small', 'medium', 'large'])"
    )
    assert _typescript_schema_expression(SchemaModel(enum=["small", 2, "large"])) == "z.unknown()"


def test_generate_dry_run_plans_files_without_writing(tmp_path: Path) -> None:
    spec = _load_fixture("petstore_v3.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)

    result = generate(operations, scoring, tmp_path / "out", dry_run=True)

    assert not (tmp_path / "out").exists()
    assert result.skipped_operations == ["delete_pet"]
    assert sorted(path.relative_to(tmp_path / "out").as_posix() for path in result.files) == [
        "package.json",
        "snippets/claude_desktop_config.json",
        "snippets/langchain_snippet.py",
        "snippets/vscode_mcp_config.json",
        "src/config.ts",
        "src/index.ts",
        "src/tools/pets.ts",
        "tsconfig.json",
    ]


def test_generate_petstore_project_and_typescript_compile(tmp_path: Path) -> None:
    if shutil.which("npm") is None:
        raise AssertionError("npm is required for the integration test")

    spec = _load_fixture("petstore_v3.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)
    out_dir = tmp_path / "generated"

    result = generate(operations, scoring, out_dir)

    assert result.skipped_operations == ["delete_pet"]
    assert (out_dir / "package.json").exists()
    assert (out_dir / "snippets" / "claude_desktop_config.json").exists()
    assert (out_dir / "snippets" / "langchain_snippet.py").exists()
    assert (out_dir / "snippets" / "vscode_mcp_config.json").exists()
    assert (out_dir / "src" / "config.ts").exists()
    assert (out_dir / "src" / "index.ts").exists()
    assert (out_dir / "src" / "tools" / "pets.ts").exists()

    install = subprocess.run(["npm", "install"], cwd=out_dir, check=False, capture_output=True, text=True)
    assert install.returncode == 0, install.stderr or install.stdout

    compile_result = subprocess.run(
        ["npx", "tsc", "--noEmit"],
        cwd=out_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    assert compile_result.returncode == 0, compile_result.stderr or compile_result.stdout


def test_report_matches_petstore_generation_result(tmp_path: Path) -> None:
    spec = _load_fixture("petstore_v3.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)
    out_dir = tmp_path / "generated"

    result = generate(operations, scoring, out_dir)
    report = build_report(
        spec_title=spec["info"]["title"],
        spec_version=spec["info"]["version"],
        total_operations=len(operations),
        generated_operations=len(operations) - len(result.skipped_operations),
        skipped_operations=[],
        score=scoring,
        generated_files=[path.relative_to(out_dir) for path in result.files],
        cli_flags={"out": str(out_dir)},
    )

    assert report.spec_title == "Petstore"
    assert report.spec_version == "1.0.0"
    assert report.total_operations == 4
    assert report.generated_operations == 3
    assert report.score.total == scoring.total
    assert report.generated_files == [
        "package.json",
        "snippets/claude_desktop_config.json",
        "snippets/langchain_snippet.py",
        "snippets/vscode_mcp_config.json",
        "src/config.ts",
        "src/index.ts",
        "src/tools/pets.ts",
        "tsconfig.json",
    ]


def test_generate_writes_expected_snippets_with_output_path(tmp_path: Path) -> None:
    spec = _load_fixture("petstore_v3.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)
    out_dir = tmp_path / "generated"

    generate(operations, scoring, out_dir, spec_title=spec["info"]["title"])

    expected_files = {
        "claude_desktop_config.json",
        "langchain_snippet.py",
        "vscode_mcp_config.json",
    }
    assert {path.name for path in (out_dir / "snippets").iterdir()} == expected_files

    replacements = {
        str(out_dir.resolve()): "__OUT_DIR__",
        "petstore": "__SERVER_NAME__",
        "Petstore": "__SERVER_TITLE__",
    }
    for name in sorted(expected_files):
        actual = (out_dir / "snippets" / name).read_text(encoding="utf-8")
        for source, target in replacements.items():
            actual = actual.replace(source, target)
        assert actual.strip() == _golden_text(name).strip()
