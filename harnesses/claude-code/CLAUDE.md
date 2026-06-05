# Global Agent Instructions

## Code Formatting & Style
<!-- block: code-style -->
- Write clean, modular, production-ready code.
- Sentence case for comments and print statements: capitalize the first word and acronyms; do not capitalize common technical terms mid-sentence unless they are proper nouns.
- Do not number sequential steps inside code comment blocks.
- Do not end comments with a period.
- NumPy style docstrings for Python code, unless superceded by repo-specific instructions.
<!-- /block: code-style -->

## Writing Conventions
<!-- block: writing-conventions -->
- Minimize use of em-dashes.
- Never use the "it's not X, it's Y" rhetorical pattern.
<!-- /block: writing-conventions -->

## Git Conventions
<!-- block: git-conventions -->
**Subject line**
- Imperative mood, uppercase start: `Add`, `Fix`, `Wire`, `Migrate`, `Update`, `Rename`
- Concise description of what, with just enough why to disambiguate from similar changes
- Parentheticals for scoping or state: `(placeholder)`, `(reconciling drift)`
- No trailing period

**Body**
- One blank line after subject
- Prose-first for changes that need motivation (bugs, migrations, non-obvious decisions); bullet list when the change spans multiple files/components where enumeration aids scanning
- Focus on why and what changed at a conceptual level — not line-by-line narration of the diff
- File paths mentioned when they disambiguate or when affected files aren't obvious from the subject
- No headers, no numbered steps

**Scope signals**
- No conventional commits prefixes (`feat:`, `docs:`, `chore:`) — bare imperative verb only

**Footer**
- Never include any authorship / coauthorship lines
- No issue references, test results, or self-referential summaries
<!-- /block: git-conventions -->

## Execution Guardrails
<!-- block: execution-guardrails -->
- Never write or execute destructive shell commands without verifying target path states.
- Prioritize deterministic code fixes over open-ended architectural rewrites unless explicitly requested.
- Never guess file structures or path availability based on minimized context — query the exact range you need.
- `edit` requires `oldText` to match the file exactly and uniquely. Keep `oldText` as short as possible while still being unique — do not pad with surrounding unchanged lines.
<!-- /block: execution-guardrails -->

## RTK (environment-rtk-optimizer)
<!-- block: rtk -->
**Usage**: Token-optimized CLI proxy (60-90% savings on dev operations)

### Meta commands (always use rtk directly)

```bash
rtk gain              # Show token savings analytics
rtk gain --history    # Show command usage history with savings
rtk discover          # Analyze Claude Code history for missed opportunities
rtk proxy <cmd>       # Execute raw command without filtering (for debugging)
```

### Installation verification

```bash
rtk --version         # Should show: rtk X.Y.Z
rtk gain              # Should work (not "command not found")
which rtk             # Verify correct binary
```

⚠️ **Name collision**: If `rtk gain` fails, you may have reachingforthejack/rtk (Rust Type Kit) installed instead.

### Hook-based usage

All other commands are automatically rewritten by the Claude Code hook.
Example: `git status` → `rtk git status` (transparent, 0 tokens overhead)

- RTK automatically rewrites bash commands to their `rtk` equivalents and compacts tool output (git, build, test, grep, search results). Use commands normally — do not prefix with `rtk`.
- Truncated logs, missing boilerplate passes, and abbreviated file listings are intentional optimizations. Trust compressed outputs as mathematically accurate and complete representations of system state. Do not re-run tool commands or loop variations simply because an output appears brief.
<!-- /block: rtk -->

## Context-Mode Tools — Mandatory Routing
<!-- block: context-mode -->
`ctx_*` tools are MCP wrappers for context-mode's FTS5 knowledge base and sandboxed execution. They are auto-installed and fully functional.

### Think in Code — mandatory

Analyze/count/filter/compare/search/parse/transform data: write code via `ctx_execute(language, code)`, `console.log()` only the answer. Do NOT read raw data into context. Program the analysis — do not compute it by reading raw output. One script replaces ten tool calls.

### Blocked — do not attempt

