// wiki-ops health check — warns when wiki page count diverges from index.md.
// Fires on turn_end; silent when the wiki is in sync or not present.
// Delegates to tools/health-check.sh in the wiki repo (single source of logic).

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"

export default async function (pi: ExtensionAPI) {
  pi.on("turn_end", async () => {
    try {
      const result = await pi.exec(
        "bash",
        ["-c", "~/repos/llm-wiki/tools/health-check.sh"],
        { timeout: 3000 }
      )
      if (result.stdout.trim()) console.warn(result.stdout.trim())
    } catch {
      // fail open — never block on a health check
    }
  })
}
