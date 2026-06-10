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

REPO = Path(__file__).parent.parent
SYNC = REPO / "tools/sync.py"
WIRE = REPO / "tools/wire_extensions.py"


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
    sys.exit(result_sync.returncode | result_wire.returncode)


if __name__ == "__main__":
    main()
