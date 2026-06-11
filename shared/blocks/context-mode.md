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
