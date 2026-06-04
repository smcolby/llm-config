#!/usr/bin/env python3
"""sync.py — propagate shared blocks and render harness agent files.

Usage:
  python tools/sync.py            # check for drift (dry run)
  python tools/sync.py --apply    # rewrite fenced blocks in harness files
  python tools/sync.py --agents   # check agent body drift
  python tools/sync.py --agents --apply  # render agents from shared/agents/
  python tools/sync.py --all --apply     # blocks + agents
"""

import argparse
import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).parent.parent
BLOCKS_DIR = REPO / "shared/blocks"
AGENTS_DIR = REPO / "shared/agents"
HARNESSES_DIR = REPO / "harnesses"
AGENT_CONFIG = REPO / "tools/harness_agent_config.toml"

HARNESS_INSTRUCTION_FILES = {
    "pi": HARNESSES_DIR / "pi/AGENTS.md",
    "claude-code": HARNESSES_DIR / "claude-code/CLAUDE.md",
    "copilot": HARNESSES_DIR / "copilot/instructions.md",
}

FENCE_RE = re.compile(
    r"(<!-- block: (?P<name>[\w-]+) -->\n)"
    r"(?P<content>.*?)"
    r"(<!-- /block: (?P=name) -->)",
    re.DOTALL,
)

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def load_block(name: str) -> str:
    path = BLOCKS_DIR / f"{name}.md"
    if not path.exists():
        print(f"  ERROR: shared/blocks/{name}.md not found", file=sys.stderr)
        sys.exit(1)
    return path.read_text().rstrip("\n") + "\n"


def check_blocks(apply: bool, harness_filter: str | None = None) -> int:
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


def parse_shared_agent(path: Path):
    text = path.read_text()
    m = FM_RE.match(text)
    if not m:
        print(f"  ERROR: no frontmatter in {path}", file=sys.stderr)
        sys.exit(1)
    import yaml
    fm = yaml.safe_load(m.group(1))
    body = text[m.end():].lstrip("\n")
    return fm, body


def check_agents(apply: bool, harness_filter: str | None = None) -> int:
    with open(AGENT_CONFIG, "rb") as f:
        config = tomllib.load(f)

    drift = 0
    for slug in sorted(AGENTS_DIR.glob("*.md")):
        fm, canonical_body = parse_shared_agent(slug)
        name = slug.stem

        for harness, hconf in config.get("harnesses", {}).items():
            if harness_filter and harness != harness_filter:
                continue
            suffix = hconf["filename_suffix"]
            out_path = HARNESSES_DIR / harness / "agents" / f"{name}{suffix}"

            if apply:
                # build frontmatter
                fields = hconf.get("include_fields", ["description"])
                lines = ["---"]
                for field in fields:
                    if field == "model":
                        lines.append(f"model: {hconf['model']}")
                    elif field == "tools":
                        lines.append(f"tools: {hconf['tools']}")
                    else:
                        lines.append(f"{field}: {fm[field]}")
                lines.append("---")
                rendered = "\n".join(lines) + "\n\n" + canonical_body
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(rendered)
                print(f"  RENDER {harness}: {out_path.name}")
            elif out_path.exists():
                existing = out_path.read_text()
                # extract body (skip frontmatter)
                bm = FM_RE.match(existing)
                existing_body = existing[bm.end():].lstrip("\n") if bm else existing
                if existing_body.rstrip("\n") != canonical_body.rstrip("\n"):
                    drift += 1
                    print(f"  DRIFT  {harness}/agents/{out_path.name}: body differs from shared")
            else:
                drift += 1
                print(f"  MISSING {harness}/agents/{out_path.name}")

    return drift


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="apply changes in place")
    parser.add_argument("--agents", action="store_true", help="check/render agent files")
    parser.add_argument("--all", dest="all_", action="store_true", help="blocks + agents")
    parser.add_argument("--harness", help="limit to one harness")
    args = parser.parse_args()

    do_blocks = not args.agents or args.all_
    do_agents = args.agents or args.all_

    drift = 0
    if do_blocks:
        print("Checking blocks...")
        drift += check_blocks(args.apply, args.harness)
    if do_agents:
        print("Checking agents...")
        drift += check_agents(args.apply, args.harness)

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
            print("⚠ --apply always overwrites harness blocks with shared. Promote first or lose the change.")
            sys.exit(1)


if __name__ == "__main__":
    main()
