# llm-config — Design Pattern

A single source of truth for all AI harness configurations: pi, Claude Code, and GitHub Copilot CLI. Edit shared content once; it propagates everywhere. Tests verify congruence.

---

## Guiding principles

1. **Shared content is the canonical source.** Harness-specific files are either generated from shared content or composed by wrapping shared blocks in harness-specific scaffolding. Never edit a harness file to change something that should be universal.
2. **Harness files are deployed directly via symlink.** What's committed is what's live. `git diff` on the repo always reflects the current state of your actual config.
3. **Composition over generation.** Harness markdown files are readable, editable documents. Shared content is embedded inside fenced block markers. `sync.py` guards the fenced regions against drift rather than regenerating whole files from opaque templates.
4. **Agents are rendered, not symlinked.** Because agent frontmatter differs per harness (Copilot adds `model` and `tools`; pi omits them), agent files are rendered by `sync.py` from a canonical shared body. The rendered files live in the repo and are symlinked into place.
5. **Harness-specific sections are first-class.** Things that only make sense in one harness (pi skill routing, Copilot tool declarations, Claude Code `@`-include syntax) are kept in the harness layer and are never touched by sync. The verify tool knows to ignore them.
6. **Blocks are universal or they are not blocks.** A shared block must be byte-for-byte identical in every harness that includes it. If a block needs harness-specific phrasing (e.g., a tool name that differs per harness), that phrasing belongs in the wrapper lines outside the fence — not inside the block. If the *rules themselves* differ per harness, it is not one block but two, and they should have distinct names. There is no per-harness block override mechanism; adding one would erode the invariant that makes `verify.py` simple and trustworthy.

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

All three harnesses use the same `SKILL.md` convention and the same `name`/`description` frontmatter format — they differ only in the directory they load from. This means `shared/skills/wiki-ops/SKILL.md` can be symlinked directly into all three with no per-harness adaptation.

| Harness | Skill directory | Mechanism |
|---------|----------------|-----------|
| pi | `~/.pi/agent/skills/wiki-ops/` | `bootstrap.sh` symlinks `shared/skills/wiki-ops/` |
| Copilot CLI | `~/.copilot/skills/wiki-ops/` | `bootstrap.sh` symlinks `shared/skills/wiki-ops/` |
| Claude Code | `~/.claude/` (no native skill dir) | Skill content referenced via `@`-include in `harnesses/claude-code/CLAUDE.md`: `@llm-config/shared/skills/wiki-ops/SKILL.md` |

New skills follow the same pattern: add `shared/skills/{name}/SKILL.md`, then add symlink entries to `bootstrap.sh` for pi and Copilot, and an `@`-include line in the Claude Code CLAUDE.md.

---

## Symlink map (bootstrap.sh)

`bootstrap.sh` establishes all symlinks on a fresh machine. The exact paths are instance-specific; the README of each repo using this pattern should contain its own full symlink map. The generic structure is:

```
REPO=~/repos/llm-config

# per harness: instruction file, harness-specific configs, skill dirs, agent dir
~/.harness-a/instructions.md    → $REPO/harnesses/harness-a/instructions.md
~/.harness-a/config.json        → $REPO/harnesses/harness-a/config.json
~/.harness-a/skills/my-skill/   → $REPO/shared/skills/my-skill/  (or external source)
~/repos/agents/harness-a/       → $REPO/harnesses/harness-a/agents/
```

`bootstrap.sh` is idempotent: existing correct symlinks are skipped, broken ones replaced.

**MCP registration is not symlinked.** Each harness has its own MCP config format and location. `bootstrap.sh` checks for required MCP registrations and prints warnings for any that are missing, but does not write MCP configs automatically — they may contain tokens or other machine-specific state that should never be committed.

**Machine-specific values** (server addresses, absolute paths) must be edited by hand after bootstrap. They are not templated — templating them would require a separate rendering step and break the "symlinked files are live files" principle. `bootstrap.sh` prints a checklist of required manual steps.

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

## Usage scenarios

These scenarios are the acceptance test for the pattern: if any requires more than one file edit plus a single command, the design should be revisited.

---

### Changing a universal behavior (e.g., banning em-dashes and "it's not X, it's Y" patterns)

1. Edit `shared/blocks/code-style.md` — add the rule in prose.
2. Run `python tools/sync.py --apply` — rewrites the `<!-- block: code-style -->` fence in `harnesses/pi/AGENTS.md`, `harnesses/claude-code/CLAUDE.md`, and `harnesses/copilot/instructions.md` simultaneously.
3. Run `python tools/verify.py` — exits `0` if all three fences now match the canonical source.
4. Commit. Because all three harness files are already symlinked into `~/.pi/agent/`, `~/.claude/`, and `~/.github/`, the change is live immediately with no further propagation step.

Alternatively, ask any agent that has access to this repo: *"Add a rule to code-style.md banning em-dashes and 'it's not X, it's Y' phrasings, then sync and verify."* The agent edits the one file, runs `sync.py --apply`, runs `verify.py`, and reports back. The symlinks do the rest.

