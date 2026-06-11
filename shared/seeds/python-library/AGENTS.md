# Project Context — Python Library

This repository is a Python library: importable package code under `src/`, tests beside it, public API documented with NumPy-style docstrings.

## Environment

- uv manages the environment: `uv venv` to create, `uv sync` to reproduce, `uv run <cmd>` to execute, `uv add <pkg>` (or `uv add --group dev <pkg>`) to manage dependencies.
- `pyproject.toml` is the single source of project metadata; `uv.lock` is committed.

## Layout

- `src/<package>/` for code, `tests/` for pytest suites, `pyproject.toml` at the root.

## Standing gates

- ruff (lint + format) and pyright strict run via pre-commit and CI. The gates pair with the deployed coding rules: fix the code, never the gate, and treat a suppression comment as a finding needing justification.
- `uv run pytest` before any commit that touches behavior.

## Operating model

- Ask before changing the public API; API additions carry docstrings and tests in the same change.
- Prefer small, incremental, reviewable changes; follow the repository's commit conventions.
- The coding rules deployed in this repo apply to all matching files; read them before editing.

## Typical tasks

- Implement features with tests (use the test-author playbook where available)
- Run adversarial review before merge (adversarial-review playbook)
- Keep docstrings, examples, and prose docs in sync with code (doc-author playbook)
