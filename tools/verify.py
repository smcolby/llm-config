#!/usr/bin/env python3
"""verify.py — assert cross-harness congruence. Exits non-zero on drift.

Checks blocks + agent bodies + manifest-derived files by default.

Usage:
  python tools/verify.py                  # check all harnesses
  python tools/verify.py --harness pi     # check one harness
  python tools/verify.py --agents         # check agent bodies only

Add to .git/hooks/pre-commit:
  #!/bin/sh
  python tools/verify.py
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import registry  # noqa: E402

REPO = Path(__file__).parent.parent
SYNC = REPO / "tools/sync.py"
WIRE = REPO / "tools/wire_extensions.py"


def check_doctrine_budget() -> int:
    """Check total doctrine size against the registry ceiling. Returns 0 or 1."""
    ceiling = registry.load().get("doctrine_token_ceiling")
    if not ceiling:
        return 0
    # chars/4 is a coarse but stable token approximation
    total = sum(len(p.read_text()) for p in (REPO / "shared/blocks").glob("*.md")) // 4
    print(f"Doctrine budget: ~{total} tokens (ceiling {ceiling})")
    if total <= ceiling:
        return 0
    print(
        f"  OVER BUDGET by ~{total - ceiling} tokens — demote or remove doctrine"
        " content before adding more (see patterns/agentic-infrastructure-pattern.md)",
        file=sys.stderr,
    )
    return 1


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", help="limit to one harness")
    parser.add_argument("--agents", action="store_true", help="check agent bodies only")
    args = parser.parse_args()

    cmd = [sys.executable, str(SYNC)]
    if args.harness:
        cmd += ["--harness", args.harness]
    cmd += ["--agents"] if args.agents else ["--all"]

    result_sync = subprocess.run(cmd)
    result_wire = subprocess.run([sys.executable, str(WIRE), "--check"])
    budget = check_doctrine_budget()
    sys.exit(result_sync.returncode | result_wire.returncode | budget)


if __name__ == "__main__":
    main()
