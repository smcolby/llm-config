#!/usr/bin/env python3
"""report.py — system topology and health check for llm-config.

Shows all shared components and how each manifests per harness, verifies all
wiring (symlinks, fences, renders), and surfaces harness-specific content for
gap analysis.

Usage:
  python tools/report.py
"""

import difflib
import json
import os
import re
import sys
import tomllib
from pathlib import Path

from rich import box
from rich.console import Console  # pip install rich
from rich.table import Table

# share drift collectors and the registry with sibling tools (tools/ on sys.path)
sys.path.insert(0, str(Path(__file__).parent))
import registry  # noqa: E402
import wire_extensions  # noqa: E402

REPO = registry.REPO
HOME = registry.HOME
EXTENSIONS_DIR = wire_extensions.EXTENSIONS_DIR
BLOCKS_DIR = REPO / "shared/blocks"
AGENTS_DIR = REPO / "shared/agents"
MODELS_DIR = REPO / "shared/models"
HARNESSES_DIR = REPO / "harnesses"
LLM_WIKI_SRC = HOME / "repos/llm-wiki"
LLM_WIKI_LINK = HOME / ".claude/skills/llm-wiki"

# Skill-dir entries that are external plugin links, not shared skills; they are
# verified under "external sources" in HARNESS WIRING instead
EXTERNAL_PLUGIN_LINKS = {"llm-wiki"}

# Per-harness wiring topology, built from tools/harnesses.toml (see registry.py)
HARNESS_WIRING: dict[str, dict] = {
    h: {
        "instruction_repo": REPO / conf["instruction_file"],
        "instruction_live": registry.expand(conf["instruction_live"]),
        "skill_dir": registry.expand(conf["skill_dir"]) if "skill_dir" in conf else None,
        "symlinks": [(REPO / s, registry.expand(d)) for s, d in conf.get("symlinks", [])],
        "generated": [(REPO / s, registry.expand(d)) for s, d in conf.get("generated", [])],
    }
    for h, conf in registry.harnesses().items()
}

HARNESS_FILES = {h: w["instruction_repo"] for h, w in HARNESS_WIRING.items()}
HARNESS_LIVE_INSTR = {h: w["instruction_live"] for h, w in HARNESS_WIRING.items()}
SYMLINK_MAP = {h: w["symlinks"] for h, w in HARNESS_WIRING.items()}
GENERATED_MAP = {h: w["generated"] for h, w in HARNESS_WIRING.items()}

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


def _tool_cell(ext: dict, harness: str) -> tuple[str, list[str]]:
    """Return (cell_text, failure_messages) for one tool × harness cell.

    Cell vocabulary comes from `mechanisms = [...]` in the harness block.
    Verify checks (verify_hook / verify_dir / verify_mcp / verify_pi_package)
    and declared symlinks are run; failures move to the SUMMARY.
    """
    hconf = ext.get("harnesses", {}).get(harness)
    if hconf is None:
        return "[dim]—[/dim]", []

    mechanisms = hconf.get("mechanisms", [])
    label = " + ".join(mechanisms) if mechanisms else "?"
    failures: list[str] = []

    for pair in hconf.get("symlinks", []):
        src = REPO / pair[0]
        dst = Path(pair[1].replace("~", str(HOME)))
        ok, msg = check_symlink(src, dst)
        if not ok:
            failures.append(f"symlink {short(dst)}: {msg}")
    if "verify_pi_package" in hconf:
        ok, msg = _ext_check_pi_package(hconf["verify_pi_package"])
        if not ok:
            failures.append(msg)
    if "verify_hook" in hconf:
        ok, msg = _ext_check_hook(hconf["verify_hook"])
        if not ok:
            failures.append(msg)
    if "verify_dir" in hconf:
        ok, msg = _ext_check_dir(hconf["verify_dir"])
        if not ok:
            failures.append(msg)
    if "verify_mcp" in hconf:
        ok, msg = _ext_check_mcp(hconf["verify_mcp"], ext.get("block", ext["name"]))
        if not ok:
            failures.append(msg)

    glyph = "[red]✗[/red]" if failures else "[green]✓[/green]"
    return f"{glyph} {label}", failures


