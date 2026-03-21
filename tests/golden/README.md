# Golden tests

This directory stores golden fixtures for snapshot-style CLI and generator tests.

## Convention

- Place input fixtures and expected outputs in feature-specific subdirectories.
- Keep expected files small, deterministic, and easy to diff in code review.
- Name snapshots clearly so pytest cases can discover them without custom rules.

## Usage

When a generator or formatter test is added:

1. Create a directory for the scenario under `tests/golden/`.
2. Commit the source fixture and the expected output files together.
3. Make the test compare actual output against the checked-in golden files.
