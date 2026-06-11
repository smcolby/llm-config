# Project Context: enchiridion

This repository is the single source of truth for AI coding-assistant configuration across three harnesses (pi, Claude Code, Copilot CLI). Content is authored once in `shared/`, propagated by the `tools/` scripts, and deployed through symlinks. It implements two patterns documented in `patterns/`: `cross-harness-config-pattern.md` (distribution) and `agentic-infrastructure-pattern.md` (content architecture). Read the README for usage and the patterns for rationale.

## Environment

- Python 3.11+ (the tools use `tomllib` and modern typing). Dependencies: `pyyaml` (sync), `rich` (report), plus `pre-commit`, `ruff`, and `pyright` for the gate. This is a config-and-scripts repo, not a distributable package: there is no uv project or lockfile, and `pyproject.toml` carries gate config only.
- After cloning: `python tools/bootstrap.py`, then `pip install pre-commit && pre-commit install --hook-type pre-commit --hook-type commit-msg`.

## The one invariant

A shared block is byte-for-byte identical in every harness that includes it. `verify.py` enforces this; never edit a fenced block region in a harness file directly. The same discipline applies to rules (schema-valid frontmatter), agents (stance-only bodies), and the doctrine token ceiling.

## How to change things

Every change ends with `python tools/verify.py` clean, then a commit. Symlinks make the commit live; do not hand-edit live files under `~/.claude`, `~/.pi`, or `~/.github`.

- **Universal behavior** (doctrine): edit `shared/blocks/<topic>.md`, then `python tools/sync.py --apply`. Doctrine has a hard token ceiling; net additions need a demotion candidate.
- **A coding rule**: edit `shared/rules/<axis>/<name>.md` (frontmatter: name, description, tier, scope, stack, reviewed), then `python tools/sync.py --rules --apply` to revalidate and regenerate the router index plus the Claude Code path-scoped renders in `harnesses/claude-code/rules/`. Prefer the `catalog-ingest` skill for external content.
- **A persona**: edit `shared/agents/<name>.md` (stance only; procedure belongs in a playbook, constraints in a rule), then `python tools/sync.py --agents --apply`.
- **A playbook or skill body**: edit `shared/skills/<name>/SKILL.md`; live instantly via symlink. New skills must be added to `tools/harnesses.toml` and wired with `python tools/bootstrap.py --skill <name>`.
- **A project seed** (a repo archetype the `repo-seed` skill stamps into new projects): edit `shared/seeds/<archetype>/` (`seed.toml`, `AGENTS.md`, `pyproject-fragment.toml`, `pre-commit-config.yaml`). Consumed at seed time; no propagation step.
- **An extension** (an MCP server or harness hook): edit `shared/extensions/<name>.toml`, then `python tools/wire_extensions.py` to regenerate the per-harness hook and MCP configs.
- **A model config**: edit `shared/models/<provider>.{json,toml}`, then `python tools/bootstrap.py` to regenerate and rewire the per-harness model files.
- **New wiring** (a new symlink target, generated file, or harness): `python tools/bootstrap.py`. Pure content edits do not need it.

## Conventions

- Follow the global doctrine and the deployed coding rules; consult the `rules` skill index before editing `tools/*.py`.
- One generator-verifier rule: placeholder substitution and registry topology live once in `tools/registry.py`; never duplicate them into a sibling tool.
- Generated files (rendered agents, router index, rendered Claude rules, manifest-derived hooks/MCP configs) are committed so `git diff` shows what changed; regenerate them with the relevant tool rather than editing by hand.
- Do not bypass the gate. The commit-msg hook rejects conventional-commit prefixes and authorship footers; follow the git conventions in doctrine.
