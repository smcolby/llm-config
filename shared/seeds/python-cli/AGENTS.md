# Project Context — Python CLI

This repository is a Python command-line tool: package code under `src/`, entry points declared in `pyproject.toml`, tests in `tests/`.

## Environment

- uv manages the environment: `uv venv` to create, `uv sync` to reproduce, `uv run <cmd>` to execute, `uv add <pkg>` (or `uv add --group dev <pkg>`) to manage dependencies.
- `pyproject.toml` is the single source of project metadata; `uv.lock` is committed.

## CLI conventions

- Entry points live in `[project.scripts]`, never as loose top-level scripts.
- Exit codes: 0 on success, non-zero on failure with a one-line error to stderr.
- stdout carries data (parseable, pipe-friendly); stderr carries diagnostics and progress.
- `--help` is complete and accurate for every command and subcommand; flags follow platform conventions (`--dry-run`, `--verbose`, `--quiet`).
- Destructive operations require confirmation or an explicit `--force`.

## Standing gates

- ruff (lint + format) and pyright strict run via pre-commit and CI. The gates pair with the deployed coding rules: fix the code, never the gate.
- `uv run pytest` before any commit that touches behavior; CLI behavior is tested at the function level, with a thin entry layer.

## Operating model

- Ask before changing command names, flags, or output formats; they are public API.
- Prefer small, incremental, reviewable changes; follow the repository's commit conventions.
- The coding rules deployed in this repo apply to all matching files; read them before editing.
