"""Tests for TypeScript project generation."""

from __future__ import annotations

import subprocess
from pathlib import Path
import shutil

import yaml

from mcp_toolsmith.extractor import extract_operations
from mcp_toolsmith.generator import generate, group_by_tag
from mcp_toolsmith.scorer import score_operations


def _load_fixture(name: str) -> dict[str, object]:
    path = Path(__file__).parent / "fixtures" / name
    return yaml.safe_load(path.read_text(encoding="utf-8"))


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


def test_generate_dry_run_plans_files_without_writing(tmp_path: Path) -> None:
    spec = _load_fixture("petstore_v3.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)

    result = generate(operations, scoring, tmp_path / "out", dry_run=True, spec_title=str(spec["info"]["title"]))

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

    result = generate(operations, scoring, out_dir, spec_title=str(spec["info"]["title"]))

    assert result.skipped_operations == ["delete_pet"]
    assert (out_dir / "package.json").exists()
    assert (out_dir / "src" / "config.ts").exists()
    assert (out_dir / "src" / "index.ts").exists()
    assert (out_dir / "src" / "tools" / "pets.ts").exists()
    assert (out_dir / "snippets" / "claude_desktop_config.json").exists()
    assert (out_dir / "snippets" / "vscode_mcp_config.json").exists()
    assert (out_dir / "snippets" / "langchain_snippet.py").exists()

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


def test_generate_writes_expected_snippets_and_server_name(tmp_path: Path) -> None:
    spec = _load_fixture("petstore_v3.yaml")
    operations = extract_operations(spec)
    scoring = score_operations(operations)
    out_dir = tmp_path / "petstore"

    generate(operations, scoring, out_dir, spec_title=str(spec["info"]["title"]))

    golden_dir = Path(__file__).parent / "golden" / "petstore" / "snippets"
    generated_dir = out_dir / "snippets"
    expected_files = sorted(path.name for path in golden_dir.iterdir() if path.is_file())

    assert sorted(path.name for path in generated_dir.iterdir() if path.is_file()) == expected_files
    for name in expected_files:
        generated = (generated_dir / name).read_text(encoding="utf-8")
        golden = (golden_dir / name).read_text(encoding="utf-8").replace("__SERVER_PATH__", out_dir.resolve().as_posix())
        assert generated == golden

    index_contents = (out_dir / "src" / "index.ts").read_text(encoding="utf-8")
    package_contents = (out_dir / "package.json").read_text(encoding="utf-8")
    assert 'name: "petstore"' in index_contents
    assert '"name": "petstore"' in package_contents
