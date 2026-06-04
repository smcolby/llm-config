# llm-config

Single source of truth for AI harness configurations: **pi**, **Claude Code**, and **GitHub Copilot CLI**. Shared content is authored once and propagated to all harnesses via symlinks and a sync tool. A verify script tests congruence and can run as a pre-commit hook.

AI coding assistants each read behavioral instructions from their own config files (`AGENTS.md`, `CLAUDE.md`, `copilot-instructions.md`). When you use more than one, the same rules — code style, safety guardrails, tool routing, agent personas — need to live in each of them. Edit one and you need to remember to update the others. They drift. This repo fixes that: shared rules live in one place, harness configs are derived from them, and a verification step makes drift visible rather than silent.

> **This repository is an instance of the pattern described in [pattern.md](pattern.md).** To implement the pattern for your own setup, point your LLM at `pattern.md` and have it build from scratch — or use this repo as a reference implementation. Adopting the repo directly assumes pi, Claude Code, and GitHub Copilot CLI as your harnesses.

---

## Design rationale

See `pattern.md` for the full design, decision record, and usage scenarios. Key decisions:

- **Composition over generation** — harness files are human-readable; sync only touches fenced regions
- **Symlinks, not copies** — what's committed is what's deployed
- **Blocks are universal or they are not blocks** — no per-harness block variants
- **Agents are rendered** — frontmatter differs per harness; bodies do not
- **Skills live in `shared/skills/`** — general-purpose skills are authored here; symlinks deploy them to all harnesses
- **Extensions are declared, not installed** — globally installed tools are wired per-harness via manifests in `shared/extensions/`; installation is out of scope

---

## How it works

Harness instruction files (`AGENTS.md`, `CLAUDE.md`, `copilot-instructions.md`) contain fenced regions:

```markdown
## Code Formatting & Style
<!-- block: code-style -->
...canonical content, managed by sync.py...
<!-- /block: code-style -->
```

`tools/sync.py` keeps the fenced regions identical to their sources in `shared/blocks/`. Rather than generating harness files wholesale from templates — which would overwrite harness-specific content on every sync — fencing lets sync touch only the shared regions while leaving each harness file otherwise intact and human-readable. Agent/persona files are rendered from `shared/agents/` with harness-appropriate frontmatter. All harness files are symlinked into their live locations by `tools/bootstrap.sh` — what's in the repo is what's deployed.

---

## Repository layout

```
shared/
  blocks/          # Atomic instruction blocks — edit here, propagates everywhere
  agents/          # Canonical agent bodies — frontmatter-free, harness-agnostic
  skills/          # General-purpose skill definitions (e.g., wiki-ops/SKILL.md)
  extensions/      # Extension manifests — one TOML per globally installed tool
harnesses/
  pi/              # Pi harness: AGENTS.md, settings.json, models.json, claude-bridge.json, agents/
  claude-code/     # Claude Code harness: CLAUDE.md, RTK.md, settings.json
  copilot/         # Copilot CLI harness: copilot-instructions.md, hooks/, agents/
tools/
  sync.py                  # Drift detection and block/agent propagation
  verify.py                # Congruence tests — exits non-zero on drift
  bootstrap.sh             # One-time (idempotent) symlink setup
  wire_extensions.py       # Extension symlink wiring (called by bootstrap.sh)
  harness_agent_config.toml  # Per-harness agent frontmatter rules
pattern.md         # Full design rationale and decision record
```

---

## Common tasks

### Change something universal (style rule, guardrail, tool routing)

```bash
# 1. edit the canonical source
$EDITOR shared/blocks/code-style.md   # or whichever block

# 2. propagate to all harness files
python tools/sync.py --apply

# 3. verify
python tools/verify.py

# 4. commit — symlinks make it live immediately
git add -A && git commit -m "..."
```

### Add a new shared block

1. Write `shared/blocks/<name>.md`
2. Add `<!-- block: <name> -->` / `<!-- /block: <name> -->` fences in each harness instruction file where you want it
3. Run `python tools/sync.py --apply && python tools/verify.py`

### Add or update an agent/persona

```bash
# new agent: write shared/agents/<slug>.md with YAML frontmatter (name + description)
# update: edit shared/agents/<slug>.md directly

python tools/sync.py --agents --apply   # renders harnesses/*/agents/
python tools/verify.py
git add -A && git commit -m "..."
# harnesses/pi/agents/ and harnesses/copilot/agents/ are live immediately via symlinks in pi/copilot
```

### Add a new skill

