#!/usr/bin/env python3
"""sync.py — propagate shared blocks, render agents, and index rules.

Usage:
  python tools/sync.py            # check for drift (dry run)
  python tools/sync.py --apply    # rewrite fenced blocks in harness files
  python tools/sync.py --agents   # check agent body drift
  python tools/sync.py --agents --apply  # render agents from shared/agents/
  python tools/sync.py --rules    # validate rules + check router index + claude rules
  python tools/sync.py --skills   # validate shared skill frontmatter
  python tools/sync.py --all --apply     # blocks + agents + rules + skills
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import registry  # noqa: E402

REPO = registry.REPO
BLOCKS_DIR = REPO / "shared/blocks"
AGENTS_DIR = REPO / "shared/agents"
RULES_DIR = REPO / "shared/rules"
SKILLS_DIR = REPO / "shared/skills"
ROUTER_SKILL = REPO / "shared/skills/rules/SKILL.md"
CLAUDE_RULES_DIR = REPO / "harnesses/claude-code/rules"
HARNESSES_DIR = REPO / "harnesses"

RULE_TIERS = {"always", "scoped", "requested", "invoked"}
RULE_BODY_MAX_LINES = 500
FRONTMATTER_TOKEN_BUDGET = 100
REVIEWED_STALE_MONTHS_DEFAULT = 12

# machine-specific roots; portable forms (~/, $HOME, relative) are fine
ABS_PATH_RE = re.compile(r"(?<![\w@.-])(?:/Users/|/home/|[A-Za-z]:\\)")

HARNESS_INSTRUCTION_FILES = {
    h: REPO / conf["instruction_file"] for h, conf in registry.harnesses().items()
}

FENCE_RE = re.compile(
    r"(<!-- block: (?P<name>[\w-]+) -->\n)"
    r"(?P<content>.*?)"
    r"(<!-- /block: (?P=name) -->)",
    re.DOTALL,
)

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def load_block(name: str) -> str:
    """Return the canonical text of a shared block, with one trailing newline."""
    path = BLOCKS_DIR / f"{name}.md"
    if not path.exists():
        print(f"  ERROR: shared/blocks/{name}.md not found", file=sys.stderr)
        sys.exit(1)
    return path.read_text().rstrip("\n") + "\n"


def check_blocks(apply: bool, harness_filter: str | None = None) -> int:
    """Check, or with apply rewrite, fenced block regions. Return the drift count."""
    drift = 0
    for harness, fpath in HARNESS_INSTRUCTION_FILES.items():
        if harness_filter and harness != harness_filter:
            continue
        if not fpath.exists():
            continue
        text = fpath.read_text()
        new_text = text
        for m in FENCE_RE.finditer(text):
            name = m.group("name")
            canonical = load_block(name)
            actual = m.group("content")
            if actual != canonical:
                drift += 1
                print(f"  DRIFT  {harness}: block '{name}'")
                if apply:
                    new_text = new_text.replace(
                        m.group(0),
                        f"<!-- block: {name} -->\n{canonical}<!-- /block: {name} -->",
                    )
        if apply and new_text != text:
            fpath.write_text(new_text)
            print(f"  FIXED  {harness}: {fpath.name}")
    return drift


def load_frontmatter(raw: str) -> tuple[dict | None, str | None]:
    """Parse a frontmatter YAML block. Returns (data, None) or (None, message).

    The common authoring mistake is an unquoted value containing a colon
    followed by a space, which YAML reads as a nested mapping; the message
    names that cause so the fix is obvious without decoding a raw scanner error.
    """
    import yaml

    try:
        return yaml.safe_load(raw), None
    except yaml.YAMLError as e:
        detail = str(e).replace("\n", " ")
        hint = (
            " (a value containing a colon followed by a space must be quoted,"
            ' e.g. description: "foo: bar")'
        )
        return None, f"invalid YAML frontmatter: {detail}{hint}"


def lint_description(rel, desc: str) -> list[str]:
    """Return description-quality warnings: third person, enough matchable keywords."""
    warnings: list[str] = []
    words = desc.split()
    if words and words[0].lower().rstrip(",.") in {"i", "we", "my", "our", "you", "your"}:
        warnings.append(f"{rel}: description should be third person, stating what and when")
    if len(words) < 8:
        warnings.append(f"{rel}: description too thin to match against tasks (under 8 words)")
    return warnings


def reviewed_months_ago(value) -> int | None:
    """Return whole months since a reviewed: stamp, or None if unparseable."""
    import datetime

    if isinstance(value, datetime.date):
        year, month = value.year, value.month
    else:
        m = re.match(r"^(\d{4})-(\d{2})", str(value))
        if not m:
            return None
        year, month = int(m.group(1)), int(m.group(2))
    today = datetime.date.today()
    return (today.year - year) * 12 + (today.month - month)


def lint_common(
    rel, fm: dict, text: str, description_lints: bool = True
) -> tuple[list[str], list[str]]:
    """Run the authoring-standards lints shared by rules and skills.

    Returns (errors, warnings): hygiene violations are errors, quality
    heuristics and staleness are warnings. description_lints is off for the
    generated router index, whose description enumerates rule names as
    activation keywords and grows with the catalog by design.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if ABS_PATH_RE.search(text):
        errors.append(f"{rel}: machine-specific absolute path; use ~/-style or relative paths")
    if description_lints and fm.get("description"):
        warnings.extend(lint_description(rel, fm["description"]))
        # scope globs are functional precision and exempt; the budget targets prose
        desc_tokens = len(fm["description"]) // 4
        if desc_tokens > FRONTMATTER_TOKEN_BUDGET:
            warnings.append(
                f"{rel}: description ~{desc_tokens} tokens"
                f" (budget {FRONTMATTER_TOKEN_BUDGET}); trim to what matching needs"
            )
    if fm.get("reviewed"):
        stale_after = registry.load().get("reviewed_stale_months", REVIEWED_STALE_MONTHS_DEFAULT)
        age = reviewed_months_ago(fm["reviewed"])
        if age is not None and age > stale_after:
            warnings.append(
                f"{rel}: reviewed {age} months ago (stale after {stale_after}); run catalog-audit"
            )
    return errors, warnings


