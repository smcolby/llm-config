# llm-config

Single source of truth for AI harness configurations: **pi**, **Claude Code**, and **GitHub Copilot CLI**. Shared content is authored once and propagated to all harnesses via symlinks and a sync tool. A verify script tests congruence and can run as a pre-commit hook.

AI coding assistants each read behavioral instructions from their own config files (`AGENTS.md`, `CLAUDE.md`, `copilot-instructions.md`). When you use more than one, the same rules — code style, safety guardrails, tool routing, agent personas — need to live in each of them. Edit one and you need to remember to update the others. They drift. This repo fixes that: shared rules live in one place, harness configs are derived from them, and a verification step makes drift visible rather than silent.

> **This repository is an instance of the pattern described in [pattern.md](pattern.md).** To implement the pattern for your own setup, point your LLM at `pattern.md` and have it build from scratch — or use this repo as a reference implementation. Adopting the repo directly assumes pi, Claude Code, and GitHub Copilot CLI as your harnesses.

---

## Design rationale

See `pattern.md` for the full design, decision record, and usage scenarios. Key decisions:

- **Composition over generation** — harness files are human-readable; sync only touches fenced regions
- **Symlinks for most files, generated files for machine-specific ones** — files containing absolute paths are rendered from templates by bootstrap.sh with placeholder substitution; everything else is symlinked directly so `git diff` reflects what's deployed
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
  models/          # Shared model provider configs — each *.json symlinked into harnesses that support it; companion *.toml declares which harnesses apply
harnesses/
  pi/              # Pi harness: AGENTS.md, settings.json, models.json (→ shared), mcp.json, extensions/, agents/
  claude-code/     # Claude Code harness: CLAUDE.md, settings.json
  copilot/         # Copilot CLI harness: copilot-instructions.md, mcp-config.json, hooks/, agents/
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
git add -A && git commit -m "Remove <harness> harness"
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
| Ollama host | `shared/models/ollama.json` | Update `baseUrl` from `http://loki.local:11434` to this machine's address |
| Pi auth | `~/.pi/agent/auth.json` | Create with API keys (never committed) |

---

## What's never committed

| Path | Reason |
|------|--------|
| `~/.pi/agent/auth.json` | API keys |
| `harnesses/*/auth.json` | API keys |
| `~/.pi/agent/npm/` | npm-installed pi packages (like node_modules) |
| `~/.pi/agent/git/` | git-installed pi packages (e.g. `git:github.com/smcolby/pi-powerline-footer`) |
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

Extensions (called "tools" in the unified report view) are third-party programs that need per-harness wiring. **llm-config does not install them** — install once at the system level (brew, npm -g, git clone), then llm-config wires every harness from the same `shared/extensions/<name>.toml` manifest. The one wrinkle: pi sandboxes its npm packages into `~/.pi/agent/npm/`, so a global install alone doesn't make a tool visible to pi; the manifest's `verify_pi_package` field declares the package for pi's own sandbox installer.

| Tool | Install yourself first | Wiring manifest |
|-----------|------------------------|-----------------|
| RTK | `brew install rtk` | `shared/extensions/rtk.toml` |
| context-mode | `npm install -g context-mode` | `shared/extensions/context-mode.toml` |
| wiki-ops | *(llm-wiki repo)* | `shared/extensions/wiki-ops.toml` |
| sentrux | *(installed separately)* | `shared/extensions/sentrux.toml` |

**`[[hooks]]` entries** in a manifest define command-based hooks. `wire_extensions.py` renders them into:
- `harnesses/copilot/hooks/<name>.json` — copilot hook JSON (from `copilot_event`)
- `harnesses/pi/extensions/<name>.ts` — pi TypeScript stub (from `pi_event`)

