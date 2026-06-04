#!/usr/bin/env python3
"""report.py — system topology and health check for llm-config.

Shows all shared components and how each manifests per harness, verifies all
wiring (symlinks, fences, renders), and surfaces harness-specific content for
gap analysis.

Usage:
  python tools/report.py
"""

import os
import re
import sys
import tomllib
from pathlib import Path

from rich.console import Console  # pip install rich

REPO = Path(__file__).parent.parent
HOME = Path.home()
BLOCKS_DIR = REPO / "shared/blocks"
AGENTS_DIR = REPO / "shared/agents"
HARNESSES_DIR = REPO / "harnesses"
AGENT_CONFIG = REPO / "tools/harness_agent_config.toml"

HARNESS_FILES = {
    "pi": HARNESSES_DIR / "pi/AGENTS.md",
    "claude-code": HARNESSES_DIR / "claude-code/CLAUDE.md",
    "copilot": HARNESSES_DIR / "copilot/copilot-instructions.md",
}

HARNESS_LIVE_INSTR = {
    "pi": HOME / ".pi/agent/AGENTS.md",
    "claude-code": HOME / ".claude/CLAUDE.md",
    "copilot": HOME / ".github/copilot-instructions.md",
}

# Symlinks that bootstrap.sh is responsible for creating
SYMLINK_MAP = {
    "pi": [
        (REPO / "harnesses/pi/AGENTS.md", HOME / ".pi/agent/AGENTS.md"),
        (REPO / "harnesses/pi/settings.json", HOME / ".pi/agent/settings.json"),
        (REPO / "harnesses/pi/models.json", HOME / ".pi/agent/models.json"),
        (
            REPO / "harnesses/pi/claude-bridge.json",
            HOME / ".pi/agent/claude-bridge.json",
        ),
    ],
    "claude-code": [
        (REPO / "harnesses/claude-code/CLAUDE.md", HOME / ".claude/CLAUDE.md"),
        (REPO / "harnesses/claude-code/RTK.md", HOME / ".claude/RTK.md"),
        (REPO / "harnesses/claude-code/settings.json", HOME / ".claude/settings.json"),
    ],
    "copilot": [
        (
            REPO / "harnesses/copilot/copilot-instructions.md",
            HOME / ".github/copilot-instructions.md",
        ),
        (REPO / "harnesses/copilot/agents", HOME / ".copilot/agents"),
    ],
}

FENCE_RE = re.compile(
    r"<!-- block: (?P<name>[\w-]+) -->\n.*?<!-- /block: (?P=name) -->",
    re.DOTALL,
)

console = Console()


# ── helpers ───────────────────────────────────────────────────────────────────


def short(p: Path) -> str:
    """Return path relative to repo root, or ~/... for home-relative paths."""
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        pass
    try:
        return "~/" + str(p.relative_to(HOME))
    except ValueError:
        return str(p)


def check_symlink(src: Path, dst: Path) -> tuple[bool, str]:
    """Return (ok, detail). detail is the link target on success, error message on failure."""
    if not dst.is_symlink():
        return (False, "missing") if not dst.exists() else (False, "not a symlink")
    link = os.readlink(dst)
    if not dst.exists():
        return False, f"dangling → {link}"
    if dst.resolve() != src.resolve():
        return False, f"wrong target → {link}"
    return True, link


def s_ok(label: str, detail: str = "") -> str:
    suffix = f"  [dim]{detail}[/dim]" if detail else ""
    return f"[green]✓[/green]  {label}{suffix}"


def s_warn(label: str, detail: str = "") -> str:
    suffix = f"  [dim]{detail}[/dim]" if detail else ""
    return f"[yellow]![/yellow]  {label}{suffix}"


def s_err(label: str) -> str:
    return f"[red]✗[/red]  {label}"


def section(title: str):
    console.print()
    console.rule(f"[bold]{title}[/bold]", style="bright_blue")


def harness_row(harness: str, content: str):
    console.print(f"    [dim]{harness:<14}[/dim]  {content}")


# ── blocks ────────────────────────────────────────────────────────────────────


def inspect_blocks(errors: list, warnings: list):
    section("SHARED BLOCKS")

    for bp in sorted(BLOCKS_DIR.glob("*.md")):
        name = bp.stem
        console.print(f"\n  [bold cyan]{name}[/bold cyan]")

        for harness, instr in HARNESS_FILES.items():
            if not instr.exists():
                harness_row(harness, s_err("instruction file not found"))
                errors.append(f"block '{name}': {harness} instruction file not found")
                continue

            has_fence = bool(re.search(rf"<!-- block: {re.escape(name)} -->", instr.read_text()))
            live = HARNESS_LIVE_INSTR[harness]
            sym_ok, sym_msg = check_symlink(instr, live)

            fence_s = (
                s_ok("fence") if has_fence else s_warn("no fence", "not included in this harness")
            )
            if not has_fence:
                warnings.append(f"block '{name}': not included in {harness}")

            sym_s = s_ok(short(live)) if sym_ok else s_err(f"{short(live)}: {sym_msg}")
            if not sym_ok:
                errors.append(f"symlink broken: {short(live)} ({sym_msg})")

            harness_row(harness, f"{fence_s}  ·  {sym_s}")


# ── agents ────────────────────────────────────────────────────────────────────