def parse_shared_agent(path: Path):
    """Parse a shared agent file into (frontmatter, body); exit on malformed input."""
    text = path.read_text()
    m = FM_RE.match(text)
    if not m:
        print(f"  ERROR: no frontmatter in {path}", file=sys.stderr)
        sys.exit(1)
    fm, err = load_frontmatter(m.group(1))
    if err or not isinstance(fm, dict):
        print(f"  ERROR: {path}: {err or 'frontmatter is not a mapping'}", file=sys.stderr)
        sys.exit(1)
    body = text[m.end() :].lstrip("\n")
    return fm, body


def check_agents(apply: bool, harness_filter: str | None = None) -> int:
    """Render, or check, per-harness agent files from shared bodies. Return the drift count."""
    agent_configs = registry.agent_configs()

    drift = 0
    for slug in sorted(AGENTS_DIR.glob("*.md")):
        fm, canonical_body = parse_shared_agent(slug)
        name = slug.stem

        for harness, hconf in agent_configs.items():
            if harness_filter and harness != harness_filter:
                continue
            suffix = hconf["filename_suffix"]
            out_path = HARNESSES_DIR / harness / "agents" / f"{name}{suffix}"

            if apply:
                # build frontmatter as a proper YAML dict, preserving declared field order
                import yaml

                fields = hconf.get("include_fields", ["description"])
                frontmatter: dict = {}
                for field in fields:
                    if field in ("model", "tools"):
                        frontmatter[field] = hconf[field]
                    else:
                        frontmatter[field] = fm[field]
                fm_yaml = yaml.safe_dump(
                    frontmatter, sort_keys=False, default_flow_style=False, width=10**9
                ).rstrip("\n")
                rendered = f"---\n{fm_yaml}\n---\n\n{canonical_body}"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(rendered)
                print(f"  RENDER {harness}: {out_path.name}")
            elif out_path.exists():
                existing = out_path.read_text()
                # extract body (skip frontmatter)
                bm = FM_RE.match(existing)
                existing_body = existing[bm.end() :].lstrip("\n") if bm else existing
                if existing_body.rstrip("\n") != canonical_body.rstrip("\n"):
                    drift += 1
                    print(f"  DRIFT  {harness}/agents/{out_path.name}: body differs from shared")
            else:
                drift += 1
                print(f"  MISSING {harness}/agents/{out_path.name}")

    return drift


