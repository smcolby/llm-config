#!/usr/bin/env bash
# bootstrap.sh — restore Pi config on a fresh machine
# Usage: clone this repo, then run ./bootstrap.sh

set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
PI="$HOME/.pi/agent"

echo "Pi config bootstrap — repo: $REPO"
echo ""

# Create skills directory if it doesn't exist
mkdir -p "$PI/skills"

# Symlink config files
echo "Linking config files..."
ln -sf "$REPO/agent/AGENTS.md"     "$PI/AGENTS.md"
ln -sf "$REPO/agent/settings.json" "$PI/settings.json"
ln -sf "$REPO/agent/models.json"   "$PI/models.json"

# Symlink skills — add one ln -sf line per skill
echo "Linking skills..."
ln -sf "$REPO/shared/skills/wiki-ops" "$PI/skills/wiki-ops"
echo "  wiki-ops → $REPO/shared/skills/wiki-ops"

echo ""
echo "Done. Manual steps still required:"
echo "  1. Create ~/.pi/agent/auth.json with your API keys (never committed)"
echo "  2. Update agent/settings.json: 'prompts' paths are machine-specific"
echo "  3. Update agent/models.json: 'baseUrl' for Ollama is machine-specific"
echo "     (current: http://loki.local:11434 — update to your local address)"
