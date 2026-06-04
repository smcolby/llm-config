# llm-config

Single source of truth for AI harness configurations: **pi**, **Claude Code**, and **GitHub Copilot CLI**. Shared content is authored once and propagated to all harnesses via symlinks and a sync tool. A verify script tests congruence and can run as a pre-commit hook.

AI coding assistants each read behavioral instructions from their own config files (`AGENTS.md`, `CLAUDE.md`, `instructions.md`). When you use more than one, the same rules — code style, safety guardrails, tool routing, agent personas — need to live in each of them. Edit one and you need to remember to update the others. They drift. This repo fixes that: shared rules live in one place, harness configs are derived from them, and a verification step makes drift visible rather than silent.

---

## How it works

Harness instruction files (`AGENTS.md`, `CLAUDE.md`, `instructions.md`) contain fenced regions:

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
  skills/          # Skill symlink targets (wiki-ops points to ~/repos/llm-wiki)
harnesses/
  pi/              # Pi harness: AGENTS.md, settings.json, models.json, claude-bridge.json, agents/
  claude-code/     # Claude Code harness: CLAUDE.md, RTK.md, settings.json
  copilot/         # Copilot CLI harness: instructions.md, agents/
tools/
  sync.py                  # Drift detection and block/agent propagation
  verify.py                # Congruence tests — exits non-zero on drift
  bootstrap.sh             # One-time (idempotent) symlink setup
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
# 2. wire it into both harnesses
tools/bootstrap.sh --skill <skill-name>

# 3. add a shared block with the activation hint
$EDITOR shared/blocks/<skill-name>.md
# add <!-- block: <skill-name> --> fences to each harness instruction file
python tools/sync.py --apply && python tools/verify.py
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
$EDITOR harnesses/<harness>/AGENTS.md  # or CLAUDE.md / instructions.md

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
git clone git@github.com:smcolby/llm-wiki.git  ~/repos/llm-wiki

# 3. wire everything
bash ~/repos/llm-config/tools/bootstrap.sh   # symlinks everything, prints a manual-steps checklist
```

Then complete the checklist bootstrap prints:

| Step | File | What to change |
|------|------|----------------|
| Ollama host | `harnesses/pi/models.json` | Update `baseUrl` from `http://loki.local:11434` to this machine's address |
| Prompt path | `harnesses/pi/settings.json` | Update `prompts` absolute path — should be `~/repos/llm-config/harnesses/pi/agents` |
| CC MCP | `~/.claude.json` | Register context-mode MCP server |
| Copilot MCP | `~/.copilot/mcp-config.json` | Register context-mode MCP server |
| Pi auth | `~/.pi/agent/auth.json` | Create with API keys (never committed) |

---

## What's never committed

| Path | Reason |
|------|--------|
| `~/.pi/agent/auth.json` | API keys |
| `harnesses/*/auth.json` | API keys |
| `~/.pi/agent/npm/` | Installed packages (like node_modules) |
| `~/.pi/agent/sessions/` | Ephemeral session data |
| `~/.claude.json` | MCP config may contain tokens |
| `~/.copilot/mcp-config.json` | MCP config may contain tokens |
| `harnesses/_deprecated/` | Archived harnesses — kept locally, gitignored |

---

## External skill repos

Skills tightly coupled to a specific project or knowledge domain live in that project's repo, not here. This repo wires them into all harnesses via symlinks.

| Skill | Source | Wired to |
|-------|--------|----------|
| `wiki-ops` | `~/repos/llm-wiki/.pi/skills/wiki-ops/` | `~/.pi/agent/skills/wiki-ops/`, `~/.copilot/skills/wiki-ops/` |

To add a new external skill: `bash tools/bootstrap.sh --skill <name>` (skill source must exist first).

To update a skill: edit in the source repo — symlinks propagate changes instantly, no sync step needed.

## Verify congruence

```bash
python tools/verify.py                   # all harnesses
python tools/verify.py --harness pi      # one harness
python tools/verify.py --agents          # agent bodies only

# install as pre-commit hook
echo '#!/bin/sh\npython tools/verify.py --all' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

---

## Block authoring rules

- A block must be **byte-for-byte identical in every harness** that includes it — this is the invariant `verify.py` enforces.
- Harness-specific phrasing (e.g., tool name differences like `pi-rtk-optimizer` vs `environment-rtk-optimizer`) belongs in the **wrapper lines outside the fence**, not inside the block.
- If a block needs genuinely different rules per harness, it is not one block — split it and give each a distinct name.
- Blocks are plain markdown prose. No templating, no variables, no conditionals.

---

## Symlink map (reference)

| Live path | Source in repo |
|-----------|----------------|
| `~/.pi/agent/AGENTS.md` | `harnesses/pi/AGENTS.md` |
| `~/.pi/agent/settings.json` | `harnesses/pi/settings.json` |
| `~/.pi/agent/models.json` | `harnesses/pi/models.json` |
| `~/.pi/agent/claude-bridge.json` | `harnesses/pi/claude-bridge.json` |
| `~/.pi/agent/skills/wiki-ops/` | `~/repos/llm-wiki/.pi/skills/wiki-ops/` |
| `~/.claude/CLAUDE.md` | `harnesses/claude-code/CLAUDE.md` |
| `~/.claude/RTK.md` | `harnesses/claude-code/RTK.md` |
| `~/.claude/settings.json` | `harnesses/claude-code/settings.json` |
| `~/.github/copilot-instructions.md` | `harnesses/copilot/instructions.md` |
| `~/.copilot/skills/wiki-ops/` | `~/repos/llm-wiki/.pi/skills/wiki-ops/` |

---

## Design rationale

See `pattern.md` for the full design, decision record, and usage scenarios. Key decisions:

- **Composition over generation** — harness files are human-readable; sync only touches fenced regions
- **Symlinks, not copies** — what's committed is what's deployed
- **Blocks are universal or they are not blocks** — no per-harness block variants
- **Agents are rendered** — frontmatter differs per harness; bodies do not
- **Skills travel with their domain** — wiki-ops stays in `llm-wiki`; this repo holds the wiring
