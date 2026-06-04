# llm-config — Design Pattern

A single source of truth for all AI harness configurations: pi, Claude Code, and GitHub Copilot CLI. Edit shared content once; it propagates everywhere. Tests verify congruence.

---

## Guiding principles

1. **Shared content is the canonical source.** Harness-specific files are either generated from shared content or composed by wrapping shared blocks in harness-specific scaffolding. Never edit a harness file to change something that should be universal.
2. **Harness files are deployed directly via symlink.** What's committed is what's live. `git diff` on the repo always reflects the current state of your actual config.
3. **Composition over generation.** Harness markdown files are readable, editable documents. Shared content is embedded inside fenced block markers. `sync.py` guards the fenced regions against drift rather than regenerating whole files from opaque templates.
4. **Agents are rendered, not symlinked.** Because agent frontmatter differs per harness (Copilot adds `model` and `tools`; pi omits them), agent files are rendered by `sync.py` from a canonical shared body. The rendered files live in the repo and are symlinked into place.
5. **Harness-specific sections are first-class.** Things that only make sense in one harness (pi skill routing, Copilot tool declarations, Claude Code `@`-include syntax) are kept in the harness layer and are never touched by sync. The verify tool knows to ignore them.

---

## Repository layout

```
llm-config/
├── shared/
│   ├── blocks/                       # Atomic instruction blocks (harness-agnostic prose)
│   │   ├── code-style.md             # Comment/print formatting rules
│   │   ├── execution-guardrails.md   # Safety rules (destructive ops, path checks, etc.)
│   │   ├── rtk.md                    # RTK token-optimizer instructions
│   │   ├── context-mode.md           # ctx_* tool routing rules
│   │   └── llm-wiki.md               # wiki-ops skill activation and conventions
│   ├── agents/                       # Canonical agent/persona bodies (no frontmatter)
│   │   ├── chemoinformatician.md
│   │   ├── coordinator.md
│   │   ├── critic.md
│   │   ├── executor.md
│   │   ├── machine-learning-expert.md
│   │   ├── planner.md
│   │   └── tester.md
│   └── skills/
│       └── wiki-ops/                 # Canonical skill — symlinked into pi; inlined elsewhere
│           └── SKILL.md
├── harnesses/
│   ├── pi/
│   │   ├── AGENTS.md                 # Composed: shared blocks + pi-specific sections
│   │   ├── settings.json             # Pi settings (machine-specific values documented)
│   │   ├── models.json               # Pi model/provider config
│   │   ├── claude-bridge.json        # pi-claude-bridge extension config
│   │   └── agents/                   # Rendered pi prompt templates (from shared/agents/)
│   │       └── *.md
│   ├── claude-code/
│   │   ├── CLAUDE.md                 # Composed: shared blocks + CC-specific sections
│   │   ├── RTK.md                    # RTK block as standalone file (CC @-include target)
│   │   └── settings.json             # Claude Code settings.json
│   └── copilot/
│       ├── instructions.md           # Global Copilot instructions (~/.github/copilot-instructions.md)
│       └── agents/                   # Rendered Copilot agent files (from shared/agents/)
│           └── *.agent.md
├── tools/
│   ├── sync.py                       # Drift detection and block propagation
│   ├── verify.py                     # Congruence tests (CI-safe, exits non-zero on drift)
│   └── bootstrap.sh                  # One-time machine setup: all symlinks
├── .gitignore
└── README.md
```

---

## Shared blocks — composition mechanism

Each harness instruction file (`AGENTS.md`, `CLAUDE.md`, `instructions.md`) embeds shared blocks using HTML comment fences:

```markdown
<!-- block: code-style -->
...content from shared/blocks/code-style.md rendered verbatim here...
<!-- /block: code-style -->
```

`sync.py` reads each `shared/blocks/*.md` file, finds matching fenced regions in all harness files, and either:
- **`--check` (default):** reports blocks that have drifted from the canonical source
- **`--apply`:** rewrites only the fenced regions in place, leaving surrounding harness content untouched

