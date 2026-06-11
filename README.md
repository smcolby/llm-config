# llm-config

Single source of truth for AI coding-assistant configuration across three harnesses: **pi**, **Claude Code**, and **GitHub Copilot CLI**. Behavioral content is authored once in `shared/`, propagated to every harness by sync tooling, and deployed through symlinks, so committing a change is deploying it. Drift between harnesses is a verifiable state caught by pre-commit rather than a slow surprise.

The repo implements two companion patterns:

- **[patterns/cross-harness-config-pattern.md](patterns/cross-harness-config-pattern.md)**: the distribution system; how one canonical source reaches many harnesses (blocks, fences, rendering, symlinks, verification).
- **[patterns/agentic-infrastructure-pattern.md](patterns/agentic-infrastructure-pattern.md)**: the content architecture; what that content is, how it is layered and scoped, and when the model sees it.

This repository is one *instance* of those patterns, fitted to its owner's harnesses, languages, and conventions. To adopt the approach, point your LLM at the two pattern documents and mint your own instance; this repo then serves as a worked reference and starting point rather than something to fork wholesale.

Design rationale lives in the patterns. This README covers what is here and how to use it.

## Contents

- [The five layers](#the-five-layers)
- [Repository layout](#repository-layout)
- [Common tasks](#common-tasks)
- [Maintenance](#maintenance)
- [Machine setup](#machine-setup)

## The five layers

Content is organized by how broadly it applies and when the model loads it:

| Layer | What it is | Lives in | Model sees it |
|---|---|---|---|
| **Doctrine** | Universal behavior: style, guardrails, git and writing conventions | `shared/blocks/` | Every session (hard token ceiling) |
| **Rules** | Scoped conventions per language, stack, or task | `shared/rules/` | When matching files or tasks are in play |
| **Playbooks** | Step-by-step procedures: review, test authoring, catalog operations | `shared/skills/` | On demand, by description match |
| **Personas** | Stances for delegated work: critic, tester, planner | `shared/agents/` | When spawned |
| **Seeds** | Templates for standing up new repositories | `shared/seeds/` | Once, at repo creation |

The ordering is a budget: each layer exists to keep content out of the always-on tier above it.

## Repository layout

```
shared/        canonical content
  blocks/      doctrine, fenced into each harness instruction file
  rules/       coding rules (lang/, stack/, task/), indexed into the `rules` router skill
  agents/      persona bodies; frontmatter rendered per harness
  skills/      playbooks + the generated rules router; symlinked into every harness
  seeds/       repo archetypes: AGENTS.md template, gate configs, rule selection
  extensions/  TOML manifests wiring third-party tools (RTK, context-mode, ...)
  models/      shared model-provider configs
harnesses/     per-harness composition: instruction file + configs + rendered agents
patterns/      the two pattern documents this repo implements
tools/         sync, verify, report, bootstrap, render_rules + the harness registry
```

## Common tasks

Every task ends the same way: `python tools/verify.py` clean, then commit. Symlinks make the commit live immediately.

**Change universal behavior** (style, guardrails, conventions):
```bash
$EDITOR shared/blocks/<topic>.md
python tools/sync.py --apply
```

**Add or update a coding rule:**
```bash
$EDITOR shared/rules/lang/python/<name>.md   # or stack/, task/
python tools/sync.py --rules --apply         # validates schema, regenerates router index
```
Prefer the `catalog-ingest` skill when adopting external content; it dedupes and hardens on the way in.

**Add or update a playbook:**
```bash
$EDITOR shared/skills/<name>/SKILL.md        # frontmatter: name, description, reviewed
# new skill only: add it to the skills list in tools/harnesses.toml, then
python tools/bootstrap.py --skill <name>
```
Edits to existing skills are live instantly; symlinks point at the source.

**Add or update a persona:**
```bash
$EDITOR shared/agents/<name>.md
python tools/sync.py --agents --apply        # renders per-harness frontmatter
```
Personas carry stance only; procedure belongs in a playbook, conventions in a rule.

**Seed a repository:** invoke the `repo-seed` skill from any harness session in the target repo. It detects language, stack, environment manager, and existing instruction files, asks at most four questions, and deploys provenance-stamped rules plus an `AGENTS.md`.

**Wire a third-party tool:**
```bash
$EDITOR shared/extensions/<name>.toml        # mechanisms, hooks, verify checks
python tools/bootstrap.py
```

**Reconcile drift** (verify reports a harness file differs from shared): decide first, then act. Promote the change into `shared/` if it should be universal, or move it outside the block fence if harness-specific. ⚠ `sync.py --apply` always overwrites fenced content with shared; promote first or lose the change.

## Maintenance

| Check | Command | When |
|---|---|---|
| Congruence, schemas, doctrine budget | `python tools/verify.py` | Pre-commit (automatic) |
| Live topology: wiring, symlinks, rules, drift | `python tools/report.py` | When things feel off |
| Content rot: stale rules, pins, redundancy | `catalog-audit` skill | Scheduled; after model or stack upgrades |

Two standing habits keep the catalog evidence-based: corrections made twice get captured as rule directives (the capture nudge in doctrine), and external content enters only through `catalog-ingest`.

## Machine setup

```bash
# install harnesses first — each must exist before wiring
npm install -g @anthropic-ai/claude-code @earendil-works/pi-coding-agent @github/copilot

git clone git@github.com:smcolby/llm-config.git ~/repos/llm-config
python ~/repos/llm-config/tools/bootstrap.py   # symlinks everything; prints manual steps
pip install pre-commit
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

Never committed: API keys and `auth.json` files, `~/.claude.json` (harness-managed, may hold tokens), pi sandbox installs and session data, `harnesses/_deprecated/`.