```bash
# 1. write the skill (or locate it in its source repo)
# 2. wire it into pi and copilot
tools/bootstrap.sh --skill <skill-name>

# 3. add @-include to harnesses/claude-code/CLAUDE.md pointing at SKILL.md

# 4. add a shared block with the activation hint
$EDITOR shared/blocks/<skill-name>.md
# add <!-- block: <skill-name> --> fences to each harness instruction file
python tools/sync.py --apply && python tools/verify.py
git add -A && git commit -m "..."
```

### Wire a new extension

Extensions are globally installed tools (via brew, npm, etc.) that need per-harness wiring.

```bash
# 1. install the extension globally on this machine (outside llm-config)

# 2. write shared/extensions/<name>.toml — declare symlinks, verify checks, manual steps
$EDITOR shared/extensions/<name>.toml

# 3. add any harness-side config files the manifest references
#    (e.g., harnesses/copilot/hooks/<name>.json for hook configs)

# 4. write the shared block carrying the LLM-facing instruction content
$EDITOR shared/blocks/<name>.md
# add fences to each harness instruction file, then sync
python tools/sync.py --apply

# 5. run bootstrap to create extension symlinks
bash tools/bootstrap.sh

python tools/verify.py
git add -A && git commit -m "..."
```


### Reconcile drift (harness got ahead of shared)

Run after spending significant time in one harness and refining its instructions directly.

```bash
python tools/verify.py   # shows which blocks drifted and in which harness
```

For each drifted block, decide:

**The change should be universal — promote it:**
```bash
# copy the improved content into the canonical source
$EDITOR shared/blocks/<name>.md

# propagate to all harnesses (including the one you already edited)
python tools/sync.py --apply
python tools/verify.py
git add -A && git commit -m "..."
```

**The change is harness-specific — keep it outside the fence:**
```bash
# open the harness file and move the changed content to a line outside the fence
# (above or below the <!-- block --> markers)
$EDITOR harnesses/<harness>/AGENTS.md  # or CLAUDE.md / copilot-instructions.md

# restore the fence content from shared
python tools/sync.py --apply
python tools/verify.py
git add -A && git commit -m "..."
```

⚠ Running `--apply` without promoting first will silently overwrite the harness change with shared.

### Drop a harness

```bash
tools/bootstrap.sh --remove <harness>   # unlinks symlinks, archives harnesses/<harness>/
# remove harness from tools/harness_agent_config.toml
python tools/verify.py
git add -A && git commit -m "chore: remove <harness> harness"
```

### Fresh machine setup

```bash
# 1. install harnesses — Claude Code, pi, and Copilot CLI must exist before bootstrap
#    Claude Code:  https://claude.ai/download (installs ~/.claude/)
#    pi:           https://pi.ai/download      (installs ~/.pi/)
#    Copilot CLI:  https://github.com/github/copilot-cli-for-beginners

# 2. clone this repo and any external skill repos
git clone git@github.com:smcolby/llm-config.git ~/repos/llm-config

# 3. wire everything
bash ~/repos/llm-config/tools/bootstrap.sh   # symlinks everything, prints a manual-steps checklist

# 4. install pre-commit hooks
pip install pre-commit && pre-commit install
```

Then complete the checklist bootstrap prints:

| Step | File | What to change |
|------|------|----------------|
| Ollama host | `harnesses/pi/models.json` | Update `baseUrl` from `http://loki.local:11434` to this machine's address |
| Prompt path | `harnesses/pi/settings.json` | Update `prompts` absolute path — should be `~/repos/llm-config/harnesses/pi/agents` |
| Pi auth | `~/.pi/agent/auth.json` | Create with API keys (never committed) |
| Extensions | (printed by bootstrap) | One-time per-harness setup for each extension (e.g., `rtk init -g`, plugin installs) |

---

## What's never committed

| Path | Reason |
|------|--------|
| `~/.pi/agent/auth.json` | API keys |
| `harnesses/*/auth.json` | API keys |
| `~/.pi/agent/npm/` | Installed packages (like node_modules) |
| `~/.pi/agent/sessions/` | Ephemeral session data |
| `~/.claude.json` | MCP config — managed by Claude Code, may contain tokens |
| `harnesses/_deprecated/` | Archived harnesses — kept locally, gitignored |

---

## Skills

General-purpose skills live in `shared/skills/<name>/SKILL.md` and are symlinked into each harness by `bootstrap.sh`.

