# pi-config

Version-controlled Pi agent configuration. Symlinked into `~/.pi/agent/` so
edits here take effect immediately.

## What's tracked

| File | Purpose |
|------|---------|
| `agent/AGENTS.md` | Global Pi instructions (style, guardrails, tool routing) |
| `agent/settings.json` | Default model, packages, prompt paths |
| `agent/models.json` | Custom model/provider definitions |
| `bootstrap.sh` | Restore symlinks on a fresh machine |

## What's not tracked

| Path | Reason |
|------|--------|
| `~/.pi/agent/auth.json` | API keys — never commit |
| `~/.pi/agent/npm/` | Installed packages, like node_modules |
| `~/.pi/agent/bin/` | Compiled binaries, reinstalled by Pi |
| `~/.pi/agent/sessions/` | Ephemeral session data |

## Machine-specific values to update after bootstrap

- `agent/settings.json` → `prompts`: absolute local paths to prompt files — update to match the new machine's directory layout
- `agent/models.json` → `baseUrl`: Ollama host address — update from `http://loki.local:11434` to the new machine's local address

## Skills

Skills with their own repos are symlinked, not stored here. The bootstrap
script recreates the symlinks. Currently tracked skills:

| Skill | Source repo |
|-------|-------------|
| `wiki-ops` | `~/repos/llm-wiki/.pi/skills/wiki-ops/` |

## Fresh machine setup

```bash
git clone git@github.com:smcolby/pi-config.git ~/repos/pi-config
# also clone any skill repos first (e.g. llm-wiki)
cd ~/repos/pi-config && ./bootstrap.sh
```
