#!/usr/bin/env python3
r"""render_rules.py — render canonical rules into harness-native scoped-rule formats.

Formats:
  mdc      Cursor project rules (.cursor/rules/<name>.mdc)
  copilot  Copilot path-scoped instructions (.github/instructions/<name>.instructions.md)

These formats are only meaningful for harnesses that support native glob-scoped
rule activation: Cursor (mdc) and Copilot CLI (copilot). Claude Code and pi do
not auto-load repo-local rule files; for those harnesses the global `rules`
skill handles activation by description match, and repo-seed appends a rules
hint to AGENTS.md instead.

Rendered copies carry a provenance stamp (canonical path @ catalog commit) so
the repo-seed skill can detect drift between a seeded repository and the
catalog. This module is also the rendering point for any future harness that
declares native scoped-rule support in the registry.

Usage:
  python tools/render_rules.py --format mdc --out /path/to/repo/.cursor/rules \\
      shared/rules/lang/python/*.md
  python tools/render_rules.py --format copilot --list   # preview filenames only
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import registry  # noqa: E402
import sync  # noqa: E402

FORMATS = ("mdc", "copilot")


def provenance(rule_path: Path) -> str:
    """Return the provenance stamp for a canonical rule: repo path @ short commit."""
    rel = rule_path.resolve().relative_to(registry.REPO)
    result = subprocess.run(
        ["git", "-C", str(registry.REPO), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    head = result.stdout.strip() or "unknown"
    return f"{rel} @ {head}"


def render(rule_path: Path, fmt: str) -> tuple[str, str]:
    """Render one canonical rule. Returns (filename, content)."""
    import yaml

    if fmt not in FORMATS:
        raise ValueError(f"unknown format '{fmt}' (expected one of {FORMATS})")

    text = rule_path.read_text()
    m = sync.FM_RE.match(text)
    if not m:
        raise ValueError(f"{rule_path}: missing frontmatter")
    fm = yaml.safe_load(m.group(1))
    body = text[m.end() :].lstrip("\n")

    name = fm["name"]
    description = " ".join(fm["description"].split())
    globs = ", ".join(fm.get("scope", []))

    if fmt == "mdc":
        frontmatter = {
            "description": description,
            "globs": globs,
            "alwaysApply": fm.get("tier") == "always",
            "provenance": provenance(rule_path),
        }
        filename = f"{name}.mdc"
    else:
        frontmatter = {
            "description": description,
            "applyTo": globs or "**",
            "provenance": provenance(rule_path),
        }
        filename = f"{name}.instructions.md"

    fm_yaml = yaml.safe_dump(
        frontmatter, sort_keys=False, default_flow_style=False, width=10**9
    ).rstrip("\n")
    return filename, f"---\n{fm_yaml}\n---\n\n{body}"


def main():
    """Render the selected rules to the chosen format and output target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rules", nargs="*", help="rule files (default: all canonical rules)")
    parser.add_argument("--format", required=True, choices=FORMATS)
    parser.add_argument("--out", help="output directory (omit to print to stdout)")
    parser.add_argument("--list", action="store_true", help="print target filenames only")
    args = parser.parse_args()

    paths = (
        [Path(p) for p in args.rules]
        if args.rules
        else sorted((registry.REPO / "shared/rules").rglob("*.md"))
    )

    for path in paths:
        filename, content = render(path, args.format)
        if args.list:
            print(filename)
        elif args.out:
            out_path = Path(args.out) / filename
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content)
            print(f"  RENDER {out_path}")
        else:
            print(content)


if __name__ == "__main__":
    main()