def load_rules() -> list[tuple[Path, dict, str]]:
    """Parse and schema-validate all canonical rules. Exits non-zero on errors."""
    rules: list[tuple[Path, dict, str]] = []
    errors: list[str] = []
    warnings: list[str] = []
    seen: dict[str, Path] = {}
    for path in sorted(RULES_DIR.rglob("*.md")):
        rel = path.relative_to(REPO)
        text = path.read_text()
        m = FM_RE.match(text)
        if not m:
            errors.append(f"{rel}: missing frontmatter")
            continue
        fm, err = load_frontmatter(m.group(1))
        if err or not isinstance(fm, dict):
            errors.append(f"{rel}: {err or 'frontmatter is not a mapping'}")
            continue
        body = text[m.end() :].lstrip("\n")
        for field in ("name", "description", "tier", "reviewed"):
            if not fm.get(field):
                errors.append(f"{rel}: missing required field '{field}'")
        tier = fm.get("tier")
        if tier and tier not in RULE_TIERS:
            errors.append(f"{rel}: invalid tier '{tier}' (expected {sorted(RULE_TIERS)})")
        if tier == "scoped" and not fm.get("scope"):
            errors.append(f"{rel}: tier 'scoped' requires a scope glob list")
        for glob in fm.get("scope") or []:
            if not isinstance(glob, str) or not glob.strip():
                errors.append(f"{rel}: scope entries must be non-empty glob strings")
            elif glob.startswith("/") or "\\" in glob:
                errors.append(f"{rel}: scope glob '{glob}' must be relative with forward slashes")
        lint_errors, lint_warnings = lint_common(rel, fm, text)
        errors.extend(lint_errors)
        warnings.extend(lint_warnings)
        name = fm.get("name")
        if name:
            if name in seen:
                other = seen[name].relative_to(REPO)
                errors.append(f"{rel}: duplicate rule name '{name}' (also in {other})")
            seen[name] = path
        if len(body.splitlines()) > RULE_BODY_MAX_LINES:
            errors.append(f"{rel}: body exceeds {RULE_BODY_MAX_LINES} lines")
        rules.append((path, fm, body))
    for w in warnings:
        print(f"  WARN  {w}")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    return rules


def build_router(rules: list[tuple[Path, dict, str]]) -> str:
    """Render the router skill index from rule frontmatter."""
    import yaml

    names = ", ".join(fm["name"] for _, fm, _ in rules)
    frontmatter = {
        "name": "rules",
        "description": (
            "Scoped coding rules catalog. Consult before creating or modifying "
            "source files; the index maps file patterns to rules. Covers: "
            f"{names}."
        ),
    }
    fm_yaml = yaml.safe_dump(
        frontmatter, sort_keys=False, default_flow_style=False, width=10**9
    ).rstrip("\n")

    rows = []
    for path, fm, _ in rules:
        rel = path.relative_to(RULES_DIR)
        scope = ", ".join(f"`{g}`" for g in fm.get("scope", [])) or "(any)"
        desc = " ".join(fm["description"].split())
        rows.append(f"| {fm['name']} | {fm['tier']} | {scope} | `rules/{rel}` | {desc} |")
    table = "\n".join(rows)

    return f"""---
{fm_yaml}
---

<!-- generated by tools/sync.py from shared/rules/ — edit the rules, not this file -->

# Coding Rules Index

Before creating or modifying files that match a rule's scope, read the rule
file (paths are relative to this skill directory). Rules with tier
`requested` activate when the task matches their description rather than by
file pattern. Each rule states principles, concrete directives, and banned
patterns with correct replacements; directives marked as enforced by tooling
are gates, so fix the code rather than fighting them.

| Rule | Tier | Applies to | Rule file | When to read |
|---|---|---|---|---|
{table}
"""


def build_claude_rules(rules: list[tuple[Path, dict, str]]) -> dict[str, str]:
    """Render the committed Claude Code rules directory from canonical rules.

    Claude Code activates these globally through the ~/.claude/rules symlink;
    rules whose tier has no claude representation (requested/invoked) are
    omitted and remain reachable through the rules router skill.
    """
    import render_rules

    marker = "<!-- generated by tools/sync.py from shared/rules/ — edit the rule, not this file -->"
    out: dict[str, str] = {}
    for path, _fm, _body in rules:
        rendered = render_rules.render(path, "claude", include_provenance=False)
        if rendered is None:
            continue
        filename, content = rendered
        head, sep, body = content.partition("\n---\n\n")
        out[filename] = f"{head}{sep}{marker}\n\n{body}"
    return out