- **`curl` / `wget`** — intercepted, replaced with error. Use `ctx_fetch_and_index(url, source)` instead.
- **Inline HTTP** (`fetch('http...`)`, `requests.get(`, etc.) in bash — intercepted. Use `ctx_execute(language, code)` so only stdout enters context.
- **WebFetch for analysis** — use `ctx_fetch_and_index(url, source)` then `ctx_search(queries)`; raw HTML never enters context.

### Tool selection hierarchy

| Priority | Need | Tool |
|----------|------|------|
| 0 | Resume / check prior context | `ctx_search(sort: "timeline")` — search BEFORE asking the user |
| 1 | Gather + query in one shot | `ctx_batch_execute(commands, queries)` |
| 2 | Follow-up questions on indexed content | `ctx_search(queries: ["q1", "q2", ...])` — batch all questions in one call |
| 3 | Derive answer from data | `ctx_execute(language, code)` or `ctx_execute_file(path, language, code)` |
| 4 | Fetch web content | `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` |
| 5 | Store for later search | `ctx_index(content, source)` |

Bash is correct for: `git`, `mkdir`, `rm`, `mv`, `cd`, `npm install`, `pip install`, and short commands whose full output you intend to read verbatim. Everything else routes through `ctx_*`.

`read` is a native environment tool (not bash, not `cat`) for reading files you intend to edit.

Reading to **edit** → `read`. Reading to **analyze or summarize** → `ctx_execute_file(path, language, code)`.

### Parallel I/O

For 3+ network commands or URLs, always set `concurrency: N` (4–8 for I/O-bound, 1 for CPU-bound or shared-state):
- `ctx_batch_execute(commands: [...], concurrency: 5)`
- `ctx_fetch_and_index(requests: [{url, source}, ...], concurrency: 5)`

GitHub API: cap at `concurrency: 4` for `gh` calls.

### Tool errors — retry before abandoning

If a tool call returns a validation or format error:
1. Read the error message
2. Fix the syntax and retry once with corrected parameters
3. Only escalate to the user if the retry also fails

Never fall back to generating content from training data when a tool is available but errored. A hallucinated answer is strictly worse than a failed tool call.

If a tool fails after one retry, tell the user what failed and what you were trying to do — do not silently fall back to generating unverified content.

### Memory — search before asking

Session history is persistent and searchable. On resume, search first:

| Need | Command |
|------|---------|
| What were we working on? | `ctx_search(queries: ["summary"], source: "compaction", sort: "timeline")` |
| What was the first request? | `ctx_search(queries: ["prompt"], source: "user-prompt", sort: "timeline")` |
| What did we decide? | `ctx_search(queries: ["decision"], source: "decision", sort: "timeline")` |
| What not to repeat? | `ctx_search(queries: ["rejected"], source: "rejected-approach")` |

Do NOT ask "what were we working on?" — search first. If search returns 0 results, proceed as a fresh session.

### ctx commands

| Command | Action |
|---------|--------|
| `ctx stats` | Call `ctx_stats` MCP tool, display full output verbatim |
| `ctx doctor` | Call `ctx_doctor` MCP tool, run returned shell command, display as checklist |
| `ctx upgrade` | Call `ctx_upgrade` MCP tool, run returned shell command, display as checklist |
| `ctx purge` | Call `ctx_purge(confirm: true)` — warn before wiping knowledge base |

After `/clear` or `/compact`: knowledge base and session stats are preserved. Use `ctx purge` to start fresh.
<!-- /block: context-mode -->

## LLM Wiki
<!-- block: llm-wiki -->
A `wiki-ops` skill is globally installed for LLM-maintained personal wikis.
Wiki repos live at `~/repos/llm-wiki/` (or any directory whose `AGENTS.md`
references this pattern).

The skill source of truth is `~/repos/llm-config/shared/skills/wiki-ops/SKILL.md`.
Edit the skill there; `bootstrap.sh` symlinks propagate changes to all harnesses automatically.
<!-- /block: llm-wiki -->

The full wiki-ops skill is loaded via:
@/Users/smcolby/repos/llm-config/shared/skills/wiki-ops/SKILL.md
