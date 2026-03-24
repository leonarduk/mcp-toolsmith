"""Golden snapshot tests for generated Petstore TypeScript output."""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path
import shutil

import yaml

from mcp_toolsmith.cli import _filter_operations
from mcp_toolsmith.extractor import extract_operations
from mcp_toolsmith.generator import generate
from mcp_toolsmith.report import build_report
from mcp_toolsmith.scorer import score_operations


@dataclass(frozen=True)
class GoldenCase:
    name: str
    unsafe: bool = False
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()


CASES = [
    GoldenCase(name="default"),
    GoldenCase(name="unsafe", unsafe=True),
    GoldenCase(name="include-pets", include=("pets",)),
    GoldenCase(name="exclude-store", exclude=("store",)),
]


def _collect_files(base_dir: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(candidate for candidate in base_dir.rglob("*") if candidate.is_file()):
        rel = path.relative_to(base_dir).as_posix()
        files[rel] = path.read_text(encoding="utf-8")
    return files


def _normalized_file_content(relative_path: str, content: str, out_dir: Path) -> str:
    if relative_path.startswith("snippets/"):
        return content.replace(str(out_dir.resolve()), "__OUT_DIR__")

    if relative_path == "report.json":
        payload = json.loads(content)
        payload["timestamp"] = "__TIMESTAMP__"
        if "cli_flags" in payload and "out" in payload["cli_flags"]:
            payload["cli_flags"]["out"] = "__OUT_DIR__"
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"

    return content


def _build_case_output(base_dir: Path, case: GoldenCase) -> Path:
    spec_path = Path(__file__).parent / "fixtures" / "petstore_v3.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))

    operations = extract_operations(spec)
    filtered_operations, pre_generation_skips = _filter_operations(
        operations,
        include=list(case.include),
        exclude=list(case.exclude),
    )
    scoring = score_operations(filtered_operations, allow_unsafe=case.unsafe)

    out_dir = base_dir / case.name
    result = generate(
        filtered_operations,
        scoring,
        out_dir,
        spec_title=spec["info"]["title"],
        unsafe=case.unsafe,
    )

    skipped_operations = pre_generation_skips + [
        {"operation_id": operation_id, "reason": "unsafe HTTP method requires --unsafe"}
        for operation_id in result.skipped_operations
    ]
    report = build_report(
        spec_title=spec["info"]["title"],
        spec_version=spec["info"]["version"],
        total_operations=len(operations),
        generated_operations=len(filtered_operations) - len(result.skipped_operations),
        skipped_operations=skipped_operations,
        score=scoring,
        generated_files=[path.relative_to(out_dir) for path in result.files],
        cli_flags={
            "source": str(spec_path.relative_to(Path.cwd())),
            "out": str(out_dir),
            "dry_run": False,
            "unsafe": case.unsafe,
            "no_report": False,
            "include": list(case.include),
            "exclude": list(case.exclude),
        },
    )
    (out_dir / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")

    return out_dir


def test_petstore_golden_outputs(tmp_path: Path, update_golden: bool) -> None:
    """Generated Petstore output should match checked-in snapshots."""

    golden_root = Path(__file__).parent / "golden" / "petstore"
    expected_cases = {case.name for case in CASES}

    for case in CASES:
        actual_dir = _build_case_output(tmp_path, case)
        expected_dir = golden_root / case.name

        actual_files = {
            path: _normalized_file_content(path, text, actual_dir)
            for path, text in _collect_files(actual_dir).items()
        }

        if update_golden:
            if expected_dir.exists():
                shutil.rmtree(expected_dir)
            expected_dir.mkdir(parents=True, exist_ok=True)
            for relative_path, content in actual_files.items():
                target = expected_dir / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            continue

        assert expected_dir.exists(), (
            f"Missing golden snapshot for case '{case.name}'. "
            "Run pytest --update-golden tests/test_golden.py to create it."
        )

        expected_files = _collect_files(expected_dir)
        actual_paths = set(actual_files)
        expected_paths = set(expected_files)

        assert actual_paths == expected_paths, (
            f"File set mismatch for golden case '{case.name}'. "
            f"Missing: {sorted(expected_paths - actual_paths)}; "
            f"Unexpected: {sorted(actual_paths - expected_paths)}"
        )

        diffs: list[str] = []
        for relative_path in sorted(expected_paths):
            expected_text = expected_files[relative_path]
            actual_text = actual_files[relative_path]
            if expected_text == actual_text:
                continue
            diff = "\n".join(
                difflib.unified_diff(
                    expected_text.splitlines(),
                    actual_text.splitlines(),
                    fromfile=f"golden/{case.name}/{relative_path}",
                    tofile=f"actual/{case.name}/{relative_path}",
                    lineterm="",
                )
            )
            diffs.append(diff)

        assert not diffs, (
            f"Golden output drift for case '{case.name}'. "
            "Run pytest --update-golden tests/test_golden.py to accept changes.\n\n"
            + "\n\n".join(diffs)
        )

    if update_golden:
        existing_case_dirs = {path.name for path in golden_root.iterdir() if path.is_dir()}
        for stale_case in sorted(existing_case_dirs - expected_cases):
            shutil.rmtree(golden_root / stale_case)
