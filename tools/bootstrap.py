#!/usr/bin/env python3
"""bootstrap.py — wire all llm-config symlinks and generated files.

Reads the harness registry (tools/harnesses.toml) and wires every installed
harness: instruction files, configs, agents, skills, and extensions. Safe to
re-run: correct symlinks are skipped, broken ones replaced, generated files
rewritten only when their rendered content changes.

Usage:
  python tools/bootstrap.py                   # wire everything
  python tools/bootstrap.py --only PATH       # re-wire a single live file
  python tools/bootstrap.py --skill NAME      # wire one skill into all harnesses
  python tools/bootstrap.py --remove HARNESS  # unlink a harness and archive it
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import registry  # noqa: E402
from registry import HOME, REPO, expand, render_template  # noqa: E402

LLM_WIKI = HOME / "repos/llm-wiki"
WIRE_EXTENSIONS = REPO / "tools/wire_extensions.py"


# ── primitives ────────────────────────────────────────────────────────────────


def link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() and os.readlink(dst) == str(src):
        print(f"  ok   {dst}")
        return
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.is_dir():
        print(f"  ERROR {dst} is a real directory — refusing to replace; resolve manually")
        return
    dst.symlink_to(src)
    print(f"  link {dst} → {src}")


def generate(src: Path, dst: Path) -> None:
    content = render_template(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink():
        dst.unlink()
    if dst.is_file() and dst.read_text() == content:
        print(f"  ok   {dst}")
        return
    dst.write_text(content)
    print(f"  gen  {dst}")


def unlink_if_symlink(dst: Path) -> None:
    if dst.is_symlink():
        dst.unlink()
        print(f"  unlink {dst}")


def harness_installed(conf: dict) -> bool:
    return expand(conf["root"]).is_dir()


# ── wiring ────────────────────────────────────────────────────────────────────


def wire_harness(name: str, conf: dict) -> None:
    if not harness_installed(conf):
        print(f"  SKIP {name} — {expand(conf['root'])} not found")
        return
    print(f"Wiring {name}...")
    for pair in conf.get("symlinks", []):
        link(REPO / pair[0], expand(pair[1]))
    for pair in conf.get("generated", []):
        generate(REPO / pair[0], expand(pair[1]))


def skill_source(skill: str) -> Path | None:
    """Resolve a skill name to its canonical directory.

    shared/skills/ is the source of truth; an external domain repo is the
    fallback for skills that have not graduated (see
    patterns/cross-harness-config-pattern.md).
    """
    shared = REPO / "shared/skills" / skill
    if shared.is_dir():
        return shared
    external = LLM_WIKI / ".pi/skills" / skill
    if external.is_dir():
        return external
    return None


def wire_skill(skill: str) -> None:
    src = skill_source(skill)
    if src is None:
        print(f"  WARN skill '{skill}' not found in shared/skills/ or llm-wiki — skipping")
        return
    for name, conf in registry.harnesses().items():
        if "skill_dir" not in conf or not harness_installed(conf):
            continue
        link(src, expand(conf["skill_dir"]) / skill)
    print(f"  skill '{skill}' wired")


def wire_external() -> None:
    """Link sources that live outside this repo (plugins, external skill repos)."""
    print("Wiring external sources...")
    claude_dir = HOME / ".claude"
    if not claude_dir.is_dir():
        print("  SKIP — ~/.claude not found")
        return
    if LLM_WIKI.is_dir():
        link(LLM_WIKI, claude_dir / "skills/llm-wiki")
    else:
        print(f"  SKIP llm-wiki — {LLM_WIKI} not cloned")
    cm = shutil.which("context-mode")
    if cm:
        plugin = Path(cm).resolve().parent / ".claude-plugin"
        if plugin.is_dir():
            # ~/.claude/context-mode is the tool's data directory (content/*.db
            # knowledge bases, sessions/); only the inner .claude-plugin manifest
            # links to the npm package, so package upgrades never touch user data
            data_dir = claude_dir / "context-mode"
            if data_dir.is_symlink():
                data_dir.unlink()
            data_dir.mkdir(exist_ok=True)
            link(plugin, data_dir / ".claude-plugin")
    else:
        print("  SKIP context-mode — not installed (npm install -g context-mode)")


def wire_only(target: str) -> None:
    """Re-wire the single registry entry whose live path matches target."""
    t = Path(target).expanduser().absolute()
    for conf in registry.harnesses().values():
        for pair in conf.get("symlinks", []):
            if expand(pair[1]) == t:
                link(REPO / pair[0], t)
                return
        for pair in conf.get("generated", []):
            if expand(pair[1]) == t:
                generate(REPO / pair[0], t)
                return
    sys.exit(f"No registry entry has live path {t}")


# ── removal ───────────────────────────────────────────────────────────────────


def remove_harness(name: str) -> None:
    conf = registry.harnesses().get(name)
    if conf is None:
        sys.exit(f"Unknown harness: {name}")
    print(f"Removing harness: {name}")
    for pair in conf.get("symlinks", []):
        unlink_if_symlink(expand(pair[1]))
    for pair in conf.get("generated", []):
        dst = expand(pair[1])
        if dst.is_file() and not dst.is_symlink():
            dst.unlink()
            print(f"  rm     {dst}")
    if "skill_dir" in conf:
        for skill in registry.skills():
            unlink_if_symlink(expand(conf["skill_dir"]) / skill)
    if name == "claude-code":
        unlink_if_symlink(HOME / ".claude/skills/llm-wiki")
        unlink_if_symlink(HOME / ".claude/context-mode/.claude-plugin")
        unlink_if_symlink(HOME / ".claude/context-mode")  # legacy whole-dir wiring
    subprocess.run([sys.executable, str(WIRE_EXTENSIONS), "--remove", name], check=True)

    archive_dir = REPO / "harnesses/_deprecated"
    archive_dir.mkdir(exist_ok=True)
    shutil.move(str(REPO / "harnesses" / name), str(archive_dir / name))
    print(f"  archived harnesses/{name} → harnesses/_deprecated/{name}")
    print(f"  Done. Delete '{name}' from tools/harnesses.toml then run verify.py.")


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", metavar="PATH", help="re-wire a single live file")
    parser.add_argument("--skill", metavar="NAME", help="wire one skill into all harnesses")
    parser.add_argument("--remove", metavar="HARNESS", help="unlink a harness and archive it")
    args = parser.parse_args()

    if args.remove:
        remove_harness(args.remove)
        return
    if args.skill:
        wire_skill(args.skill)
        return
    if args.only:
        wire_only(args.only)
        return

    print("=== llm-config bootstrap ===")
    print(f"Repo: {REPO}\n")

    for name, conf in registry.harnesses().items():
        wire_harness(name, conf)
        print()

    for skill in registry.skills():
        wire_skill(skill)
    print()

    wire_external()
    print()

    print("Wiring extensions...")
    subprocess.run([sys.executable, str(WIRE_EXTENSIONS)], check=True)
    print()

    print("=== Manual steps required ===")
    print("  1. Edit shared/models/ollama.json — update Ollama baseUrl to this machine's address")
    print("  2. Create ~/.pi/agent/auth.json with API keys (never committed)")
    print("  (Extension-specific one-time setup printed above)")
    if not os.environ.get("OLLAMA_HOST"):
        print(
            "  3. Add 'export OLLAMA_HOST=http://loki.local:11434' to your shell profile"
            " so 'ollama launch claude' routes to loki.local"
        )
    print()
    print("Run 'python tools/verify.py' to confirm congruence.")


if __name__ == "__main__":
    main()