**Single file edited:** `shared/blocks/code-style.md`
**Commands:** `sync.py --apply` → `verify.py`
**Manual propagation:** none — symlinks are live

---

### Adding new cross-harness functionality (e.g., connecting to llm-wiki)

This involves two artifacts: a skill (procedural instructions for the LLM) and an activation block (a short note in each harness's global instructions telling it the skill exists).

1. Write `shared/skills/wiki-ops/SKILL.md` — the canonical skill definition.
2. Write `shared/blocks/llm-wiki.md` — a short block explaining how to invoke wiki-ops (the activation hint embedded in every harness's global instructions).
3. Run `bootstrap.sh --skill wiki-ops` — symlinks the skill directory into `~/.pi/agent/skills/wiki-ops/` and `~/.copilot/skills/wiki-ops/`, and adds the `@`-include line to `harnesses/claude-code/CLAUDE.md`.
4. Add `<!-- block: llm-wiki -->` fences in the appropriate section of each harness instruction file, then run `python tools/sync.py --apply` to populate them.
5. Run `python tools/verify.py` — confirms all three harnesses have the identical activation block.

An agent can own steps 3–5 entirely: *"Wire up the wiki-ops skill across all harnesses and verify congruence."* The agent runs bootstrap, adds the fences, syncs, and verifies. You only authored the skill and the block.

**Files authored:** `shared/skills/wiki-ops/SKILL.md`, `shared/blocks/llm-wiki.md`
**Commands:** `bootstrap.sh --skill wiki-ops` → `sync.py --apply` → `verify.py`
**Manual propagation:** none

---

### Adding a new prompt template / persona (e.g., a new "scientist" agent)

1. Write `shared/agents/scientist.md` — body only, no frontmatter. First line: `description: Domain scientist specializing in ...`
2. Run `python tools/sync.py --agents --apply` — renders:
   - `harnesses/pi/agents/scientist.md` (pi frontmatter: `description` only)
   - `harnesses/copilot/agents/scientist.agent.md` (Copilot frontmatter: `description`, `name`, `model`, `tools`)
3. Run `python tools/verify.py` — confirms rendered bodies match the canonical source.
4. Commit. Because `~/repos/agents/pi/` and `~/repos/agents/copilot-cli/` are symlinks into the harness agent dirs, the new agent is immediately accessible in both.

Claude Code has no native agent file format. The persona is available to CC via the pi bridge (`/agent scientist` in a pi session running CC as provider), or by referencing the shared body as a system prompt. If CC gains a native agent format, add it to `harness_agent_config.toml` and re-run sync.

**Single file authored:** `shared/agents/scientist.md`
**Commands:** `sync.py --agents --apply` → `verify.py`
**Manual propagation:** none — symlinks are live

---

### Dropping a harness (e.g., a billing or terms change makes a harness untenable)

This is the exact scenario that motivated this repo. When a harness becomes unavailable or undesirable, the goal is to remove it without touching anything shared.

1. Remove the harness symlinks: run `bootstrap.sh --remove {harness}` (or manually `unlink` each symlink listed in the symlink map for that harness).
2. Move `harnesses/{harness}/` to `harnesses/_deprecated/{harness}/` — keep it in the repo for reference, don't delete it.
3. Remove the harness from `tools/harness_agent_config.toml`.
4. Run `python tools/verify.py` — should pass cleanly since the removed harness is no longer checked.
5. Commit.

Shared blocks, skills, and agent bodies are untouched. The remaining harnesses continue operating without interruption. If the harness comes back (billing restored, terms clarified), restore the symlinks and re-add to `harness_agent_config.toml`.

**Files changed:** `tools/harness_agent_config.toml`, `harnesses/_deprecated/` (move)
**Commands:** `bootstrap.sh --remove {harness}` → `verify.py`
**Risk to other harnesses:** none

---

### Setting up a fresh machine

`bootstrap.sh` is idempotent — safe to re-run. The sequence on a new machine:

1. Clone the repo: `git clone ... ~/repos/llm-config`
2. Run `./tools/bootstrap.sh` — creates all symlinks, checks MCP registrations, reports what needs manual attention.
3. Edit machine-specific values by hand (bootstrap prints a checklist):
   - `harnesses/pi/models.json` — update Ollama `baseUrl` to this machine's address
   - `harnesses/pi/settings.json` — update absolute `prompts` path if it differs
   - Register context-mode in each harness's MCP config (`~/.claude.json`, `~/.copilot/mcp-config.json`, pi internals)
   - Copy `~/.pi/agent/auth.json` from backup or recreate with API keys (never committed)
4. Run `python tools/verify.py` — confirms no drift was introduced during setup.

Machine-specific values are never committed and never synced. The repo is the config; the machine is the runtime. Bootstrap bridges the two.

**Files changed:** machine-local only (MCP configs, auth.json, machine-specific JSON values)
**Commands:** `bootstrap.sh` → `verify.py`
**Committed changes:** none

---

### Updating an existing skill (e.g., improving wiki-ops workflows)

Unlike adding a skill, updating one requires no bootstrap step — symlinks already point at the source.

1. Edit `shared/skills/wiki-ops/SKILL.md` directly.
2. The change is live immediately in pi and Copilot (symlinks) and in Claude Code (file is read at session start via `@`-include).
3. Run `python tools/verify.py` — skills are not block-fenced, so this mainly confirms no instruction file drift was accidentally introduced.
4. Commit.

There is no sync step because the skill directory is symlinked wholesale, not copied or rendered. The canonical file *is* the deployed file for pi and Copilot. For Claude Code the `@`-include re-reads the file on each session, so updates take effect without any action.

**Single file edited:** `shared/skills/wiki-ops/SKILL.md`
**Commands:** `verify.py` (optional sanity check)
**Manual propagation:** none — symlinks and `@`-include handle it

---

## Relationship to external skill repos

Skills with their own source repos (project-specific tooling, domain knowledge bases) are not stored in `llm-config` itself. Instead:

- The canonical `SKILL.md` lives in the source repo (e.g. `~/repos/my-project/.skills/my-skill/`)
- `shared/skills/` holds nothing — it is purely a bootstrap target directory
- `bootstrap.sh` symlinks from the source repo into each harness's skill directory
- Editing the skill in the source repo propagates to all harnesses automatically via symlinks

**Decision rule (the karpathy principle):** a skill travels with the thing it knows about. If a skill is tightly coupled to a specific project or data domain, it stays in that project's repo. If it becomes general-purpose, it graduates to `shared/skills/` in `llm-config` directly. Each repo using this pattern documents its external skill sources in its README.

---

### Promoting a harness-side change to shared (reconciling drift)

This is the scenario where you spend significant time in one harness, improve its instructions directly, then want those improvements to become universal.

`verify.py` (or `sync.py`) will report drift — the harness block differs from `shared/blocks/<name>.md`. Before running `--apply`, decide:

**If the change should be universal:**
1. Open `shared/blocks/<name>.md` and apply the same change there.
2. Run `python tools/sync.py --apply` — propagates the updated block to ALL harnesses (including the one you already edited, which will be a no-op since they now match).
3. Run `python tools/verify.py` — confirm clean.
4. Commit shared source + all harness files together.

**If the change is harness-specific:**
1. Open the harness instruction file and move the changed content to a line *outside* the fence (above or below the `<!-- block -->` markers).
2. Run `python tools/sync.py --apply` — restores the fence content from shared (your harness-specific addition stays, untouched, outside the fence).
3. Commit.

⚠ Never run `--apply` when drift is intentional without promoting first. `--apply` always overwrites harness blocks with shared; the harness change will be lost.

**Summary:**
- Drift detected → inspect before applying
- Universal change → promote to shared first, then sync
- Harness-specific change → move outside fence, then sync

---

### Bootstrapping from zero (no repo, no harness configs)

For someone implementing this pattern from scratch, or restoring to a completely clean machine with nothing installed:

1. **Install harnesses** — install each AI coding assistant you plan to use. Harnesses must exist before bootstrap can wire symlinks into them.

2. **Initialize the repo:**
   ```bash
   mkdir ~/repos/llm-config && cd ~/repos/llm-config
   git init
   mkdir -p shared/blocks shared/agents shared/skills
   mkdir -p harnesses/harness-a harnesses/harness-b
   mkdir -p tools
   ```

3. **Write shared blocks** — create `shared/blocks/*.md` files, one per universal instruction topic (code style, guardrails, tool routing, etc.). These are plain prose — no fencing required in the canonical files.

4. **Create harness instruction files** — for each harness, create its instruction file (e.g. `harnesses/harness-a/instructions.md`) containing the harness-specific wrapper text plus `<!-- block: name -->` fences wherever shared blocks should appear. Leave the fences empty for now.

5. **Run initial sync:**
   ```bash
   python tools/sync.py --apply   # populates all block fences from shared/blocks/
   python tools/verify.py         # should pass clean
   ```

6. **Write bootstrap.sh** — using the symlink map structure documented in this pattern, wire `harnesses/*/` files into their live harness locations. Make it idempotent (`ln -sf`).

7. **Run bootstrap and verify:**
   ```bash
   bash tools/bootstrap.sh
   python tools/verify.py
   git add -A && git commit -m "init: llm-config"
   ```

8. **Complete manual steps** — MCP registrations, API keys, machine-specific config values. `bootstrap.sh` should print a checklist.

---

## Non-goals

- **No config file generation from templates.** Harness JSON/YAML files are edited directly. Only markdown instruction blocks and agent bodies are synced.
- **No runtime injection.** This is a static file management system. There is no daemon watching for changes.
- **No secrets management.** `auth.json`, API keys, and tokens are excluded from the repo via `.gitignore` and documented in `README.md` as manual steps.
