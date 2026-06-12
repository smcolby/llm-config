#!/usr/bin/env python3
r"""render_rules.py — render canonical rules into harness-native scoped-rule formats.

Formats:
  mdc      Cursor project rules (.cursor/rules/<name>.mdc)
  copilot  Copilot path-scoped instructions (.github/instructions/<name>.instructions.md)
  claude   Claude Code path-scoped rules (.claude/rules/<name>.md, also valid
           at the user level under ~/.claude/rules/)

These formats are only meaningful for harnesses that support native glob-scoped
rule activation: Cursor (mdc), Copilot CLI (copilot), and Claude Code (claude).
Claude Code activates `paths`-scoped rules at both the user level (the catalog
wires harnesses/claude-code/rules/ to ~/.claude/rules/ via sync.py and the
registry) and the repo level (deployed by repo-seed). pi has no scoped-rule
mechanism; there the global `rules` skill handles activation by description
match, and repo-seed appends a rules hint to AGENTS.md instead.

Claude Code has no description-based activation for rules: a rule without
`paths` is always-on. Rendering to the claude format therefore skips
`requested` and `invoked` tier rules (they activate through the `rules`
skill); `scoped` renders with `paths` and `always` renders unconditional.

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

FORMATS = ("mdc", "copilot", "claude")


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


def render(
    rule_path: Path,
    fmt: str,
    include_provenance: bool = True,
    include_requested: bool = False,
) -> tuple[str, str] | None:
    """Render one canonical rule to (filename, content).

    Returns None when the rule's tier has no representation in the target
    format. Provenance is included for repo-deployed copies (reseed diffs against the
    stamped commit) and omitted for catalog-committed renders, where the stamp
    would churn on every commit and git already tracks drift.

    include_requested opens the claude target for `requested`-tier rules at
    repo-local deployment time. Globally those rules must route through the
    rules skill because Claude Code unscoped rules are always-on, but a
    repo-local copy whose scope field is honored as `paths` activates the
    same way Cursor or Copilot would scope it. Rules without scope render
    unscoped (always-on for that repo) since their activation is genuinely
    universal within the deploying repo's bounds.
    """
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
        }
        filename = f"{name}.mdc"
    elif fmt == "copilot":
        frontmatter = {
            "description": description,
            "applyTo": globs or "**",
        }
        filename = f"{name}.instructions.md"
    else:
        # claude rules have no description activation: an unscoped rule is
        # always-on, so requested/invoked tiers stay with the rules skill
        # unless include_requested opts the call in to repo-local deployment
        tier = fm.get("tier")
        if tier not in ("scoped", "always") and not (include_requested and tier == "requested"):
            return None
        frontmatter = {"description": description}
        if tier == "scoped" or (include_requested and tier == "requested" and fm.get("scope")):
            frontmatter["paths"] = fm["scope"]
        filename = f"{name}.md"

    if include_provenance:
        frontmatter["provenance"] = provenance(rule_path)

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
    parser.add_argument(
        "--include-requested",
        action="store_true",
        help="render requested-tier rules (repo-local deployment); scope becomes paths",
    )
    args = parser.parse_args()

    paths = (
        [Path(p) for p in args.rules]
        if args.rules
        else sorted((registry.REPO / "shared/rules").rglob("*.md"))
    )

    for path in paths:
        rendered = render(path, args.format, include_requested=args.include_requested)
        if rendered is None:
            print(f"  SKIP   {path.name}: tier has no {args.format} representation")
            continue
        filename, content = rendered
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
