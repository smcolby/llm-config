# llm-config — Design Pattern

This document describes the design of a single-repo system for managing AI harness configurations across multiple coding assistants. It covers the problems it solves, the principles behind the decisions, and the specific mechanisms used to implement them.

---

## Problem this solves

AI coding assistants read behavioral instructions from harness-specific files: `AGENTS.md` (pi), `CLAUDE.md` (Claude Code, Anthropic), `copilot-instructions.md` (GitHub Copilot CLI, GitHub/Microsoft). When you work across multiple assistants, the same rules need to appear in each — code formatting conventions, safety guardrails, tool routing instructions, agent personas. Edit one harness and you need to remember to update the others. They drift. Sometimes intentionally (a rule that only makes sense for one harness); more often accidentally, as a silent accumulation.

The naive fix — copy-paste shared content, update all copies manually — fails immediately: there's no authoritative version, no automated way to detect divergence, and no record of what changed where. The result is either a high-overhead maintenance burden or configs that gradually diverge until two assistants behave meaningfully differently for no intentional reason.

This pattern solves it by keeping shared content in a single source and making all harness files derive from it, with a lightweight verification step that makes drift a visible, actionable state rather than a silent one.

---

## Guiding principles

1. **Shared content is the canonical source.** Harness-specific files are either generated from shared content or composed by wrapping shared blocks in harness-specific scaffolding. Never edit a harness file to change something that should be universal.
2. **Harness files are deployed via symlink or template generation.** Most files are symlinked directly — what's committed is what's live. Files that must contain machine-specific absolute paths (e.g., agent prompt directories, statusline commands) are generated from templates by `bootstrap.py` using placeholder substitution, keeping those paths out of the committed source.
3. **Composition over generation.** Harness markdown files are readable, editable documents. Shared content is embedded inside fenced block markers. `sync.py` guards the fenced regions against drift rather than regenerating whole files from opaque templates.
4. **Agents are rendered, not symlinked.** Because agent frontmatter differs per harness (Copilot adds `model` and `tools`; pi omits them), agent files are rendered by `sync.py` from a canonical shared body. The rendered files live in the repo and are symlinked into place.
5. **Harness-specific sections are first-class.** Things that only make sense in one harness (pi skill routing, Copilot tool declarations, Claude Code `@`-include syntax) are kept in the harness layer and are never touched by sync. The verify tool knows to ignore them.
6. **Blocks are universal or they are not blocks.** A shared block must be byte-for-byte identical in every harness that includes it. If a block needs harness-specific phrasing (e.g., a tool name that differs per harness), that phrasing belongs in the wrapper lines outside the fence — not inside the block. If the *rules themselves* differ per harness, it is not one block but two, and they should have distinct names. There is no per-harness block override mechanism; adding one would erode the invariant that makes `verify.py` simple and trustworthy.
7. **Harness topology is declared once.** A single registry file (`tools/harnesses.toml`) lists every harness: its instruction file, its symlinks and generated files, its skill directory, and its agent frontmatter rules. Sync, report, and bootstrap all read the registry, so adding or dropping a harness is a registry edit — never parallel edits to multiple tools. The same discipline applies to anything machine-specific: placeholder substitution is defined in exactly one function (`registry.py`), used by both the generator (`bootstrap.py`) and the verifier (`report.py`). If a generator and its verifier each carry their own copy of a rule, a bug in the rule is invisible to verification.

---

## Repository layout

The structure below is the generic shape. Instance-specific file names (block topics, agent names, harness config filenames) are shown as placeholders.