Complex extensions with TypeScript logic beyond a simple command (e.g. RTK's pi extension) remain hand-authored; they use `symlinks` entries as before and are not generated.

**MCP servers** are declared inline in each manifest's top-level `[mcp]` section. A harness opts in to registration by listing `"mcp"` in its `mechanisms` field. `wire_extensions.py` walks every manifest and renders `harnesses/copilot/mcp-config.json` and `harnesses/pi/mcp.json` by aggregating opted-in MCP entries. A tool that exists only as an MCP server (no hooks, no symlinks) still gets its own manifest.

Generated files are committed to the repo (same pattern as rendered agent files). Run `wire_extensions.py` after changing any manifest; `verify.py` catches drift.

`report.py` reads manifests to verify wiring at any time, and presents a single TOOLS table (one row per manifest, one column per harness, mechanism vocabulary in each cell). If a tool is not installed on this machine, its verify checks will fail — that is expected on machines where it has not been installed.

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
python tools/report.py   # full topology: blocks, agents, skills, models, MCP, manifest drift, wiring, generated-file drift
```

Prints every shared component and how it manifests per harness, verifies all symlinks and wiring, and surfaces harness-specific content for gap analysis. Sections covered:

- **EXTENSIONS** — manifest → per-harness wiring (hooks, symlinks, verify checks)
- **SHARED BLOCKS / AGENTS / SKILLS** — what's authored vs how each harness sees it
- **SHARED MODELS** — provider configs and which harnesses consume them
- **TOOLS** — one row per extension manifest, one column per harness, mechanism vocabulary (`hook`, `plugin`, `skill`, `pi-npm`, `pi-ext`, `mcp`, or combinations) in each cell with verify-check status
- **MANIFEST-DERIVED FILES** — drift between `shared/extensions/*.toml` and the per-harness files they render to (hook JSON, pi TypeScript stubs, aggregated MCP configs); same check as `wire_extensions.py --check`
- **HARNESS WIRING** — bootstrap-managed symlinks + generated files; surfaces missing/dangling state
- **GENERATED FILE DRIFT** — live files written by bootstrap from templates vs. the rendered template, with unified diff and resolution instructions; warnings only (manual reconciliation)

Exits non-zero on hard failures (broken symlink, missing render, dangling skill). Generated-file drift is a warning. Requires `rich`: `pip install rich`.

---

## Block authoring rules

- A block must be **byte-for-byte identical in every harness** that includes it — this is the invariant `verify.py` enforces.
- Harness-specific phrasing (e.g., section heading differences like `RTK (TypeScript extension)` vs `RTK (environment-rtk-optimizer)`) belongs in the **wrapper lines outside the fence**, not inside the block.
- If a block needs genuinely different rules per harness, it is not one block — split it and give each a distinct name.
- Blocks are plain markdown prose. No templating, no variables, no conditionals.

The `rtk` block is the canonical example of a correctly shared block: RTK supports Claude Code (PreToolUse hook), Copilot CLI (deny-with-suggestion), and pi (TypeScript extension) with identical LLM-facing instructions across all three. The integration mechanism differs per harness; the instructions do not.

---

## Symlink map (reference)

| Live path | Source in repo |
|-----------|----------------|
| `~/.pi/agent/AGENTS.md` | `harnesses/pi/AGENTS.md` |
| `~/.pi/agent/settings.json` | generated from `harnesses/pi/settings.json` (`__REPO__` substituted by bootstrap.sh) |
| `~/.pi/agent/models.json` | `shared/models/ollama.json` (via `harnesses/pi/models.json` → `shared/models/ollama.json`) |
| `~/.pi/agent/skills/wiki-ops/` | `shared/skills/wiki-ops/` |
| `~/.claude/CLAUDE.md` | generated from `harnesses/claude-code/CLAUDE.md` (`__REPO__` substituted by bootstrap.sh) |
| `~/.claude/settings.json` | generated from `harnesses/claude-code/settings.json` (`__HOME__` substituted by bootstrap.sh) |
| `~/.claude/statusline.sh` | `harnesses/claude-code/statusline.sh` |
| `~/.claude/agents` | `harnesses/claude-code/agents` |
| `~/.claude/skills/llm-wiki` | `~/repos/llm-wiki` (plugin: Stop hook + health-check.sh) |
| `~/.github/copilot-instructions.md` | `harnesses/copilot/copilot-instructions.md` |
| `~/.github/hooks/rtk.json` | `harnesses/copilot/hooks/rtk.json` *(generated)* |
| `~/.github/hooks/context-mode.json` | `harnesses/copilot/hooks/context-mode.json` |
| `~/.github/hooks/wiki-ops.json` | `harnesses/copilot/hooks/wiki-ops.json` *(generated)* |
| `~/.copilot/mcp-config.json` | `harnesses/copilot/mcp-config.json` *(generated)* |
| `~/.copilot/agents/` | `harnesses/copilot/agents/` |
| `~/.pi/agent/mcp.json` | `harnesses/pi/mcp.json` |
| `~/.pi/agent/extensions/rtk.ts` | `harnesses/pi/extensions/rtk.ts` |
| `~/.pi/agent/extensions/wiki-ops.ts` | `harnesses/pi/extensions/wiki-ops.ts` *(generated)* |
| `~/.copilot/skills/wiki-ops/` | `shared/skills/wiki-ops/` |


