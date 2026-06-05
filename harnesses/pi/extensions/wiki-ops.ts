// AUTO-GENERATED from shared/extensions/wiki-ops.toml — do not edit directly
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"

export default async function (pi: ExtensionAPI) {
  pi.on("turn_end", async () => {
    try {
      const result = await pi.exec("bash", ["-c", "~/repos/llm-wiki/tools/health-check.sh"], { timeout: 5000 })
      if (result.stdout.trim()) console.warn(result.stdout.trim())
    } catch { /* fail open */ }
  })
}