def check_rules(apply: bool) -> int:
    """Validate rules and check, or with apply regenerate, the rule artifacts.

    Covers the router skill index and the Claude Code rules directory.
    Returns the drift count.
    """
    rules = load_rules()
    drift = 0

    # router skill index
    expected = build_router(rules)
    if not (ROUTER_SKILL.exists() and ROUTER_SKILL.read_text() == expected):
        drift += 1
        if apply:
            ROUTER_SKILL.parent.mkdir(parents=True, exist_ok=True)
            ROUTER_SKILL.write_text(expected)
            print("  RENDER shared/skills/rules/SKILL.md")
        else:
            print("  DRIFT  shared/skills/rules/SKILL.md: router index differs from shared/rules/")

    # claude code path-scoped rules
    expected_files = build_claude_rules(rules)
    for filename, content in expected_files.items():
        out_path = CLAUDE_RULES_DIR / filename
        if out_path.exists() and out_path.read_text() == content:
            continue
        drift += 1
        if apply:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content)
            print(f"  RENDER harnesses/claude-code/rules/{filename}")
        else:
            print(f"  DRIFT  harnesses/claude-code/rules/{filename}: differs from shared/rules/")
    if CLAUDE_RULES_DIR.exists():
        for stale in sorted(CLAUDE_RULES_DIR.glob("*.md")):
            if stale.name in expected_files:
                continue
            drift += 1
            if apply:
                stale.unlink()
                print(f"  REMOVE harnesses/claude-code/rules/{stale.name}")
            else:
                print(f"  STALE  harnesses/claude-code/rules/{stale.name}: no canonical rule")

    return drift


def check_skills() -> int:
    """Schema-validate shared skill frontmatter. Exits non-zero on errors."""
    errors: list[str] = []
    warnings: list[str] = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        rel = skill_md.relative_to(REPO)
        text = skill_md.read_text()
        m = FM_RE.match(text)
        if not m:
            errors.append(f"{rel}: missing frontmatter")
            continue
        fm, err = load_frontmatter(m.group(1))
        if err or not isinstance(fm, dict):
            errors.append(f"{rel}: {err or 'frontmatter is not a mapping'}")
            continue
        for field in ("name", "description"):
            if not fm.get(field):
                errors.append(f"{rel}: missing required field '{field}'")
        if fm.get("name") and fm["name"] != skill_md.parent.name:
            errors.append(f"{rel}: name '{fm['name']}' != directory '{skill_md.parent.name}'")
        # the generated router's freshness is checked mechanically by check_rules
        if skill_md != ROUTER_SKILL and not fm.get("reviewed"):
            errors.append(f"{rel}: missing 'reviewed' (required for playbooks)")
        body = text[m.end() :]
        if len(body.splitlines()) > RULE_BODY_MAX_LINES:
            errors.append(f"{rel}: body exceeds {RULE_BODY_MAX_LINES} lines")
        lint_errors, lint_warnings = lint_common(
            rel, fm, text, description_lints=skill_md != ROUTER_SKILL
        )
        errors.extend(lint_errors)
        warnings.extend(lint_warnings)
    for w in warnings:
        print(f"  WARN  {w}")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    return 0


def main():
    """Run the requested sync checks, applying changes when --apply is set."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="apply changes in place")
    parser.add_argument("--agents", action="store_true", help="check/render agent files")
    parser.add_argument(
        "--rules", action="store_true", help="validate rules + router index + claude rules"
    )
    parser.add_argument("--skills", action="store_true", help="validate skill frontmatter")
    parser.add_argument(
        "--all", dest="all_", action="store_true", help="blocks + agents + rules + skills"
    )
    parser.add_argument("--harness", help="limit to one harness")
    args = parser.parse_args()

    only_flags = args.agents or args.rules or args.skills
    do_blocks = not only_flags or args.all_
    do_agents = args.agents or args.all_
    do_rules = args.rules or args.all_
    do_skills = args.skills or args.all_

    drift = 0
    if do_blocks:
        print("Checking blocks...")
        drift += check_blocks(args.apply, args.harness)
    if do_agents:
        print("Checking agents...")
        drift += check_agents(args.apply, args.harness)
    if do_rules:
        print("Checking rules...")
        drift += check_rules(args.apply)
    if do_skills:
        print("Checking skills...")
        drift += check_skills()

    if drift == 0:
        print("OK — all harnesses in sync")
    else:
        if args.apply:
            print(f"\n{drift} issue(s) fixed.")
        else:
            print(f"\n{drift} issue(s) found.")
            print()
            print("Before running --apply, decide for each drifted block:")
            print("  • Change was intentional (e.g. you refined a harness directly):")
            print("      Copy the updated content into shared/blocks/<name>.md first,")
            print("      then run --apply to propagate it to ALL harnesses.")
            print("  • Change was accidental or you want shared to win:")
            print("      Run --apply to overwrite the harness block with shared.")
            print()
            print(
                "⚠ --apply always overwrites harness blocks with shared."
                " Promote first or lose the change."
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
