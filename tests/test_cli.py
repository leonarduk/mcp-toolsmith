"""CLI smoke tests for the package scaffold."""

from __future__ import annotations

import subprocess
import sys
import unittest


class CLITestCase(unittest.TestCase):
    """Verify the installed CLI entrypoint and module execution."""

    def run_command(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run a command and capture text output."""
        return subprocess.run(args, check=False, capture_output=True, text=True)

    def test_version_flag_reports_package_version(self) -> None:
        """The console script should print the packaged version."""
        result = self.run_command("mcp-toolsmith", "--version")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "mcp-toolsmith 0.1.0")
        self.assertEqual(result.stderr, "")

    def test_generate_stub_runs_cleanly(self) -> None:
        """The generate stub should exit successfully with its placeholder output."""
        result = self.run_command("mcp-toolsmith", "generate")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "not yet implemented")
        self.assertEqual(result.stderr, "")

    def test_module_invocation_displays_help(self) -> None:
        """Running the CLI module directly should show help text."""
        result = self.run_command(sys.executable, "-m", "mcp_toolsmith.cli", "--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("Convert OpenAPI specifications into MCP server templates.", result.stdout)
        self.assertIn("generate", result.stdout)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
