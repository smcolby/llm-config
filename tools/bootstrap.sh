#!/usr/bin/env bash
# bootstrap.sh — wire all llm-config symlinks on a fresh machine.
# Safe to re-run: existing correct symlinks are skipped, broken ones replaced.
# Run from any directory; paths are relative to this script's location.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOME_DIR="$HOME"

link() {
	local src="$1" dst="$2"
	mkdir -p "$(dirname "$dst")"
	if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
		echo "  ok   $dst"
	else
		ln -sf "$src" "$dst"
		echo "  link $dst → $src"
	fi
}

remove_harness() {
	local harness="$1"
	echo "Removing harness: $harness"
	case "$harness" in
	pi)
		unlink "$HOME_DIR/.pi/agent/AGENTS.md" 2>/dev/null || true
		unlink "$HOME_DIR/.pi/agent/settings.json" 2>/dev/null || true
		unlink "$HOME_DIR/.pi/agent/models.json" 2>/dev/null || true
		unlink "$HOME_DIR/.pi/agent/mcp.json" 2>/dev/null || true
		unlink "$HOME_DIR/.pi/agent/extensions/rtk.ts" 2>/dev/null || true
		unlink "$HOME_DIR/.pi/agent/skills/wiki-ops" 2>/dev/null || true
		;;
	claude-code)
		unlink "$HOME_DIR/.claude/CLAUDE.md" 2>/dev/null || true
		unlink "$HOME_DIR/.claude/settings.json" 2>/dev/null || true
		unlink "$HOME_DIR/.claude/skills/llm-wiki" 2>/dev/null || true
		;;
	copilot)
		unlink "$HOME_DIR/.github/copilot-instructions.md" 2>/dev/null || true
		unlink "$HOME_DIR/.copilot/mcp-config.json" 2>/dev/null || true
		unlink "$HOME_DIR/.copilot/skills/wiki-ops" 2>/dev/null || true
		;;
	*)
		echo "Unknown harness: $harness" >&2
		exit 1
		;;
	esac
	mkdir -p "$REPO/harnesses/_deprecated"
	mv "$REPO/harnesses/$harness" "$REPO/harnesses/_deprecated/$harness"
	echo "  archived harnesses/$harness → harnesses/_deprecated/$harness"
	echo "  Done. Remove '$harness' from tools/harness_agent_config.toml then run verify."
}

wire_skill() {
	local skill="$1"
	local skill_src

	# prefer llm-wiki canonical location, fall back to shared/skills/
	if [ -d "$HOME_DIR/repos/llm-wiki/.pi/skills/$skill" ]; then
		skill_src="$HOME_DIR/repos/llm-wiki/.pi/skills/$skill"
	elif [ -d "$REPO/shared/skills/$skill" ]; then
		skill_src="$REPO/shared/skills/$skill"
	else
		echo "  WARN  skill '$skill' not found in llm-wiki or shared/skills/ — skipping" >&2
		return
	fi

	link "$skill_src" "$HOME_DIR/.pi/agent/skills/$skill"
	link "$skill_src" "$HOME_DIR/.copilot/skills/$skill"
	echo "  skill '$skill' wired for pi and copilot"
}

# ── argument handling ──────────────────────────────────────────────────────────

if [ "${1:-}" = "--remove" ]; then
	remove_harness "${2:?Usage: bootstrap.sh --remove <harness>}"
	exit 0
fi

if [ "${1:-}" = "--skill" ]; then
	wire_skill "${2:?Usage: bootstrap.sh --skill <skill-name>}"
	exit 0
fi

echo "=== llm-config bootstrap ==="
echo "Repo: $REPO"
echo ""

# ── pi harness ────────────────────────────────────────────────────────────────

if [ -d "$HOME_DIR/.pi/agent" ]; then
	echo "Wiring pi..."
	link "$REPO/harnesses/pi/AGENTS.md" "$HOME_DIR/.pi/agent/AGENTS.md"
	link "$REPO/harnesses/pi/settings.json" "$HOME_DIR/.pi/agent/settings.json"
	link "$REPO/harnesses/pi/models.json" "$HOME_DIR/.pi/agent/models.json"
	link "$REPO/harnesses/pi/mcp.json" "$HOME_DIR/.pi/agent/mcp.json"
	wire_skill "wiki-ops"
else
	echo "  SKIP pi — ~/.pi/agent not found"
fi
echo ""

# ── claude code harness ───────────────────────────────────────────────────────

if [ -d "$HOME_DIR/.claude" ]; then
	echo "Wiring claude-code..."
	link "$REPO/harnesses/claude-code/CLAUDE.md" "$HOME_DIR/.claude/CLAUDE.md"
	link "$REPO/harnesses/claude-code/settings.json" "$HOME_DIR/.claude/settings.json"
	link "$REPO/harnesses/claude-code/statusline.sh" "$HOME_DIR/.claude/statusline.sh"
	link "$HOME_DIR/repos/llm-wiki" "$HOME_DIR/.claude/skills/llm-wiki"
else
	echo "  SKIP claude-code — ~/.claude not found"
fi
echo ""

# ── copilot harness ───────────────────────────────────────────────────────────

echo "Wiring copilot..."
mkdir -p "$HOME_DIR/.github" "$HOME_DIR/.copilot/skills"
# rtk hook was renamed rtk-rewrite.json → rtk.json; clean up the old symlink if present
unlink "$HOME_DIR/.github/hooks/rtk-rewrite.json" 2>/dev/null || true
link "$REPO/harnesses/copilot/copilot-instructions.md" "$HOME_DIR/.github/copilot-instructions.md"
link "$REPO/harnesses/copilot/mcp-config.json" "$HOME_DIR/.copilot/mcp-config.json"
link "$REPO/harnesses/copilot/agents" "$HOME_DIR/.copilot/agents"
wire_skill "wiki-ops" # no-op if already done for pi (idempotent)
echo ""

# ── extensions ────────────────────────────────────────────────────────────────

echo "Wiring extensions..."
python3 "$REPO/tools/wire_extensions.py"
echo ""

# ── manual steps checklist ────────────────────────────────────────────────────

echo "=== Manual steps required ==="
echo "  1. Edit shared/models/ollama.json — update Ollama baseUrl to this machine's address"
echo "  2. Edit harnesses/pi/settings.json — update 'prompts' absolute path if needed"
echo "  3. Create ~/.pi/agent/auth.json with API keys (never committed)"
echo "  (Extension-specific one-time setup printed above)"
if [ -z "${OLLAMA_HOST:-}" ]; then
	echo "  4. Add 'export OLLAMA_HOST=http://loki.local:11434' to your shell profile so 'ollama launch claude' routes to loki.local"
fi
echo ""
echo "Run 'python tools/verify.py' to confirm congruence."
