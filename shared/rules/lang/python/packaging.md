---
name: python-packaging
description: >
  Python project layout and dependency management: uv environments,
  pyproject.toml as single source, src layout, lockfile policy, and the
  ruff/pyright standing gate. Apply when creating or modifying
  pyproject.toml, lockfiles, requirements files, or project scaffolding.
tier: scoped
scope: ["**/pyproject.toml", "**/uv.lock", "**/requirements*.txt", "**/setup.py", "**/setup.cfg"]
stack: ["uv>=0.5"]
reviewed: 2026-06
---

You are an expert in modern Python packaging and project structure.

## Principles

1. One file owns project metadata: `pyproject.toml`. Anything duplicating it is drift waiting to happen.
2. Environments are disposable; lockfiles make them reproducible.
3. The lint and type gate is part of the project, never a personal preference.

## Environment and dependencies

- uv for everything: `uv venv` to create, `uv add` / `uv remove` to manage dependencies, `uv run` to execute, `uv sync` to reproduce.
- Dependencies declared in `pyproject.toml` with sensible lower bounds; exact pins live in `uv.lock`, committed.
- Dev tooling (pytest, ruff, pyright, pre-commit) in a `dev` dependency group, never mixed into runtime dependencies.
- Never `pip install` into a project environment ad hoc; if it is needed, it is declared.

## Layout

- src layout: `src/<package>/` with tests in `tests/` beside it, never inside the package.
- `setup.py` and `setup.cfg` do not appear in new projects; existing ones migrate to `pyproject.toml` when touched.
- Entry points declared in `[project.scripts]`, never as loose top-level scripts.

## Standing gate

- ruff (lint + format) and pyright configured in `pyproject.toml`, run via pre-commit and CI.
- Gate configuration changes are reviewed like code: loosening a rule needs a reason in the commit message.

## Anti-hallucination

| Banned | Correct |
|---|---|
| `requirements.txt` as the source of truth | `pyproject.toml` + `uv.lock` |
| `python -m venv` + `pip` in new projects | `uv venv` + `uv add` |
| `setup.py develop` / `pip install -e .` | `uv sync` (or `uv pip install -e .` only when an editable install is genuinely required) |
| `[tool.poetry]` sections in new projects | PEP 621 `[project]` table |
