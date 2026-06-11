When entering a repository, look for repository-level instruction files and treat
them as authoritative for work in that repo, regardless of which harness you are:

  - `AGENTS.md` at repo root
  - `CLAUDE.md` at repo root
  - `.github/copilot-instructions.md`

If multiple are present, read all of them. If they conflict with each other, prefer
the file written for the active harness; otherwise treat them as additive.

Repository-level instructions override global instructions where they conflict.
Global rules continue to apply unless the repo file explicitly relaxes them.

When editing repository instructions, edit the canonical file (`AGENTS.md` when
present, else the repo's existing instruction file) and keep harness-branded
duplicates as pointers to it; never fork content across them.

Instruction files also appear in subdirectories. When working under a directory
that has one, read it; deeper files take precedence over shallower ones for
their subtree.

Also honor scoped rule files committed in the repo (e.g. `.cursor/rules/`,
`.github/instructions/`, `.claude/rules/`), regardless of which harness you
are: before touching files a rule's scope matches, read that rule.
