# Project Context — Blog Analysis

This repository is a lightweight analysis backing a blog post. `blogpost.md` at the repo root is the deliverable; everything else exists to produce its numbers and figures.

## Environment

- uv manages the environment: `uv venv` to create, `uv sync` to reproduce, `uv run <cmd>` to execute, `uv add <pkg>` (or `uv add --group dev <pkg>`) to manage dependencies.
- `pyproject.toml` is the single source of project metadata; `uv.lock` is committed.

## The post

- `blogpost.md` is the featured artifact; the prose writing conventions deployed in this repo govern it strictly.
- Every number, table, and figure in the post is produced by code in this repo and regenerable with a single documented command; a claim the analysis cannot reproduce does not go in the post.
- Figures are generated into `figures/` by scripts, never hand-edited; regenerating them must be cheap enough to do on every revision.
- When the analysis changes, the post changes in the same commit; a post that disagrees with the code behind it is a defect.

## Analysis hygiene

- Analysis code lives in `analysis/` as small, runnable scripts (or a notebook that runs clean top to bottom); logic reused across scripts graduates into package functions with tests.
- `data/` and large outputs are gitignored; the repo stores code, configuration, and the post. Document how to obtain or regenerate data in the README.
- Randomness is seeded and recorded; a result that cannot be reproduced does not exist.

## Standing gates

- ruff (lint + format) and pyright run via pre-commit; analysis scripts are exempt from docstring gates but not from correctness.
- The prose conventions apply to `blogpost.md` and the README alike.

## Operating model

- Prefer small, incremental, reviewable changes; follow the repository's commit conventions.
- The coding rules deployed in this repo apply to all matching files; read them before editing.