| Skill | Source | Wired to |
|-------|--------|----------|
| `wiki-ops` | `shared/skills/wiki-ops/` | `~/.pi/agent/skills/wiki-ops/`, `~/.copilot/skills/wiki-ops/` |

To add a skill: write `shared/skills/<name>/SKILL.md`, add a `<!-- block: <name> -->` activation hint in `shared/blocks/`, run `bootstrap.sh --skill <name>` and `sync.py --apply`.

To update a skill: edit `shared/skills/<name>/SKILL.md` directly — symlinks deploy the change instantly, no sync step needed.

For domain-specific skills tightly coupled to a single project, the skill can live in that project's repo and be registered in `bootstrap.sh` as an external source. See `pattern.md` for the decision rule.

## Extensions

Extensions are globally installed tools that need per-harness wiring. **llm-config does not install them** — that is the user's responsibility. The repo only owns the wiring: which files to symlink, which mechanism checks to verify, and which one-time setup commands to print in bootstrap's checklist.

| Extension | Install yourself first | Wiring manifest |
|-----------|------------------------|-----------------|
| RTK | `brew install rtk` | `shared/extensions/rtk.toml` |
| context-mode | `npm install -g context-mode` | `shared/extensions/context-mode.toml` |

`report.py` reads manifests to verify extension wiring at any time. If an extension is not globally installed, its verify checks will fail — that is expected on machines where it has not been installed.

## Verify congruence

```bash
python tools/verify.py                   # all harnesses
python tools/verify.py --harness pi      # one harness
python tools/verify.py --agents          # agent bodies only

```

## Linting and type checking

Python tools are linted with [ruff](https://github.com/astral-sh/ruff) and type-checked with [pyright](https://github.com/microsoft/pyright). Config lives in `pyproject.toml`.

```bash
ruff check tools/          # lint
ruff format tools/         # format
npx pyright tools/         # type check
```

All three, plus `verify.py`, run automatically as pre-commit hooks:

```bash
pip install pre-commit
pre-commit install         # installs .pre-commit-config.yaml hooks into .git/hooks/
```

## System inspection

```bash
python tools/report.py   # full topology: blocks, agents, skills, symlinks, harness-specific sections
```

Prints every shared component and how it manifests per harness, verifies all symlinks and wiring, and surfaces harness-specific content for gap analysis. Exits non-zero if any hard check fails (broken symlink, missing render, dangling skill). Requires `rich`: `pip install rich`.

---

## Block authoring rules

- A block must be **byte-for-byte identical in every harness** that includes it — this is the invariant `verify.py` enforces.
- Harness-specific phrasing (e.g., tool name differences like `pi-rtk-optimizer` vs `environment-rtk-optimizer`) belongs in the **wrapper lines outside the fence**, not inside the block.
- If a block needs genuinely different rules per harness, it is not one block — split it and give each a distinct name.
- Blocks are plain markdown prose. No templating, no variables, no conditionals.

The `rtk` block is the canonical example of a correctly shared block: RTK supports Claude Code (PreToolUse hook), Copilot CLI (deny-with-suggestion), and pi (TypeScript extension) with identical LLM-facing instructions across all three. The integration mechanism differs per harness; the instructions do not.

---

## Symlink map (reference)

| Live path | Source in repo |
|-----------|----------------|
| `~/.pi/agent/AGENTS.md` | `harnesses/pi/AGENTS.md` |
| `~/.pi/agent/settings.json` | `harnesses/pi/settings.json` |
| `~/.pi/agent/models.json` | `harnesses/pi/models.json` |
| `~/.pi/agent/claude-bridge.json` | `harnesses/pi/claude-bridge.json` |
| `~/.pi/agent/skills/wiki-ops/` | `shared/skills/wiki-ops/` |
| `~/.claude/CLAUDE.md` | `harnesses/claude-code/CLAUDE.md` |
| `~/.claude/RTK.md` | `harnesses/claude-code/RTK.md` |
| `~/.claude/settings.json` | `harnesses/claude-code/settings.json` |
| `~/.github/copilot-instructions.md` | `harnesses/copilot/copilot-instructions.md` |
| `~/.github/hooks/rtk-rewrite.json` | `harnesses/copilot/hooks/rtk-rewrite.json` |
| `~/.copilot/mcp-config.json` | `harnesses/copilot/mcp-config.json` |
| `~/.copilot/agents/` | `harnesses/copilot/agents/` |
| `~/.pi/agent/mcp.json` | `harnesses/pi/mcp.json` |
| `~/.copilot/skills/wiki-ops/` | `shared/skills/wiki-ops/` |


