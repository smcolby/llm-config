# Global Agent Instructions

## Code Formatting & Style
<!-- block: code-style -->
- Sentence case for comments and print statements: capitalize the first word and acronyms; do not capitalize common technical terms mid-sentence unless they are proper nouns.
- Do not number sequential steps inside code comment blocks.
- Do not end comments with a period.
<!-- /block: code-style -->

## Writing Conventions
<!-- block: writing-conventions -->
- Never use em-dashes, en-dashes, or sequential hyphens to interrupt sentences, offset side-thoughts, or join clauses; use commas, parentheses, colons, semicolons, or separate sentences instead. Single hyphens remain correct for compound words ("well-known"), prefixes ("pre-empt"), and numeric ranges.
- Never use the rhetorical pattern "It's not [X], it's [Y]" to explain a concept; define the subject directly and concretely.
- No conversational filler or throat-clearing ("Sure, here is the code," "It is important to note that"); start with the substance of the answer.
- No unprompted concluding summaries ("Ultimately," "In conclusion," "In summary"); stop once the core answer is complete.
- Banned vocabulary: delve, tapestry, beacon, testament, symphony, pivotal, landscape, and similar overused AI words.
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
- Edit-tool replacements must match the file exactly and uniquely. Keep the match snippet as short as possible while still being unique; do not pad with surrounding unchanged lines.
- When you correct the same agent mistake twice, propose capturing it as a directive in the coding-rules catalog.
<!-- /block: execution-guardrails -->

## Repository Instructions
<!-- block: repo-instructions -->
When entering a repository, look for repository-level instruction files and treat
them as authoritative for work in that repo, regardless of which harness you are:

  - `AGENTS.md` at repo root
  - `CLAUDE.md` at repo root
  - `.github/copilot-instructions.md`

If multiple are present, read all of them. If they conflict with each other, prefer
the file written for the active harness; otherwise treat them as additive.

Repository-level instructions override global instructions where they conflict.
Global rules continue to apply unless the repo file explicitly relaxes them.

Also honor scoped rule files committed in the repo (e.g. `.cursor/rules/`,
`.github/instructions/`), regardless of which harness you are: before touching
files a rule's scope matches, read that rule.
<!-- /block: repo-instructions -->

## RTK (environment-rtk-optimizer)
<!-- block: rtk -->
**Usage**: Token-optimized CLI proxy (60-90% savings on dev operations)

### Meta commands (always use rtk directly)

```bash
rtk gain              # Show token savings analytics
rtk gain --history    # Show command usage history with savings
rtk discover          # Analyze command history for missed opportunities
rtk proxy <cmd>       # Execute raw command without filtering (for debugging)
```

### Hook-based usage

All other commands are automatically rewritten by the harness hook.
Example: `git status` → `rtk git status` (transparent, 0 tokens overhead)

- RTK automatically rewrites bash commands to their `rtk` equivalents and compacts tool output (git, build, test, grep, search results). Use commands normally — do not prefix with `rtk`.
- Truncated logs, missing boilerplate passes, and abbreviated file listings are intentional optimizations. Trust compressed outputs as mathematically accurate and complete representations of system state. Do not re-run tool commands or loop variations simply because an output appears brief.
<!-- /block: rtk -->

## Context-Mode Tools — Mandatory Routing
<!-- block: context-mode -->
`ctx_*` tools are MCP wrappers for context-mode's FTS5 knowledge base and sandboxed execution. If `ctx_*` tools are not available in the current session, fall back to native tools (read, grep, web fetch); do not fail the task hunting for them.

### Think in Code — mandatory

Analyze/count/filter/compare/search/parse/transform data: write code via `ctx_execute(language, code)`, `console.log()` only the answer. Do NOT read raw data into context — program the analysis; one script replaces ten tool calls.

### Blocked — do not attempt

- **`curl` / `wget`** — intercepted. Use `ctx_fetch_and_index(url, source)` instead.
- **Inline HTTP** (`fetch('http...`, `requests.get(`, etc.) in bash — intercepted. Use `ctx_execute(language, code)` so only stdout enters context.
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

Bash remains correct for `git`, `mkdir`, `rm`, `mv`, `cd`, package installs, and short commands whose full output you intend to read verbatim. Reading to **edit** → `read` (native tool); reading to **analyze or summarize** → `ctx_execute_file(path, language, code)`.

For 3+ network commands or URLs, set `concurrency: 4-8` for I/O-bound work (1 for CPU-bound or shared state; cap `gh` API calls at 4).

Session history is persistent and survives /clear and /compact: on resume, `ctx_search` for prior context (compaction summaries, decisions, rejected approaches) before asking the user what you were working on. If a ctx call errors, fix the syntax and retry once before escalating; never substitute generated content for a failed lookup.
<!-- /block: context-mode -->

## Coding Rules
<!-- block: rules -->
A scoped coding-rules catalog is installed as the `rules` skill. Before creating or modifying source files, consult its index, which maps file patterns to rules (Python core, testing, docs, packaging, security), and read the matching rules. Directives marked as tool-enforced are gates: fix the code rather than fighting the linter.
<!-- /block: rules -->

## LLM Wiki
<!-- block: llm-wiki -->
A `wiki-ops` skill is globally installed for LLM-maintained personal wikis.
Wiki repos live at `~/repos/llm-wiki/` (or any directory whose `AGENTS.md`
references this pattern). Invoke the skill for ingest, query, or lint work.
<!-- /block: llm-wiki -->

wiki-ops is installed as a native skill (`~/.claude/skills/wiki-ops`); invoke it via the Skill tool when wiki work comes up.
