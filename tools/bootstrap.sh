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
		unlink "$HOME_DIR/.pi/agent/claude-bridge.json" 2>/dev/null || true
		unlink "$HOME_DIR/.pi/agent/skills/wiki-ops" 2>/dev/null || true
		;;
	claude-code)
		unlink "$HOME_DIR/.claude/CLAUDE.md" 2>/dev/null || true
		unlink "$HOME_DIR/.claude/RTK.md" 2>/dev/null || true
		unlink "$HOME_DIR/.claude/settings.json" 2>/dev/null || true
		;;
	copilot)
		unlink "$HOME_DIR/.github/copilot-instructions.md" 2>/dev/null || true
		unlink "$HOME_DIR/.github/hooks/rtk-rewrite.json" 2>/dev/null || true
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

check_mcp() {
	local harness="$1" config_path="$2"
	if [ -f "$config_path" ]; then
		if grep -q "context-mode" "$config_path" 2>/dev/null; then
			echo "  ok   context-mode registered in $harness MCP config"
		else
			echo "  WARN context-mode NOT registered in $harness MCP config ($config_path)"
		fi
	else
		echo "  WARN $harness MCP config not found ($config_path)"
	fi
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
	link "$REPO/harnesses/pi/claude-bridge.json" "$HOME_DIR/.pi/agent/claude-bridge.json"
	wire_skill "wiki-ops"
else
	echo "  SKIP pi — ~/.pi/agent not found"
fi
echo ""

# ── claude code harness ───────────────────────────────────────────────────────

if [ -d "$HOME_DIR/.claude" ]; then
	echo "Wiring claude-code..."
	link "$REPO/harnesses/claude-code/CLAUDE.md" "$HOME_DIR/.claude/CLAUDE.md"
	link "$REPO/harnesses/claude-code/RTK.md" "$HOME_DIR/.claude/RTK.md"
	link "$REPO/harnesses/claude-code/settings.json" "$HOME_DIR/.claude/settings.json"
else
	echo "  SKIP claude-code — ~/.claude not found"
fi
echo ""

# ── copilot harness ───────────────────────────────────────────────────────────

echo "Wiring copilot..."
mkdir -p "$HOME_DIR/.github/hooks" "$HOME_DIR/.copilot/skills"
link "$REPO/harnesses/copilot/copilot-instructions.md" "$HOME_DIR/.github/copilot-instructions.md"
link "$REPO/harnesses/copilot/hooks/rtk-rewrite.json" "$HOME_DIR/.github/hooks/rtk-rewrite.json"
link "$REPO/harnesses/copilot/agents" "$HOME_DIR/.copilot/agents"
wire_skill "wiki-ops" # no-op if already done for pi (idempotent)
echo ""

# ── MCP registration checks ───────────────────────────────────────────────────

echo "Checking MCP registrations..."
check_mcp "claude-code" "$HOME_DIR/.claude.json"
check_mcp "copilot" "$HOME_DIR/.copilot/mcp-config.json"
echo ""

# ── manual steps checklist ────────────────────────────────────────────────────

echo "=== Manual steps required ==="
echo "  1. Edit harnesses/pi/models.json — update Ollama baseUrl to this machine's address"
echo "  2. Edit harnesses/pi/settings.json — update 'prompts' absolute path if needed"
echo "  3. Register context-mode in ~/.claude.json (claude-code MCP)"
echo "  4. Register context-mode in ~/.copilot/mcp-config.json (copilot MCP)"
echo "  5. Create ~/.pi/agent/auth.json with API keys (never committed)"
echo ""
echo "Run 'python tools/verify.py' to confirm congruence."
