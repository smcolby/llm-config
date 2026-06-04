#!/usr/bin/env python3
"""wire_extensions.py — create extension symlinks defined in shared/extensions/*.toml.

Called by bootstrap.sh. Reads all extension manifests, creates any file-based
wiring (symlinks), and prints a one-time manual setup checklist for steps that
cannot be automated.
"""

import os
import tomllib
from pathlib import Path

REPO = Path(__file__).parent.parent
HOME = Path.home()
EXTENSIONS_DIR = REPO / "shared/extensions"


def expand(p: str) -> Path:
    return Path(p.replace("~", str(HOME)))


def link(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() and os.readlink(dst) == str(src):
        print(f"  ok   {dst}")
    else:
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        dst.symlink_to(src)
        print(f"  link {dst} → {src}")


def main():
    if not EXTENSIONS_DIR.exists():
        return

    manual_steps: list[str] = []

    for ext_file in sorted(EXTENSIONS_DIR.glob("*.toml")):
        with open(ext_file, "rb") as f:
            ext = tomllib.load(f)

        name = ext["name"]
        print(f"  {name}")

        for harness, hconf in ext.get("harnesses", {}).items():
            for pair in hconf.get("symlinks", []):
                link(REPO / pair[0], expand(pair[1]))

            if step := hconf.get("manual_setup"):
                manual_steps.append(f"    [{harness}] {step}")

    if manual_steps:
        print("\nExtension manual setup (one-time per machine):")
        for step in manual_steps:
            print(step)


if __name__ == "__main__":
    main()