def inspect_agents(errors: list, warnings: list):
    section("SHARED AGENTS")

    with open(AGENT_CONFIG, "rb") as f:
        config = tomllib.load(f)

    for ap in sorted(AGENTS_DIR.glob("*.md")):
        name = ap.stem
        console.print(f"\n  [bold cyan]{name}[/bold cyan]")

        for harness, hconf in config["harnesses"].items():
            rendered = HARNESSES_DIR / harness / "agents" / f"{name}{hconf['filename_suffix']}"
            if rendered.exists():
                harness_row(harness, s_ok(short(rendered)))
            else:
                harness_row(
                    harness,
                    s_err(f"{short(rendered)}  [dim](run sync.py --agents --apply)[/dim]"),
                )
                errors.append(f"agent '{name}': rendered file missing in {harness}")

        harness_row(
            "claude-code",
            "[dim]no native agent format — use a /skill for persona invocation[/dim]",
        )


# ── skills ────────────────────────────────────────────────────────────────────


def inspect_skills(errors: list, warnings: list):
    section("SKILLS")
    skills: dict[str, dict[str, Path]] = {}

    for skill_dir, harness in [
        (HOME / ".pi/agent/skills", "pi"),
        (HOME / ".copilot/skills", "copilot"),
    ]:
        if skill_dir.exists():
            for item in sorted(skill_dir.iterdir()):
                skills.setdefault(item.name, {})[harness] = item

    cc = HARNESS_FILES["claude-code"]
    if cc.exists():
        for line in cc.read_text().splitlines():
            if line.startswith("@") and "SKILL.md" in line:
                p = Path(line[1:])
                skills.setdefault(p.parent.name, {})["claude-code"] = p

    if not skills:
        console.print("\n  [dim]no skills detected[/dim]")
        return

    for skill_name, by_harness in sorted(skills.items()):
        console.print(f"\n  [bold cyan]{skill_name}[/bold cyan]")

        for harness in HARNESS_FILES:
            if harness not in by_harness:
                harness_row(harness, "[dim]not wired[/dim]")
                warnings.append(f"skill '{skill_name}': not wired in {harness}")
                continue

            p = by_harness[harness]

            if harness == "claude-code":
                if p.exists():
                    harness_row(harness, s_ok(f"@-include → {short(p)}"))
                else:
                    harness_row(harness, s_err(f"@-include target missing: {short(p)}"))
                    errors.append(f"skill '{skill_name}': CC @-include target missing")
            elif p.is_symlink():
                link = os.readlink(p)
                link_short = link.replace(str(HOME), "~")
                if p.exists():
                    harness_row(harness, s_ok(short(p), f"→ {link_short}"))
                else:
                    harness_row(harness, s_err(f"dangling: {short(p)} → {link_short}"))
                    errors.append(f"skill '{skill_name}': {harness} symlink dangling")
            elif p.is_dir():
                harness_row(harness, s_warn(short(p), "directory, not a symlink"))
                warnings.append(
                    f"skill '{skill_name}': {harness} path is a directory, not a symlink"
                )
            else:
                harness_row(harness, s_err(f"{short(p)} not found"))
                errors.append(f"skill '{skill_name}': {harness} not wired")


# ── symlinks ──────────────────────────────────────────────────────────────────


def inspect_symlinks(errors: list, warnings: list):
    section("SYMLINKS")

    for harness, links in SYMLINK_MAP.items():
        console.print(f"\n  [bold]{harness}[/bold]")
        for src, dst in links:
            ok_flag, msg = check_symlink(src, dst)
            if ok_flag:
                console.print(f"    {s_ok(short(dst), f'→ {short(src)}')}")
            else:
                console.print(f"    {s_err(f'{short(dst)}: {msg}')}")
                errors.append(f"symlink {short(dst)}: {msg}")


# ── harness-specific ──────────────────────────────────────────────────────────


def inspect_harness_specific():
    section("HARNESS-SPECIFIC SECTIONS  (diagnostic)")

    for harness, instr in HARNESS_FILES.items():
        console.print(f"\n  [bold]{harness}[/bold]")
        if not instr.exists():
            console.print("    [dim]instruction file not found[/dim]")
            continue

        # strip all fenced regions; what remains is harness-specific
        stripped = FENCE_RE.sub("", instr.read_text())
        items = [
            line.strip()
            for line in stripped.splitlines()
            if line.strip()
            and line.strip() != "---"
            and (line.strip().startswith("#") or line.strip().startswith("@"))
        ]

        if items:
            for item in items:
                if item.startswith("@"):
                    console.print(f"    [yellow]@[/yellow]  [dim]{item[1:]}[/dim]")
                else:
                    console.print(f"    [dim]§[/dim]  {item}")
        else:
            console.print("    [dim](none)[/dim]")


# ── main ──────────────────────────────────────────────────────────────────────


def main():
    errors: list[str] = []
    warnings: list[str] = []

    console.print()
    console.rule(
        "[bold bright_blue]llm-config system inspection[/bold bright_blue]",
        style="bright_blue",
    )

    inspect_blocks(errors, warnings)
    inspect_agents(errors, warnings)
    inspect_skills(errors, warnings)
    inspect_symlinks(errors, warnings)
    inspect_harness_specific()

    section("SUMMARY")
    console.print()

    if not errors and not warnings:
        console.print("  [green]✓  all checks passed[/green]")
    else:
        for msg in errors:
            console.print(f"  [red]✗  {msg}[/red]")
        for msg in warnings:
            console.print(f"  [yellow]!  {msg}[/yellow]")
        console.print()
        if errors:
            e, w = len(errors), len(warnings)
            console.print(f"  [red]{e} error(s)[/red]  ·  [yellow]{w} warning(s)[/yellow]")
        else:
            console.print(
                f"  [green]✓  no hard errors[/green]  ·  "
                f"[yellow]{len(warnings)} warning(s)[/yellow]"
            )

    console.print()
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