`verify.py` runs `--check` and exits non-zero if any harness block differs from its canonical source. It is the hook for CI and pre-commit.

Blocks are harness-agnostic prose. If a block needs any harness-specific phrasing (e.g., "pi tool" vs "bash tool"), that phrasing lives outside the fence in the harness file, not in the shared block.

---

## Shared agents — render mechanism

The `shared/agents/` directory contains the **body only** of each agent — plain markdown, no frontmatter. Frontmatter is harness-specific:

| Field | pi | Copilot CLI |
|-------|-----|-------------|
| `description` | yes | yes |
| `name` | no | yes |
| `model` | no | yes |
| `tools` | no | yes |

A thin per-harness config (stored in `tools/harness_agent_config.toml`) defines the frontmatter template to prepend per harness:

```toml
[harnesses.copilot]
filename_suffix = ".agent.md"
frontmatter_extra = """
model: claude-sonnet-4-6
tools: ['read', 'search', 'edit', 'execute']
"""

[harnesses.pi]
filename_suffix = ".md"
frontmatter_extra = ""
```

`sync.py --agents` reads `shared/agents/*.md`, renders each to `harnesses/{harness}/agents/`, and reports drift. The rendered files are committed to the repo so the diff is always visible.

**Adding a new agent:** write `shared/agents/my-agent.md` with a `description:` line at the top (used to populate that frontmatter field), then run `sync.py --agents --apply`.

---

## Skills — symlink mechanism

`shared/skills/wiki-ops/SKILL.md` is the canonical skill definition. Each harness consumes it differently:

| Harness | Mechanism |
|---------|-----------|
| pi | `bootstrap.sh` symlinks `shared/skills/wiki-ops/` → `~/.pi/agent/skills/wiki-ops/` |
| Claude Code | `shared/skills/wiki-ops/SKILL.md` content is embedded in `harnesses/claude-code/CLAUDE.md` as an `@`-include: `@llm-config/shared/skills/wiki-ops/SKILL.md` |
| Copilot | Skill content is embedded inline in `harnesses/copilot/instructions.md` via a shared block fence |

New skills follow the same pattern: add `shared/skills/{name}/SKILL.md`, then add harness-specific wiring in `bootstrap.sh` (symlink for pi) and update the relevant harness instruction files.

---

## Symlink map (bootstrap.sh)

`bootstrap.sh` establishes all symlinks on a fresh machine. Run it once after cloning.

```
REPO=~/repos/llm-config   # rename from pi-config after GitHub rename

# pi harness
~/.pi/agent/AGENTS.md            → $REPO/harnesses/pi/AGENTS.md
~/.pi/agent/settings.json        → $REPO/harnesses/pi/settings.json
~/.pi/agent/models.json          → $REPO/harnesses/pi/models.json
~/.pi/agent/claude-bridge.json   → $REPO/harnesses/pi/claude-bridge.json
~/.pi/agent/skills/wiki-ops/     → $REPO/shared/skills/wiki-ops/

# pi agents: keep existing external path, point it at rendered harness dir
~/repos/agents/pi/               → $REPO/harnesses/pi/agents/

# claude code harness
~/.claude/CLAUDE.md              → $REPO/harnesses/claude-code/CLAUDE.md
~/.claude/RTK.md                 → $REPO/harnesses/claude-code/RTK.md
~/.claude/settings.json          → $REPO/harnesses/claude-code/settings.json

# copilot harness
~/.github/copilot-instructions.md → $REPO/harnesses/copilot/instructions.md

# copilot agents: same pattern as pi — keep existing external path
~/repos/agents/copilot-cli/      → $REPO/harnesses/copilot/agents/
```

Machine-specific values (Ollama `baseUrl`, `prompts` absolute paths) are documented in `README.md` and must be edited by hand after bootstrap. They are not templated — templating them would require a separate rendering step and break the "symlinked files are live files" principle.

---