def inspect_tools(errors: list, warnings: list):
    """Single TOOLS table: tools as rows, harnesses as columns, mechanism per cell."""
    section("TOOLS  (per-harness integration mechanism)")

    extensions = load_extensions()
    if not extensions:
        console.print("\n  [dim]no tools defined[/dim]")
        return

    harnesses = list(HARNESS_WIRING.keys())
    table = Table(box=box.SIMPLE_HEAD, padding=(0, 2), pad_edge=False, show_edge=False)
    table.add_column("tool", style="cyan")
    for h in harnesses:
        table.add_column(h, justify="center")

    for ext in sorted(extensions, key=lambda e: e["name"].lower()):
        row = [ext["name"]]
        for h in harnesses:
            cell, failures = _tool_cell(ext, h)
            row.append(cell)
            for msg in failures:
                errors.append(f"tool '{ext['name']}' ({h}): {msg}")
        table.add_row(*row)

    console.print(table)


# ── blocks ────────────────────────────────────────────────────────────────────


def inspect_blocks(errors: list, warnings: list):
    """Block fence presence per harness. Instruction file wiring is checked in HARNESS WIRING."""
    section("SHARED BLOCKS  (fence presence per harness)")

    harnesses = list(HARNESS_FILES.keys())
    fence_text = {
        h: HARNESS_FILES[h].read_text() if HARNESS_FILES[h].exists() else None for h in harnesses
    }
    for h, text in fence_text.items():
        if text is None:
            errors.append(f"{h}: instruction file not found at {short(HARNESS_FILES[h])}")

    table = Table(box=box.SIMPLE_HEAD, padding=(0, 2), pad_edge=False, show_edge=False)
    table.add_column("block", style="cyan")
    for h in harnesses:
        table.add_column(h, justify="center")

    for bp in sorted(BLOCKS_DIR.glob("*.md")):
        name = bp.stem
        row = [name]
        for h in harnesses:
            text = fence_text[h]
            if text is None:
                row.append("[red]?[/red]")
                continue
            has_fence = bool(re.search(rf"<!-- block: {re.escape(name)} -->", text))
            if has_fence:
                row.append("[green]✓[/green]")
            else:
                row.append("[yellow]—[/yellow]")
                warnings.append(f"block '{name}': not included in {h}")
        table.add_row(*row)

    console.print(table)


# ── agents ────────────────────────────────────────────────────────────────────


def inspect_agents(errors: list, warnings: list):
    """Rendered agent file presence per harness."""
    section("SHARED AGENTS  (rendered file presence per harness)")

    agent_configs = registry.agent_configs()

    harnesses = list(agent_configs.keys())
    table = Table(box=box.SIMPLE_HEAD, padding=(0, 2), pad_edge=False, show_edge=False)
    table.add_column("agent", style="cyan")
    for h in harnesses:
        table.add_column(h, justify="center")

    for ap in sorted(AGENTS_DIR.glob("*.md")):
        name = ap.stem
        row = [name]
        for h in harnesses:
            hconf = agent_configs[h]
            rendered = HARNESSES_DIR / h / "agents" / f"{name}{hconf['filename_suffix']}"
            if rendered.exists():
                row.append("[green]✓[/green]")
            else:
                row.append("[red]✗[/red]")
                errors.append(
                    f"agent '{name}': rendered file missing in {h} "
                    f"({short(rendered)}; run sync.py --agents --apply)"
                )
        table.add_row(*row)

    console.print(table)


# ── rules ─────────────────────────────────────────────────────────────────────


def inspect_rules(errors: list, warnings: list):
    """Canonical rule catalog: schema, tiers, scopes, review dates, router freshness."""
    section("RULES  (catalog + router skill index)")

    import sync

    if not (REPO / "shared/rules").exists():
        console.print("\n  [dim]no rules defined[/dim]")
        return

    try:
        rules = sync.load_rules()
    except SystemExit:
        console.print(f"\n  {s_err('rule schema errors — see sync.py --rules output')}")
        errors.append("rule schema validation failed (python tools/sync.py --rules)")
        return

    table = Table(box=box.SIMPLE_HEAD, padding=(0, 2), pad_edge=False, show_edge=False)
    table.add_column("rule", style="cyan")
    table.add_column("tier")
    table.add_column("scope")
    table.add_column("stack")
    table.add_column("reviewed")
    for _path, fm, _body in rules:
        scope = ", ".join(fm.get("scope", [])) or "[dim]—[/dim]"
        stack = ", ".join(fm.get("stack", [])) or "[dim]—[/dim]"
        table.add_row(fm["name"], fm["tier"], scope, stack, str(fm["reviewed"]))
    console.print(table)

    expected = sync.build_router(rules)
    if sync.ROUTER_SKILL.exists() and sync.ROUTER_SKILL.read_text() == expected:
        console.print(f"\n  {s_ok('router index fresh', short(sync.ROUTER_SKILL))}")
    else:
        console.print(f"\n  {s_err('router index stale — run sync.py --rules --apply')}")
        errors.append("rules router index stale or missing (sync.py --rules --apply)")


