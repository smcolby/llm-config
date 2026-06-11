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

**Commit scope**
- One logical change per commit; never batch unrelated changes
- Never push, amend published commits, or force-push without explicit instruction

**Scope signals**
- No conventional commits prefixes (`feat:`, `docs:`, `chore:`) — bare imperative verb only

**Footer**
- Never include any authorship / coauthorship lines
- No issue references, test results, or self-referential summaries