## Congruence testing (verify.py)

`verify.py` checks two things:

1. **Block congruence:** every `<!-- block: name -->` fence in every harness file matches `shared/blocks/{name}.md` verbatim (after normalizing trailing whitespace).
2. **Agent congruence:** the body of every rendered agent file in `harnesses/{harness}/agents/` matches `shared/agents/{name}.md` verbatim (excluding frontmatter lines).

Exit codes:
- `0` — all harnesses are in sync
- `1` — one or more blocks or agent bodies have drifted; diff printed to stdout

Intended usage:
```bash
python tools/verify.py              # check all harnesses
python tools/verify.py --harness pi # check one harness only
```

Add `python tools/verify.py` to `.git/hooks/pre-commit` to catch drift before it lands.

---

## Workflow: editing shared content

**To change something universal** (e.g., update the RTK instructions):
1. Edit `shared/blocks/rtk.md`
2. Run `python tools/sync.py --apply` — rewrites the fenced block in every harness file
3. Commit everything together

**To change something harness-specific** (e.g., pi's model list):
1. Edit `harnesses/pi/models.json` directly
2. Commit — no sync needed

**To add a new agent/persona:**
1. Write `shared/agents/my-agent.md` (body only; `description:` as the first line)
2. Run `python tools/sync.py --agents --apply`
3. Commit the shared source + all rendered harness files together

**To add a new harness:**
1. Create `harnesses/{name}/` with its instruction file(s)
2. Add block fences for all shared blocks you want included
3. Add symlink entries to `bootstrap.sh`
4. Add harness to `tools/harness_agent_config.toml`
5. Run `python tools/sync.py --apply && python tools/verify.py`

---

## What lives where — decision guide

| Content type | Lives in | Reason |
|---|---|---|
| Code style rules | `shared/blocks/code-style.md` | Identical across all harnesses |
| RTK instructions | `shared/blocks/rtk.md` | Same tool, same behavior |
| wiki-ops activation | `shared/blocks/llm-wiki.md` | Same workflow regardless of harness |
| wiki-ops skill definition | `shared/skills/wiki-ops/SKILL.md` | Single canonical skill; consumed differently per harness |
| Agent/persona body | `shared/agents/*.md` | Core behavior is harness-agnostic |
| Agent frontmatter | Generated by `sync.py` from `harness_agent_config.toml` | Frontmatter schema differs per harness |
| pi tool routing | `harnesses/pi/AGENTS.md` (outside fences) | pi-specific: context-mode, pi-lens, pi-subagents |
| CC `@`-include syntax | `harnesses/claude-code/CLAUDE.md` (outside fences) | CC-native mechanism |
| Ollama base URL | `harnesses/pi/models.json` | Machine-specific; never synced |
| pi package list | `harnesses/pi/settings.json` | pi-specific extension ecosystem |
| Copilot `tools` frontmatter | Generated via `harness_agent_config.toml` | Copilot-specific API |

---

## Relationship to llm-wiki

The `~/repos/llm-wiki/` repo holds a project-specific skill (`wiki-ops`) following the same pattern: canonical skill lives in the project, symlinked globally. The `shared/skills/wiki-ops/` directory in this repo replaces the llm-wiki copy as the global canonical source. `bootstrap.sh` symlinks it in place of the current `llm-wiki`-sourced symlink.

This maintains the karpathy-style principle: the skill travels with the thing it knows about. If wiki-ops evolves to be more generic (not llm-wiki-specific), it graduates to `llm-config`. If it stays tightly coupled to wiki conventions, it stays in `llm-wiki` and is referenced from here.

---

## Non-goals

- **No config file generation from templates.** Harness JSON/YAML files are edited directly. Only markdown instruction blocks and agent bodies are synced.
- **No runtime injection.** This is a static file management system. There is no daemon watching for changes.
- **No secrets management.** `auth.json`, API keys, and tokens are excluded from the repo via `.gitignore` and documented in `README.md` as manual steps.