# ── skills ────────────────────────────────────────────────────────────────────


def inspect_skills(errors: list, warnings: list):
    section("SKILLS")
    skills: dict[str, dict[str, Path]] = {}

    skill_dirs = {h: w["skill_dir"] for h, w in HARNESS_WIRING.items() if w["skill_dir"]}
    for harness, skill_dir in skill_dirs.items():
        if skill_dir.exists():
            for item in sorted(skill_dir.iterdir()):
                if item.name.startswith(".") or item.name in EXTERNAL_PLUGIN_LINKS:
                    continue
                skills.setdefault(item.name, {})[harness] = item

    if not skills:
        console.print("\n  [dim]no skills detected[/dim]")
        return

    for skill_name, by_harness in sorted(skills.items()):
        console.print(f"\n  [bold cyan]{skill_name}[/bold cyan]")

        for harness in skill_dirs:
            if harness not in by_harness:
                harness_row(harness, "[dim]not wired[/dim]")
                warnings.append(f"skill '{skill_name}': not wired in {harness}")
                continue

            p = by_harness[harness]

            if p.is_symlink():
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


# ── harness wiring (symlinks + generated files) ───────────────────────────────


def inspect_harness_wiring(errors: list, warnings: list):
    section("HARNESS WIRING  (symlinks + generated files)")

    all_harnesses = sorted(set(list(SYMLINK_MAP) + list(GENERATED_MAP)))
    for harness in all_harnesses:
        console.print(f"\n  [bold]{harness}[/bold]")
        for src, dst in SYMLINK_MAP.get(harness, []):
            ok_flag, msg = check_symlink(src, dst)
            if ok_flag:
                console.print(f"    {s_ok(short(dst), f'→ {short(src)}')}")
            else:
                console.print(f"    {s_err(f'{short(dst)}: {msg}')}")
                errors.append(f"symlink {short(dst)}: {msg}")
        for _src, dst in GENERATED_MAP.get(harness, []):
            if dst.exists() and not dst.is_symlink():
                console.print(f"    {s_ok(short(dst), '(generated)')}")
            elif dst.is_symlink():
                console.print(f"    {s_warn(short(dst), 'still a symlink — re-run bootstrap.py')}")
                warnings.append(
                    f"generated file {short(dst)}: still a symlink, re-run bootstrap.py"
                )
            else:
                console.print(f"    {s_err(f'{short(dst)}: not found — run bootstrap.py')}")
                errors.append(f"generated file {short(dst)}: not found")

    # external-source symlinks (sources live outside this repo)
    console.print("\n  [bold]external sources[/bold]")
    if LLM_WIKI_SRC.exists():
        ok_flag, msg = check_symlink(LLM_WIKI_SRC, LLM_WIKI_LINK)
        if ok_flag:
            console.print(f"    {s_ok(short(LLM_WIKI_LINK), f'→ {short(LLM_WIKI_SRC)}')}")
        else:
            console.print(f"    {s_err(f'{short(LLM_WIKI_LINK)}: {msg}')}")
            errors.append(f"symlink {short(LLM_WIKI_LINK)}: {msg}")
    else:
        console.print(
            f"    [dim]—  {short(LLM_WIKI_LINK)}: source {short(LLM_WIKI_SRC)} "
            f"not cloned on this machine[/dim]"
        )


# ── generated-file drift ──────────────────────────────────────────────────────


# single substitution definition shared with bootstrap.py — see registry.py
render_template = registry.render_template


