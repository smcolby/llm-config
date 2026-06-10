When entering a repository, look for repository-level instruction files and treat
them as authoritative for work in that repo, regardless of which harness you are:

  - `AGENTS.md` at repo root
  - `CLAUDE.md` at repo root
  - `.github/copilot-instructions.md`

If multiple are present, read all of them. If they conflict with each other, prefer
the file written for the active harness; otherwise treat them as additive.

Repository-level instructions override global instructions where they conflict.
Global rules continue to apply unless the repo file explicitly relaxes them.