```
llm-config/
├── shared/
│   ├── blocks/                       # Atomic instruction blocks — one file per universal topic
│   │   └── <topic>.md
│   ├── agents/                       # Canonical agent/persona bodies — no frontmatter
│   │   └── <persona>.md
│   ├── skills/                       # General-purpose skills with no domain coupling
│   │   └── <skill>/SKILL.md
│   ├── extensions/                   # Extension manifests — one TOML per globally installed tool
│   │   └── <extension>.toml
│   └── models/                       # Shared model provider configs — one JSON + companion TOML per provider
│       ├── <provider>.json
│       └── <provider>.toml           # declares which harnesses support this provider
├── harnesses/
│   ├── <harness-a>/
│   │   ├── <instruction-file>.md     # Composed: shared blocks + harness-specific sections
│   │   ├── <config>.json             # Harness-specific config (settings, models, etc.)
│   │   └── agents/                   # Rendered agent files (from shared/agents/)
│   │       └── <persona>.<suffix>.md
│   └── <harness-b>/
│       └── ...
├── tools/
│   ├── harnesses.toml                # Harness registry — single source of harness topology
│   ├── registry.py                   # Registry loader + placeholder substitution (one definition)
│   ├── sync.py                       # Drift detection and block/agent propagation
│   ├── verify.py                     # Congruence tests (exits non-zero on drift)
│   ├── bootstrap.py                  # Idempotent machine setup (symlinks, generated files, skills)
│   └── wire_extensions.py            # Extension file generation and wiring (called by bootstrap.py)
├── .gitignore
└── README.md
```

The instance-specific layout (actual block names, agent names, harness config files) is documented in this repo's README.

---

## Harness registry — one declaration of topology

Every tool in the system needs to know the same facts about each harness: where its instruction file lives in the repo, where the harness reads it from, which files are symlinked vs generated, where skills go, and how agent frontmatter is rendered. If each tool carries its own copy of those facts (a dict in the sync tool, a wiring table in the report tool, hardcoded paths in the bootstrap script), they drift apart — exactly the disease this pattern exists to cure, reproduced inside its own tooling.

The fix is a single registry file, `tools/harnesses.toml`, with one entry per harness:

```toml
skills = ["<skill-name>", ...]        # shared skills wired into every harness

[harnesses.<name>]
root = "~/.<harness>"                 # presence of this dir == harness installed
instruction_file = "harnesses/<name>/<instructions>.md"
instruction_live = "~/.<harness>/<instructions>.md"
skill_dir = "~/.<harness>/skills"
symlinks = [["<repo path>", "<live path>"], ...]
generated = [["<repo template>", "<live path>"], ...]

[harnesses.<name>.agents]             # agent frontmatter rules (see Shared agents)
filename_suffix = ".md"
include_fields = ["name", "description"]
```

A small loader module (`tools/registry.py`) parses the registry and exposes it to `sync.py`, `report.py`, and `bootstrap.py`. It also owns the one `render_template()` function that substitutes machine-specific placeholders (`__REPO__`, `__HOME__`) into generated files. Bootstrap renders with it; report verifies against it. Keeping generator and verifier on the same function is load-bearing: if they each implement substitution separately, a bug in the rules produces identical wrong output on both sides and verification passes silently.

Adding a harness is a registry entry plus block fences in its instruction file. Dropping one is `bootstrap.py --remove <name>` plus deleting the entry.

---

## Shared blocks — composition mechanism

The central challenge of keeping harness configs in sync is that each harness file is not *only* shared content — it also has harness-specific sections that should never be overwritten. Full template generation (render the whole file from a template) would erase those sections on every sync. Copying files wholesale has the same problem. Fencing solves it: each harness instruction file embeds shared blocks between HTML comment markers, and sync only touches what's between those markers.

Each harness instruction file (`AGENTS.md` for pi, `CLAUDE.md` for Claude Code, `copilot-instructions.md` for GitHub Copilot CLI) embeds shared blocks using HTML comment fences:

```markdown
<!-- block: code-style -->
...content from shared/blocks/code-style.md rendered verbatim here...
<!-- /block: code-style -->
```

`sync.py` reads each `shared/blocks/*.md` file, finds matching fenced regions in all harness files, and either:
- **(default, no flag):** reports blocks that have drifted from the canonical source
- **`--apply`:** rewrites only the fenced regions in place, leaving surrounding harness content untouched

`verify.py` runs `--check` and exits non-zero if any harness block differs from its canonical source. It is the hook for CI and pre-commit.

Blocks are harness-agnostic prose. If a block needs any harness-specific phrasing (e.g., a tool name that differs per harness), that phrasing lives outside the fence in the harness file — not in the shared block.

---

## Shared agents — render mechanism