def _colored_diff(expected: str, actual: str, src: Path, dst: Path) -> list[str]:
    diff = difflib.unified_diff(
        expected.splitlines(),
        actual.splitlines(),
        fromfile=f"template (rendered): {short(src)}",
        tofile=f"live: {short(dst)}",
        n=1,
        lineterm="",
    )
    out: list[str] = []
    for line in diff:
        if line.startswith(("+++", "---")):
            out.append(f"[bold]{line}[/bold]")
        elif line.startswith("@@"):
            out.append(f"[cyan]{line}[/cyan]")
        elif line.startswith("+"):
            out.append(f"[green]{line}[/green]")
        elif line.startswith("-"):
            out.append(f"[red]{line}[/red]")
        else:
            out.append(f"[dim]{line}[/dim]")
    return out


def inspect_generated_drift(warnings: list):
    section("GENERATED FILE DRIFT  (live vs rendered template)")

    any_drift = False
    for harness in sorted(GENERATED_MAP):
        for src, dst in GENERATED_MAP[harness]:
            if not src.exists() or not dst.exists() or dst.is_symlink():
                # missing / unrendered cases are reported in HARNESS WIRING above
                continue
            # normalise trailing newlines on both sides
            expected = render_template(src).rstrip("\n")
            actual = dst.read_text().rstrip("\n")
            if expected == actual:
                continue

            any_drift = True
            console.print(f"\n  [bold cyan]{harness}[/bold cyan]  ·  {short(dst)}")
            for line in _colored_diff(expected, actual, src, dst):
                console.print(f"    {line}")
            console.print()
            console.print("    [dim]Resolve manually:[/dim]")
            console.print(
                "    [dim]  • discard live changes, restore from template:[/dim]"
                "  python tools/bootstrap.py"
            )
            console.print(
                f"    [dim]  • promote live values into template:[/dim]"
                f"  edit {short(src)} (keep [italic]__HOME__[/italic] / "
                f"[italic]__REPO__[/italic] placeholders), then python tools/bootstrap.py"
            )
            warnings.append(
                f"generated file drift: {short(dst)} differs from rendered "
                f"{short(src)} — manual reconciliation required"
            )

    if not any_drift:
        console.print("\n  [green]✓  no drift between live files and rendered templates[/green]")


# ── manifest-derived files ────────────────────────────────────────────────────


def inspect_manifest_drift(errors: list, warnings: list):
    section("MANIFEST-DERIVED FILES  (manifest → repo)")

    entries = wire_extensions.collect_hooks_drift() + wire_extensions.collect_mcp_drift()
    if not entries:
        console.print("\n  [dim]no manifest-derived files[/dim]")
        return

    by_source: dict[Path, list[wire_extensions.DriftEntry]] = {}
    for e in entries:
        by_source.setdefault(e.source, []).append(e)

    any_issue = False
    for source in sorted(by_source, key=lambda p: str(p)):
        console.print(f"\n  [bold cyan]{short(source)}[/bold cyan]")
        for e in by_source[source]:
            if e.status == "ok":
                console.print(f"    {s_ok(short(e.path))}")
            elif e.status == "drift":
                any_issue = True
                console.print(f"    {s_warn(short(e.path), 'drift — manifest and file differ')}")
                warnings.append(
                    f"manifest drift: {short(e.path)} out of sync with {short(e.source)}"
                )
            else:  # missing
                any_issue = True
                console.print(f"    {s_err(f'{short(e.path)}: missing')}")
                errors.append(f"manifest-derived file missing: {short(e.path)}")

    if any_issue:
        console.print("\n    [dim]Resolve: python tools/wire_extensions.py[/dim]")


# ── main ──────────────────────────────────────────────────────────────────────


def main():
    errors: list[str] = []
    warnings: list[str] = []

    console.print()
    console.rule(
        "[bold bright_blue]llm-config system inspection[/bold bright_blue]",
        style="bright_blue",
    )

    inspect_tools(errors, warnings)
    inspect_blocks(errors, warnings)
    inspect_agents(errors, warnings)
    inspect_rules(errors, warnings)
    inspect_skills(errors, warnings)
    inspect_models(errors, warnings)
    inspect_manifest_drift(errors, warnings)
    inspect_harness_wiring(errors, warnings)
    inspect_generated_drift(warnings)

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
