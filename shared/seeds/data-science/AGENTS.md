# Project Context — Data Science

This repository is a data science project: EDA, notebooks, experiments, and light pipelines. Exploratory work lives in `notebooks/`; code that stabilizes graduates into `src/`.

## Environment

- uv manages the environment: `uv venv` to create, `uv sync` to reproduce, `uv run <cmd>` to execute, `uv add <pkg>` (or `uv add --group dev <pkg>`) to manage dependencies.
- `pyproject.toml` is the single source of project metadata; `uv.lock` is committed.

## Notebook hygiene

- Every committed notebook runs clean top to bottom (`Restart & Run All`); hidden state and out-of-order execution are defects.
- Outputs are stripped before commit (nbstripout or equivalent hook); plots and artifacts are regenerable, never the stored source of truth.
- A notebook that is rerun more than a few times is a pipeline: promote its logic into `src/` functions with tests, and let the notebook call them.

## Data and experiments

- `data/`, model artifacts, and large outputs are gitignored; the repo stores code and configuration, never datasets. Document how to obtain or regenerate data in the README.
- Experiments are reproducible: parameters, seeds, and metrics recorded per run (experiment log, tracked config files, or a tracking tool); a result that cannot be reproduced does not exist.
- Train/test discipline per the project's domain rules: no leakage through global preprocessing before splits.

## Standing gates

- ruff (lint + format) and pyright run via pre-commit on `src/`; notebooks are exempt from docstring gates but not from correctness.
- `uv run pytest` covers `src/`; promoted pipeline code is tested like library code.

## Operating model

- Prefer small, incremental, reviewable changes; follow the repository's commit conventions.
- The coding rules deployed in this repo apply to all matching files; read them before editing.
