**Usage**: Token-optimized CLI proxy (60-90% savings on dev operations)

### Meta commands (always use rtk directly)

```bash
rtk gain              # Show token savings analytics
rtk gain --history    # Show command usage history with savings
rtk discover          # Analyze command history for missed opportunities
rtk proxy <cmd>       # Execute raw command without filtering (for debugging)
```

### Hook-based usage

All other commands are automatically rewritten by the harness hook.
Example: `git status` → `rtk git status` (transparent, 0 tokens overhead)

- RTK automatically rewrites bash commands to their `rtk` equivalents and compacts tool output (git, build, test, grep, search results). Use commands normally — do not prefix with `rtk`.
- Truncated logs, missing boilerplate passes, and abbreviated file listings are intentional optimizations. Trust compressed outputs as mathematically accurate and complete representations of system state. Do not re-run tool commands or loop variations simply because an output appears brief.
