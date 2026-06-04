A `wiki-ops` skill is globally installed for LLM-maintained personal wikis.
Wiki repos live at `~/repos/llm-wiki/` (or any directory whose `AGENTS.md`
references this pattern).

The skill source of truth is `~/repos/llm-config/shared/skills/wiki-ops/SKILL.md`.
Edit the skill there; `bootstrap.sh` symlinks propagate changes to all harnesses automatically.
