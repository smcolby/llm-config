A `wiki-ops` skill is globally installed for LLM-maintained personal wikis.
Wiki repos live at `~/repos/llm-wiki/` (or any directory whose `AGENTS.md`
references this pattern).

The skill source of truth is `~/repos/llm-wiki/.pi/skills/wiki-ops/SKILL.md`,
symlinked into each harness's skill directory by `bootstrap.sh`. Edit the skill
there; the symlinks propagate changes to all harnesses automatically.