Agent files cannot be symlinked wholesale because their frontmatter schemas differ per harness: Copilot CLI requires `name`, `model`, and `tools` fields while pi only uses `description`. If a single file were symlinked to both harnesses, it would either have the wrong fields for one of them or require a lowest-common-denominator format that satisfies neither. The solution is to store only the body (the actual behavioral content, which is harness-agnostic) in shared, and render harness-appropriate frontmatter on top of it.

Each file in `shared/agents/` has minimal YAML frontmatter (`name:` and `description:`) followed by the harness-agnostic body. `sync.py` reads the frontmatter fields it needs and discards the rest when rendering harness files. Frontmatter rendered into each harness:

| Field | pi | Copilot CLI | Claude Code |
|-------|-----|-------------|-------------|
| `description` | yes | yes | yes |
| `name` | no | yes | yes |
| `model` | no | yes | no (inherits session model) |
| `tools` | no | yes (YAML list) | yes (comma-separated string) |

The `[harnesses.<name>.agents]` sub-table in the harness registry controls which fields appear and what values to use for static fields:

```toml
[harnesses.pi.agents]
filename_suffix = ".md"
include_fields = ["description"]

[harnesses.copilot.agents]
filename_suffix = ".agent.md"
include_fields = ["name", "description", "model", "tools"]
model = "claude-sonnet-4-6"
tools = ["read", "search", "edit", "execute"]

[harnesses.claude-code.agents]
filename_suffix = ".md"
include_fields = ["name", "description", "tools"]
tools = "Read, Edit, Bash, Glob, Grep, Write"
```

`sync.py --agents` reads `shared/agents/*.md`, renders each to `harnesses/{harness}/agents/`, and reports drift. The rendered files are committed to the repo so the diff is always visible.

**Adding a new agent:** write `shared/agents/my-agent.md` with YAML frontmatter containing at minimum `name:` and `description:` (sync.py reads these when building harness frontmatter), then run `sync.py --agents --apply`.

---

## Skills — symlink mechanism

Unlike instruction blocks (embedded fragments that need fencing) and agents (files with varying frontmatter), skill definitions are self-contained `SKILL.md` files with a uniform format across all harnesses. There is no per-harness adaptation needed, so the entire skill directory can be symlinked wholesale rather than rendered or fenced. Skills also tend to be longer and more complex than blocks, making embedding them inline impractical.

