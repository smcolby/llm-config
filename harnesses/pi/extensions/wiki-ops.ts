// wiki-ops health check — warns when wiki page count diverges from index.md.
// Fires on turn_end; silent when the wiki is in sync or not present.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"

const CHECK_CMD =
  "idx=$(grep -oP 'Pages: \\K[0-9]+' ~/repos/llm-wiki/index.md 2>/dev/null); " +
  "pages=$(find ~/repos/llm-wiki/wiki -name '*.md' 2>/dev/null | wc -l | tr -d ' '); " +
  "[ -n \"$idx\" ] && [ \"$pages\" != \"$idx\" ] && " +
  "printf 'wiki-ops: %s pages on disk but index.md says %s — update index before committing\\n' \"$pages\" \"$idx\" || true"

export default async function (pi: ExtensionAPI) {
  pi.on("turn_end", async () => {
    try {
      const result = await pi.exec("bash", ["-c", CHECK_CMD], { timeout: 3000 })
      if (result.stdout.trim()) console.warn(result.stdout.trim())
    } catch {
      // fail open — never block on a health check
    }
  })
}
