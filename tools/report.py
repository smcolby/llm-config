#!/usr/bin/env python3
"""report.py — system topology and health check for llm-config.

Shows all shared components and how each manifests per harness, verifies all
wiring (symlinks, fences, renders), and surfaces harness-specific content for
gap analysis.

Usage:
  python tools/report.py
"""

import json
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
MODELS_DIR = REPO / "shared/models"
EXTENSIONS_DIR = REPO / "shared/extensions"
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

# Symlinks that bootstrap.sh is responsible for creating (core harness wiring only;
# extension symlinks are defined in shared/extensions/*.toml and managed by wire_extensions.py)
SYMLINK_MAP = {
    "pi": [
        (REPO / "harnesses/pi/AGENTS.md", HOME / ".pi/agent/AGENTS.md"),
        (REPO / "harnesses/pi/settings.json", HOME / ".pi/agent/settings.json"),
        (REPO / "harnesses/pi/models.json", HOME / ".pi/agent/models.json"),
        (REPO / "harnesses/pi/mcp.json", HOME / ".pi/agent/mcp.json"),
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
        (REPO / "harnesses/copilot/mcp-config.json", HOME / ".copilot/mcp-config.json"),
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


# ── extensions ────────────────────────────────────────────────────────────────


def load_extensions() -> list[dict]:
    if not EXTENSIONS_DIR.exists():
        return []
    result = []
    for p in sorted(EXTENSIONS_DIR.glob("*.toml")):
        with open(p, "rb") as f:
            result.append(tomllib.load(f))
    return result


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _ext_check_pi_package(pkg: str) -> tuple[bool, str]:
    packages = _load_json(HARNESSES_DIR / "pi/settings.json").get("packages", [])
    return (
        (True, f"package: {pkg}")
        if any(pkg in p for p in packages)
        else (False, f"'{pkg}' not in packages in harnesses/pi/settings.json")
    )


def _ext_check_hook(cmd: str) -> tuple[bool, str]:
    hooks = _load_json(HARNESSES_DIR / "claude-code/settings.json").get("hooks", {})
    for entry in hooks.get("PreToolUse", []):
        for h in entry.get("hooks", []):
            if cmd in h.get("command", ""):
                return True, f"hook: {h['command']}"
    return False, f"no PreToolUse hook containing '{cmd}'"


def _ext_check_dir(path_str: str) -> tuple[bool, str]:
    path = Path(path_str.replace("~", str(HOME)))
    return (
        (True, f"plugin dir: {short(path)}")
        if path.is_dir()
        else (False, f"dir not found: {short(path)}")
    )


def _ext_check_mcp(config_str: str, server_key: str) -> tuple[bool, str]:
    config = Path(config_str.replace("~", str(HOME)))
    if not config.exists():
        return False, f"{short(config)}: file not found"
    servers = _load_json(config).get("mcpServers", {})
    return (
        (True, f"registered in {short(config)}")
        if any(server_key in k for k in servers)
        else (False, f"'{server_key}' not in mcpServers in {short(config)}")
    )


def inspect_extensions(errors: list, warnings: list):
    section("EXTENSIONS")
    extensions = load_extensions()

    if not extensions:
        console.print("\n  [dim]no extensions defined[/dim]")
        return

    for ext in extensions:
        name = ext["name"]
        install = ext.get("install", "")
        repo = ext.get("repo", "")
        header = f"[bold cyan]{name}[/bold cyan]"
        if install:
            header += f"  [dim]install:[/dim] {install}"
        if repo:
            header += f"  [dim]{repo}[/dim]"
        console.print(f"\n  {header}")

        for harness, hconf in ext.get("harnesses", {}).items():
            parts: list[str] = []

            for pair in hconf.get("symlinks", []):
                src = REPO / pair[0]
                dst = Path(pair[1].replace("~", str(HOME)))
                ok, msg = check_symlink(src, dst)
                if ok:
                    parts.append(s_ok(short(dst), f"→ {short(src)}"))
                else:
                    parts.append(s_err(f"{short(dst)}: {msg}"))
                    errors.append(f"extension '{name}' ({harness}) symlink: {msg}")

            if "verify_pi_package" in hconf:
                ok, msg = _ext_check_pi_package(hconf["verify_pi_package"])
                if ok:
                    parts.append(s_ok(msg))
                else:
                    parts.append(s_err(msg))
                    errors.append(f"extension '{name}' ({harness}): {msg}")

            if "verify_hook" in hconf:
                ok, msg = _ext_check_hook(hconf["verify_hook"])
                if ok:
                    parts.append(s_ok(msg))
                else:
                    parts.append(s_err(msg))
                    errors.append(f"extension '{name}' ({harness}): {msg}")

            if "verify_dir" in hconf:
                ok, msg = _ext_check_dir(hconf["verify_dir"])
                if ok:
                    parts.append(s_ok(msg))
                else:
                    parts.append(s_err(msg))
                    errors.append(f"extension '{name}' ({harness}): {msg}")

            if "verify_mcp" in hconf:
                ok, msg = _ext_check_mcp(hconf["verify_mcp"], ext.get("block", name))
                if ok:
                    parts.append(s_ok(msg))
                else:
                    parts.append(s_err(msg))
                    errors.append(f"extension '{name}' ({harness}): {msg}")

            if not parts:
                setup = hconf.get("manual_setup", "no verify configured")
                parts.append(s_warn(setup))

            harness_row(harness, "  ·  ".join(parts))


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


# ── models ────────────────────────────────────────────────────────────────────


def inspect_models(errors: list, warnings: list):
    section("SHARED MODELS")

    if not MODELS_DIR.exists():
        console.print("\n  [dim]no shared models defined[/dim]")
        return

    model_files = sorted(MODELS_DIR.glob("*.json"))
    if not model_files:
        console.print("\n  [dim]no model files found[/dim]")
        return

    # Directories to scan for symlinks pointing into shared/models/
    scan_dirs = [HARNESSES_DIR / h for h in HARNESS_FILES]

    for model_file in model_files:
        console.print(f"\n  [bold cyan]{model_file.name}[/bold cyan]")

        # Load companion manifest if present (same stem, .toml extension)
        manifest_path = model_file.with_suffix(".toml")
        manifest: dict = {}
        if manifest_path.exists():
            with open(manifest_path, "rb") as f:
                manifest = tomllib.load(f)
        expected_harnesses: list[str] = manifest.get("harnesses", [])
        not_applicable: dict[str, str] = manifest.get("not_applicable", {})
        notes: dict[str, str] = manifest.get("notes", {})

        # Find all symlinks in scan dirs that resolve to this model file
        wired: dict[str, Path] = {}
        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for candidate in scan_dir.iterdir():
                if candidate.is_symlink() and candidate.resolve() == model_file.resolve():
                    wired[scan_dir.name] = candidate

        # Report per harness
        all_harnesses = list(HARNESS_FILES.keys())
        for harness in all_harnesses:
            if harness in not_applicable:
                harness_row(harness, f"[dim]—  not applicable ({not_applicable[harness]})[/dim]")
            elif harness in notes:
                harness_row(harness, f"[dim]ℹ  {notes[harness]}[/dim]")
            elif harness in wired or harness in expected_harnesses:
                link = wired.get(harness)
                if link:
                    harness_row(harness, s_ok(short(link), f"→ {short(model_file)}"))
                else:
                    harness_row(harness, s_err(f"expected symlink missing in harnesses/{harness}/"))
                    errors.append(f"shared model '{model_file.name}': {harness} symlink missing")
            # harnesses that are neither expected nor excluded are silently skipped

        if not wired and expected_harnesses:
            warnings.append(f"shared model '{model_file.name}': no harness symlinks found")


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

    inspect_extensions(errors, warnings)
    inspect_blocks(errors, warnings)
    inspect_agents(errors, warnings)
    inspect_skills(errors, warnings)
    inspect_models(errors, warnings)
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
