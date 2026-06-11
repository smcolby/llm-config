---
name: repo-seed
description: >
  Stand up or refresh a repository's agentic infrastructure from the
  llm-config catalog: detect languages and stack, ask the unresolved axis
  questions, render provenance-stamped rules, and instantiate AGENTS.md
  plus tool configs from a seed archetype. Use when creating a new repo,
  adding agent config to an existing repo, or bringing a seeded repo up to
  date with the catalog (reseed).
reviewed: 2026-06
---

# Repo Seed / Reseed

Deploys catalog content into a repository as committable, provenance-stamped copies. The catalog lives in the llm-config repository (resolve it via the real path of this SKILL.md); seeds live in `shared/seeds/`, rules in `shared/rules/`, and the renderer is `tools/render_rules.py`.

## Seed (new or unseeded repo)

### 1. Detect first

Inspect before asking anything:

- **Languages**: file extensions present (or planned, for an empty repo).
- **Stack**: `pyproject.toml` / lockfiles / imports (FastAPI, NumPy, etc.).
- **Test framework**: test dirs, pytest config, imports.
- **Harnesses in use**: `.cursor/`, `.github/copilot-*` or `.github/instructions/`, `.claude/`, existing `AGENTS.md`.

### 2. Ask only what detection could not resolve

At most four questions, detected values offered as defaults:

1. Purpose archetype: `python-library`, `python-cli`, `python-service`, or `data-science` (pick the closest; mixed repos take the dominant one).
2. Strictness posture: adopt the seed's full gate config, or start lenient (gates warn, tighten later).
3. Target harness formats, only when none are detectable: Cursor project rules, Copilot instructions, neither (AGENTS.md only).
4. Anything genuinely ambiguous from detection (e.g. two candidate archetypes).

### 3. Deploy per the selection matrix

| Content | Action |
|---|---|
| Seed `AGENTS.md` | Instantiate from `shared/seeds/<archetype>/AGENTS.md`, filling project specifics; repo-owned after creation |
| `lang/*` rules for detected languages | Render per detected harness: `python tools/render_rules.py --format mdc --out <repo>/.cursor/rules <rule files>` and/or `--format copilot --out <repo>/.github/instructions` |
| `stack/*` rules matching detected dependencies | Same rendering, after confirming with the user |
| Tool configs | Merge `shared/seeds/<archetype>/pyproject-fragment.toml` into the repo's `pyproject.toml` (never clobber existing sections; reconcile) and add the pre-commit config |
| Doctrine, playbooks, `task/*` rules | Never deployed; they stay global |

Rendered rule copies carry a `provenance:` stamp (canonical path @ catalog commit) injected by the renderer; do not strip it.

### 4. Close out

Run the repo's gates once (`ruff check`, `pyright`, `pytest` if tests exist) so the user sees the baseline; list what was deployed and what was skipped; remind the user to commit.

## Reseed (already-seeded repo)

1. Find deployed copies by their `provenance:` stamps (`.cursor/rules/`, `.github/instructions/`).
2. For each, compare against the current canonical rule; collect diffs.
3. Present diffs grouped by rule; the user approves per rule. Approved: re-render and re-stamp. Declined: add `diverged: true` to the copy's frontmatter so future reseeds stop re-proposing it.
4. Re-run detection: new languages or dependencies since seeding mean new rules to offer; removed ones mean copies to retire.
5. AGENTS.md is repo-owned and never overwritten by reseed; at most, suggest additions.