Skills come from one of two places:
- **`shared/skills/<name>/`** — for general-purpose skills with no domain coupling
- **An external domain repo** — for skills tightly coupled to a specific project or knowledge base (see [Relationship to external skill repos](#relationship-to-external-skill-repos))

Each harness declares a `skill_dir` in the harness registry; `bootstrap.py` symlinks every registered skill into every declared skill directory. The skill's `SKILL.md` carries YAML frontmatter (`name`, `description`) so harnesses can offer the skill on demand rather than carrying its full text in every session.

| Harness | Live skill directory | Mechanism |
|---------|---------------------|-----------|
| pi | `~/.pi/agent/skills/<name>/` | `bootstrap.py` symlinks the skill directory |
| Copilot CLI | `~/.copilot/skills/<name>/` | `bootstrap.py` symlinks the skill directory |
| Claude Code | `~/.claude/skills/<name>/` | `bootstrap.py` symlinks the skill directory |

On-demand loading via a native skill directory is strongly preferred over inlining: an `@`-include line in the global instruction file (pointing at `SKILL.md`) also delivers the content, but it loads the full skill into every session whether or not it is needed. Treat `@`-includes as a fallback for a harness with no native skill support.

Claude Code's `~/.claude/skills/` directory serves double duty: it is both a skill directory and a plugin directory (for repos that define `hooks/hooks.json` and `.claude-plugin/plugin.json`). The `enabledPlugins` key in `settings.json` activates plugins installed here.

New skills follow the same pattern: if general-purpose, add `shared/skills/{name}/SKILL.md` and register the name in the registry's `skills` list; if domain-specific, place it in the domain repo and register it in `bootstrap.py` as an external source. Then run `bootstrap.py --skill <name>`. If the skill repo also ships hooks, enable it as a plugin in `settings.json`.

---

## Extensions / tools — wiring globally installed third-party tools

Skills and blocks handle LLM-authored content. Tools (called "extensions" in the codebase) are a different category: third-party programs (installed via brew, npm, or cloned from git) that need per-harness configuration to activate. The installation itself is outside llm-config's scope; the repo owns the wiring only.

The expected install paradigm is **install once at the system level, then llm-config wires each harness**. Two caveats: (1) some harnesses sandbox their tooling, e.g. pi installs npm packages into `~/.pi/agent/npm/` regardless of any global install, so for pi the wiring is a *declaration in `pi/settings.json` `packages[]`* that pi resolves into a sandboxed install; (2) MCP servers register per-harness in each harness's MCP config file, except where the harness loads MCP servers through a plugin runtime (e.g. Claude Code, where the plugin directory's manifest registers MCP servers without a config entry).

Each tool is declared in one TOML manifest at `shared/extensions/<name>.toml`. `wire_extensions.py` generates harness-specific files from those declarations: copilot hook JSON files, pi TypeScript extension stubs, and aggregated MCP configs.

**Manifest schema:**

```toml
name = "MyTool"
repo = "https://github.com/owner/mytool"
install = "brew install mytool"   # for reference; not run by llm-config
block = "mytool"                  # shared block carrying the LLM-facing instructions

# Optional: top-level [mcp] section if this tool ships an MCP server.
# Harnesses opt in by listing "mcp" in their mechanisms.
[mcp]
command = "mytool"
args = ["--mcp"]

# Optional: command-based hooks rendered per harness by wire_extensions.py.
# Each [[hooks]] entry becomes one event handler. copilot_event → JSON file;
# pi_event → TypeScript stub. Omit a field to skip that harness.
[[hooks]]
copilot_event = "PreToolUse"
pi_event = "tool_call"
command = "mytool hook"
timeout = 5

[harnesses.claude-code]
mechanisms = ["hook"]                  # vocabulary used in the TOOLS table
verify_hook = "mytool hook claude"     # substring to find in PreToolUse hook commands
manual_setup = "mytool init -g"        # one-time command, printed in bootstrap checklist

[harnesses.copilot]
mechanisms = ["hook", "mcp"]
symlinks = [["harnesses/copilot/hooks/mytool.json", "~/.github/hooks/mytool.json"]]
verify_mcp = "~/.copilot/mcp-config.json"
manual_setup = "mytool init -g --copilot"

[harnesses.pi]
mechanisms = ["pi-ext", "mcp"]
symlinks = [["harnesses/pi/extensions/mytool.ts", "~/.pi/agent/extensions/mytool.ts"]]
verify_mcp = "~/.pi/agent/mcp.json"
# omit the entire [harnesses.<h>] block if this tool isn't wired for that harness
```

The `mechanisms` field is the integration-shape vocabulary; report.py renders it directly into the TOOLS table cell. Conventional values: `hook` (settings hook or hook JSON), `plugin` (plugin directory), `skill` (skill symlink), `pi-npm` / `pi-git` (pi sandbox install), `pi-ext` (pi TypeScript extension), `mcp` (MCP server registration).

Tools whose pi wiring requires more than a simple command (e.g. version checks, custom rewrite logic) should keep a hand-authored `.ts` file and use `symlinks` without `[[hooks]]`. Tools that exist only as MCP servers (no hook, no symlink, no install overhead) still get a manifest — just `name` + `[mcp]` + a `[harnesses.<h>]` block with `mechanisms = ["mcp"]`.

Supported verify check types (one per harness, checked by `report.py`):
- `verify_hook`: substring to find in a PreToolUse hook command in the Claude Code settings
- `verify_dir`: directory path to check for existence (used for plugin installs)
- `verify_mcp`: path to an MCP config file to check for server registration
- `verify_pi_package`: package identifier (e.g. `npm:context-mode`) to find in `harnesses/pi/settings.json` `packages[]`

**`wire_extensions.py`** reads all manifests, then:
1. Generates copilot hook JSON files and pi TypeScript stubs from `[[hooks]]` entries
2. Generates harness MCP configs by walking every manifest's `[mcp]` section and including each in the harnesses that opt in via `mechanisms = [..., "mcp"]`
3. Creates `symlinks` declared per harness
4. Prints a `manual_setup` checklist for one-time steps that cannot be automated

Pass `--check` to report drift in generated files without writing. `verify.py` calls this automatically.

Generated files are committed to the repo (same pattern as rendered agent files) — `git diff` always shows what changed. `bootstrap.py` calls `wire_extensions.py` automatically. **Adding a new extension requires no changes to `bootstrap.py` or `report.py`** — drop a TOML in `shared/extensions/` and both tools pick it up.

The LLM-facing instruction content for each extension lives in the shared block named by `block`. The manifest handles only the mechanism (wiring and generation); the block handles the content (what the LLM reads).

---

## Symlink map (bootstrap.py)

Symlinks are what make the repo the live config: because harness files are symlinked into the locations each assistant reads from, committing a change IS deploying it. There is no separate deploy step, no copy to keep in sync with the repo, no risk of the live file and the committed file diverging. `git diff` always reflects what's actually running.

`bootstrap.py` establishes all symlinks on a fresh machine, reading the wiring from the harness registry. The exact paths are instance-specific; the README of each repo using this pattern should contain its own full symlink map. The generic structure is:

```
REPO=~/repos/llm-config

# per harness: instruction file, harness-specific configs, skill dirs
~/.harness-a/instructions.md    → $REPO/harnesses/harness-a/instructions.md
~/.harness-a/config.json        → $REPO/harnesses/harness-a/config.json
~/.harness-a/skills/my-skill/   → skill source (shared/skills/ or external repo)
```

`bootstrap.py` is idempotent: existing correct symlinks are skipped, broken ones replaced.

**MCP configs are committed and symlinked** for harnesses whose configs are token-free (e.g. pi and Copilot). `bootstrap.py` symlinks them like any other harness file. The one exception is `~/.claude.json`, which Claude Code manages itself and may contain tokens — it is gitignored and never committed.

**Machine-specific values** fall into two categories. Absolute paths embedded in config files (e.g., a `prompts` directory path, a statusline command path) are handled via placeholder substitution: the committed file contains a placeholder (`__REPO__` or `__HOME__`), and `bootstrap.py` generates the live file with the placeholder replaced. These files are declared under `generated` in the registry rather than `symlinks`, and the substitution function lives in `registry.py` so the report tool verifies against exactly what bootstrap renders. Other machine-specific values (e.g., a remote server's hostname in a model config) cannot be inferred and must be edited by hand after bootstrap. `bootstrap.py` prints a checklist of any remaining manual steps.

---

## Congruence testing (verify.py)

Without a congruence check, drift is invisible. The natural workflow — refining instructions while actively working in a specific harness — means you regularly improve one harness's config directly. Without a tool to detect when those improvements diverge from the shared source, the divergence just accumulates silently. Two harnesses start behaving differently for no intentional reason, and you can't tell from the files themselves when the split happened or whether it was deliberate.

`verify.py` makes drift a visible, actionable state rather than a silent one. It checks two things:

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

Pre-commit hooks (configured in `.pre-commit-config.yaml`) run `verify.py` alongside ruff and pyright on every commit.

---

## System inspection (report.py)

`verify.py` guards against content drift but says nothing about whether the live system is actually wired. A block can be byte-for-byte correct in the repo and still not be deployed if its instruction file's symlink is broken. A skill can be defined and never linked. Without a tool to surface the live state, the gap between *what the repo says* and *what's actually running* is invisible.

`report.py` provides a human-readable view of the full system topology at any point in time. It shows:
- Every shared block, which harnesses include it as a fence, and whether the instruction file is correctly symlinked or generated into its live location
- Every shared agent, which harnesses have a rendered file
- Every detected skill, whether its symlinks are valid and non-dangling, and the live target path
- Every shared model config, which harnesses have a symlink to it, and which harnesses are explicitly excluded (e.g. cloud-only harnesses that can't use local model routing)
- A unified TOOLS table showing each declared tool's integration mechanism per harness (one row per tool, one column per harness, mechanism vocabulary in each cell — `hook`, `plugin`, `skill`, `pi-npm`, `pi-ext`, `mcp`, or `+`-joined combinations)
- Drift between manifest sources (`shared/extensions/*.toml`) and the per-harness files they render to in the repo (same check as `wire_extensions.py --check`)
- All bootstrap-managed symlinks and generated files, plus their wiring status
- Drift between bootstrap-generated live files (with placeholders resolved) and the rendered template — surfaced as a warning with a unified diff and manual-resolution instructions

Run it with:
```bash
python tools/report.py
```

Exit codes:
- `0` — all hard checks passed (symlinks valid, renders present, skill targets exist); generated-file drift is a warning, not an error, and does not affect exit status
- `1` — at least one hard check failed; details printed inline

Harness-specific sections are always shown and never cause a non-zero exit — they are diagnostic, not errors. The intent is to make intentional per-harness differences visible so you can decide whether to promote them to shared blocks or leave them as deliberate divergence.

`report.py` requires `rich` (`pip install rich`) for formatted output.

---

## Workflow: editing shared content

**To change something universal** (e.g., update the RTK instructions):
1. Edit `shared/blocks/rtk.md`
2. Run `python tools/sync.py --apply` — rewrites the fenced block in every harness file
3. Commit everything together

**To change something harness-specific** (e.g., pi's model list):
1. Edit `shared/models/ollama.json` directly (symlinked into pi via `harnesses/pi/models.json`)
2. Commit — no sync needed

**To add a new agent/persona:**
1. Write `shared/agents/my-agent.md` (body only; `description:` as the first line)
2. Run `python tools/sync.py --agents --apply`
3. Commit the shared source + all rendered harness files together

**To add a new harness:**
1. Create `harnesses/{name}/` with its instruction file(s)
2. Add a `[harnesses.{name}]` entry to `tools/harnesses.toml` (wiring + agent rules) — sync, report, and bootstrap all pick it up from there
3. Add block fences for all shared blocks you want included
4. Run `python tools/bootstrap.py && python tools/sync.py --apply && python tools/verify.py`

---

## What lives where — decision guide

| Content type | Lives in | Reason |
|---|---|---|
| Universal instruction (style, guardrails, tool routing) | `shared/blocks/<topic>.md` | Identical across all harnesses |
| Harness-specific instruction | Harness instruction file, outside block fences | Only meaningful for that harness |
| Agent/persona body | `shared/agents/<persona>.md` | Core behavior is harness-agnostic |
| Agent frontmatter | Rendered by `sync.py` from the registry's `agents` sub-tables | Schema differs per harness |
| Harness wiring (symlinks, generated files, skill dirs) | `tools/harnesses.toml` | One registry read by sync, report, and bootstrap |
| General-purpose skill | `shared/skills/<name>/SKILL.md` | No per-harness adaptation needed |
| Domain-specific skill | External domain repo; symlinked by `bootstrap.py` | Evolves with the domain it serves |
| Extension wiring | `shared/extensions/<name>.toml` | Per-harness wiring for globally installed tools |
| Extension instruction content | `shared/blocks/<name>.md` | Same as any other shared block |
| Model provider config (multi-harness) | `shared/models/<provider>.json` + `.toml` | Config consumed by harness runtimes that support a multi-provider registry (e.g. pi); harnesses with alternative wiring (e.g. Claude Code via `ollama launch claude`) are noted in the companion `.toml` |
| Harness-specific config | `harnesses/<harness>/<config>.json` | Harness or machine specific; never synced |
| Machine-specific values | Edited in-place after bootstrap, never committed | Must match this machine's runtime |
| API keys / tokens | Gitignored paths only | Security |

---

## Usage scenarios

These scenarios are the acceptance test for the pattern: if any requires more than one file edit plus a single command, the design should be revisited.

---

### Changing a universal behavior (e.g., banning em-dashes and "it's not X, it's Y" patterns)

1. Edit `shared/blocks/code-style.md` — add the rule in prose.
2. Run `python tools/sync.py --apply` — rewrites the `<!-- block: code-style -->` fence in `harnesses/pi/AGENTS.md`, `harnesses/claude-code/CLAUDE.md`, and `harnesses/copilot/copilot-instructions.md` simultaneously.
3. Run `python tools/verify.py` — exits `0` if all three fences now match the canonical source.
4. Commit. Because all three harness files are already symlinked into `~/.pi/agent/`, `~/.claude/`, and `~/.github/`, the change is live immediately with no further propagation step.

Alternatively, ask any agent that has access to this repo: *"Add a rule to code-style.md banning em-dashes and 'it's not X, it's Y' phrasings, then sync and verify."* The agent edits the one file, runs `sync.py --apply`, runs `verify.py`, and reports back. The symlinks do the rest.

**Single file edited:** `shared/blocks/code-style.md`
**Commands:** `sync.py --apply` → `verify.py`
**Manual propagation:** none — symlinks are live

---

### Adding new cross-harness functionality (e.g., connecting to llm-wiki)

This involves two artifacts: a skill (procedural instructions for the LLM) and an activation block (a short note in each harness's global instructions telling it the skill exists).

1. Write `shared/skills/wiki-ops/SKILL.md` — the canonical skill definition, with `name` and `description` frontmatter.
2. Write `shared/blocks/llm-wiki.md` — a short block explaining how to invoke wiki-ops (the activation hint embedded in every harness's global instructions).
3. Add the skill name to the registry's `skills` list, then run `python tools/bootstrap.py --skill wiki-ops` — symlinks the skill into every harness's skill directory.
4. Add `<!-- block: llm-wiki -->` fences in the appropriate section of each harness instruction file, then run `python tools/sync.py --apply` to populate them.
5. Run `python tools/verify.py` — confirms all three harnesses have the identical activation block.

An agent can own steps 3–5 entirely: *"Wire up the wiki-ops skill across all harnesses and verify congruence."* The agent registers the skill, adds the fences, syncs, and verifies. You only authored the skill and the block.

**Files authored:** `shared/skills/wiki-ops/SKILL.md`, `shared/blocks/llm-wiki.md`
**Commands:** `bootstrap.py --skill` → `sync.py --apply` → `verify.py`
**Manual propagation:** none

---

### Adding a new prompt template / persona (e.g., a new "scientist" agent)

1. Write `shared/agents/scientist.md` with YAML frontmatter (`name` and `description` fields). The body follows — harness-agnostic prose, no harness-specific frontmatter.
2. Run `python tools/sync.py --agents --apply` — renders:
   - `harnesses/pi/agents/scientist.md` (pi frontmatter: `description` only)
   - `harnesses/copilot/agents/scientist.agent.md` (Copilot frontmatter: `description`, `name`, `model`, `tools`)
   - `harnesses/claude-code/agents/scientist.md` (Claude Code subagent frontmatter: `name`, `description`, `tools` as a comma-separated string)
3. Run `python tools/verify.py` — confirms rendered bodies match the canonical source.
4. Commit. The rendered files are in `harnesses/{pi,copilot,claude-code}/agents/`, which each harness reads directly: pi via its `prompts` path, Copilot via `~/.copilot/agents` symlink, Claude Code via `~/.claude/agents` symlink.

**Single file authored:** `shared/agents/scientist.md`
**Commands:** `sync.py --agents --apply` → `verify.py`
**Manual propagation:** none — symlinks are live

---

### Dropping a harness (e.g., a billing or terms change makes a harness untenable)

This is the exact scenario that motivated this repo. When a harness becomes unavailable or undesirable, the goal is to remove it without touching anything shared.

1. Run `python tools/bootstrap.py --remove {harness}` — unlinks every symlink and generated file the registry and extension manifests declare for that harness, then moves `harnesses/{harness}/` to `harnesses/_deprecated/{harness}/` (kept in the repo for reference, not deleted).
2. Delete the harness entry from `tools/harnesses.toml`.
3. Run `python tools/verify.py` — should pass cleanly since the removed harness is no longer checked.
4. Commit.

Shared blocks, skills, and agent bodies are untouched. The remaining harnesses continue operating without interruption. If the harness comes back (billing restored, terms clarified), restore the registry entry, move the directory back, and re-run bootstrap.

**Files changed:** `tools/harnesses.toml`, `harnesses/_deprecated/` (move)
**Commands:** `bootstrap.py --remove` → `verify.py`
**Risk to other harnesses:** none

---

### Setting up a fresh machine

`bootstrap.py` is idempotent — safe to re-run. The sequence on a new machine:

1. Clone the repo: `git clone ... ~/repos/llm-config`
2. Run `python tools/bootstrap.py` — creates all symlinks, wires skills and extensions, reports what needs manual attention.
3. Edit machine-specific values by hand (bootstrap prints a checklist):
   - `shared/models/ollama.json` — update Ollama `baseUrl` to this machine's address
   - Copy `~/.pi/agent/auth.json` from backup or recreate with API keys (never committed)
4. Run `python tools/verify.py` — confirms no drift was introduced during setup.

Machine-specific values are never committed and never synced. The repo is the config; the machine is the runtime. Bootstrap bridges the two.

**Files changed:** machine-local only (auth.json, machine-specific JSON values)
**Commands:** `bootstrap.py` → `verify.py`
**Committed changes:** none

---

### Updating an existing skill (e.g., improving wiki-ops workflows)

Unlike adding a skill, updating one requires no bootstrap step — symlinks already point at the source.

1. Edit `shared/skills/wiki-ops/SKILL.md` directly.
2. The change is live immediately in every harness — each skill directory symlink points at the canonical file.
3. Run `python tools/verify.py` — skills are not block-fenced, so this mainly confirms no instruction file drift was accidentally introduced.
4. Commit.

There is no sync step because the skill directory is symlinked wholesale, not copied or rendered. The canonical file *is* the deployed file.

**Single file edited:** `shared/skills/wiki-ops/SKILL.md`
**Commands:** `verify.py` (optional sanity check)
**Manual propagation:** none — symlinks handle it

---

## Relationship to external skill repos

Skills tightly coupled to a specific project or knowledge domain live in that project's repo, not in `llm-config`. The skill evolves with the thing it knows about — a wiki restructure and its skill update can land in the same commit, in the right repo.

- The canonical `SKILL.md` lives in the source repo (e.g. `~/repos/my-project/.skills/my-skill/`)
- `bootstrap.py` symlinks from the source repo into each harness's skill directory; `shared/skills/` always takes precedence when both define the same skill name
- Editing the skill in the source repo propagates to all harnesses automatically via those symlinks

**Decision rule:** a skill travels with the thing it knows about. If a skill is tightly coupled to a specific project or data domain, it stays in that project's repo. If it becomes general-purpose and useful regardless of domain context, it graduates to `shared/skills/` in `llm-config` directly.

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
   mkdir -p shared/blocks shared/agents shared/skills shared/extensions shared/models
   mkdir -p harnesses/harness-a harnesses/harness-b
   mkdir -p tools
   ```

3. **Install Python dependencies:**
   ```bash
   pip install pyyaml rich pre-commit
   ```
   `pyyaml` is required by `sync.py`; `rich` by `report.py`; `pre-commit` for the verify hook.

4. **Write shared blocks** — create `shared/blocks/*.md` files, one per universal instruction topic (code style, guardrails, tool routing, etc.). These are plain prose — no fencing required in the canonical files.

5. **Write the harness registry** — create `tools/harnesses.toml` with one entry per harness (instruction file, symlinks, generated files, skill directory, agent frontmatter rules) and a loader module `tools/registry.py`, as described in [Harness registry](#harness-registry--one-declaration-of-topology).

6. **Create harness instruction files** — for each harness, create its instruction file (e.g. `harnesses/harness-a/instructions.md`) containing the harness-specific wrapper text plus `<!-- block: name -->` fences wherever shared blocks should appear. Leave the fences empty for now.

7. **Run initial sync:**
   ```bash
   python tools/sync.py --apply   # populates all block fences from shared/blocks/
   python tools/verify.py         # should pass clean
   ```

8. **Write bootstrap.py** — a tool that walks the registry and wires `harnesses/*/` files into their live harness locations (symlinks for path-free files, placeholder rendering for generated ones). Make it idempotent.

9. **Run bootstrap and verify:**
   ```bash
   python tools/bootstrap.py
   python tools/verify.py
   git add -A && git commit -m "init: llm-config"
   ```

10. **Complete manual steps** — extension one-time setup, API keys, machine-specific config values. `bootstrap.py` should print a checklist.

---

## Non-goals

- **No general config file generation from templates.** Harness JSON/YAML files are edited directly and committed as-is. The narrow exception is files containing machine-specific absolute paths: those use placeholder substitution in `bootstrap.py` so the committed source stays path-free. Only markdown instruction blocks and agent bodies are synced across harnesses.
- **No runtime injection.** This is a static file management system. There is no daemon watching for changes.
- **No secrets management.** `auth.json`, API keys, and tokens are excluded from the repo via `.gitignore` and documented in `README.md` as manual steps.
