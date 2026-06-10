#!/usr/bin/env python3
"""wire_extensions.py — generate and symlink per-harness extension files.

Reads shared/extensions/*.toml and shared/mcp-servers.toml, then:
  - Generates copilot hook JSON files from [[hooks]] entries
  - Generates pi TypeScript extension stubs from [[hooks]] entries
  - Generates harness MCP config files from shared/mcp-servers.toml
  - Creates symlinks declared in each manifest

Called by bootstrap.sh. Pass --check to report drift without writing.
"""

import argparse
import json
import os
import tomllib
from pathlib import Path
from typing import NamedTuple


class DriftEntry(NamedTuple):
    """A manifest-derived file with its current drift status."""

    path: Path  # the generated file in the repo
    source: Path  # the manifest it was rendered from
    status: str  # "ok" | "missing" | "drift"


REPO = Path(__file__).parent.parent
HOME = Path.home()
EXTENSIONS_DIR = REPO / "shared/extensions"
MCP_MANIFEST = REPO / "shared/mcp-servers.toml"

# Output paths for generated MCP configs, keyed by harness name
MCP_PATHS: dict[str, Path] = {
    "copilot": REPO / "harnesses/copilot/mcp-config.json",
    "pi": REPO / "harnesses/pi/mcp.json",
}

# TypeScript template for generated pi extensions (one handler per [[hooks]] entry with pi_event)
_TS_TEMPLATE = (
    "// AUTO-GENERATED from shared/extensions/{stem}.toml — do not edit directly\n"
    'import type {{ ExtensionAPI }} from "@earendil-works/pi-coding-agent"\n'
    "\n"
    "export default async function (pi: ExtensionAPI) {{\n"
    "{handlers}"
    "}}\n"
)

_TS_HANDLER = (
    '  pi.on("{event}", async () => {{\n'
    "    try {{\n"
    '      const result = await pi.exec("bash", ["-c", {command_repr}],'
    " {{ timeout: {timeout_ms} }})\n"
    "      if (result.stdout.trim()) console.warn(result.stdout.trim())\n"
    "    }} catch {{ /* fail open */ }}\n"
    "  }})\n"
)


def expand(p: str) -> Path:
    return Path(p.replace("~", str(HOME)))


def link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() and os.readlink(dst) == str(src):
        print(f"  ok   {dst}")
    else:
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        dst.symlink_to(src)
        print(f"  link {dst} → {src}")


def _write_if_changed(path: Path, content: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == content:
        print(f"  ok   {label}")
    else:
        path.write_text(content)
        print(f"  gen  {label}")


def _status_of(path: Path, content: str) -> str:
    if not path.exists():
        return "missing"
    if path.read_text() != content:
        return "drift"
    return "ok"


def _check_content(path: Path, content: str, label: str) -> int:
    """Return 1 if file is missing or differs from content, 0 if clean."""
    status = _status_of(path, content)
    if status == "missing":
        print(f"  MISSING  {label}")
        return 1
    if status == "drift":
        print(f"  DRIFT    {label}")
        return 1
    return 0


def _copilot_hooks_json(hooks: list[dict]) -> str | None:
    """Render [[hooks]] entries to copilot hook JSON. Returns None if no copilot hooks."""
    result: dict = {}
    for h in hooks:
        event = h.get("copilot_event")
        if not event:
            continue
        entry: dict = {"type": "command", "command": h["command"]}
        if "timeout" in h:
            entry["timeout"] = h["timeout"]
        result.setdefault(event, []).append(entry)
    if not result:
        return None
    return json.dumps({"hooks": result}, indent=2) + "\n"


def _pi_ts(stem: str, hooks: list[dict]) -> str | None:
    """Render [[hooks]] entries to a pi TypeScript stub. Returns None if no pi hooks."""
    handlers = []
    for h in hooks:
        event = h.get("pi_event")
        if not event:
            continue
        handlers.append(
            _TS_HANDLER.format(
                event=event,
                command_repr=json.dumps(h["command"]),
                timeout_ms=int(h.get("timeout", 5) * 1000),
            )
        )
    if not handlers:
        return None
    return _TS_TEMPLATE.format(stem=stem, handlers="".join(handlers))


def _mcp_content(harness: str, manifest: dict) -> str:
    servers = {
        name: {k: v for k, v in srv.items() if k != "harnesses"}
        for name, srv in manifest.get("servers", {}).items()
        if harness in srv.get("harnesses", [])
    }
    return json.dumps({"mcpServers": servers}, indent=2) + "\n"


def generate_hooks(check: bool) -> int:
    drift = 0
    for ext_file in sorted(EXTENSIONS_DIR.glob("*.toml")):
        with open(ext_file, "rb") as f:
            ext = tomllib.load(f)
        hooks = ext.get("hooks", [])
        if not hooks:
            continue
        stem = ext_file.stem

        copilot_content = _copilot_hooks_json(hooks)
        if copilot_content is not None:
            path = REPO / f"harnesses/copilot/hooks/{stem}.json"
            label = f"copilot/hooks/{stem}.json"
            if check:
                drift += _check_content(path, copilot_content, label)
            else:
                _write_if_changed(path, copilot_content, label)

        pi_content = _pi_ts(stem, hooks)
        if pi_content is not None:
            path = REPO / f"harnesses/pi/extensions/{stem}.ts"
            label = f"pi/extensions/{stem}.ts"
            if check:
                drift += _check_content(path, pi_content, label)
            else:
                _write_if_changed(path, pi_content, label)

    return drift


def generate_mcp(check: bool) -> int:
    if not MCP_MANIFEST.exists():
        return 0
    with open(MCP_MANIFEST, "rb") as f:
        manifest = tomllib.load(f)
    drift = 0
    for harness, path in MCP_PATHS.items():
        content = _mcp_content(harness, manifest)
        label = str(path.relative_to(REPO))
        if check:
            drift += _check_content(path, content, label)
        else:
            _write_if_changed(path, content, label)
    return drift


def collect_hooks_drift() -> list[DriftEntry]:
    """Return drift status for every hook/extension file derived from shared/extensions/*.toml."""
    result: list[DriftEntry] = []
    for ext_file in sorted(EXTENSIONS_DIR.glob("*.toml")):
        with open(ext_file, "rb") as f:
            ext = tomllib.load(f)
        hooks = ext.get("hooks", [])
        if not hooks:
            continue
        stem = ext_file.stem

        copilot_content = _copilot_hooks_json(hooks)
        if copilot_content is not None:
            path = REPO / f"harnesses/copilot/hooks/{stem}.json"
            result.append(DriftEntry(path, ext_file, _status_of(path, copilot_content)))

        pi_content = _pi_ts(stem, hooks)
        if pi_content is not None:
            path = REPO / f"harnesses/pi/extensions/{stem}.ts"
            result.append(DriftEntry(path, ext_file, _status_of(path, pi_content)))

    return result


def collect_mcp_drift() -> list[DriftEntry]:
    """Return drift status for every harness MCP config rendered from shared/mcp-servers.toml."""
    if not MCP_MANIFEST.exists():
        return []
    with open(MCP_MANIFEST, "rb") as f:
        manifest = tomllib.load(f)
    result: list[DriftEntry] = []
    for _harness, path in MCP_PATHS.items():
        content = _mcp_content(_harness, manifest)
        result.append(DriftEntry(path, MCP_MANIFEST, _status_of(path, content)))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args()

    if args.check:
        print("Checking generated files...")
        drift = generate_hooks(check=True) + generate_mcp(check=True)
        if drift == 0:
            print("OK — all generated files in sync")
        else:
            print(f"\n{drift} file(s) out of sync — run wire_extensions.py to regenerate")
            raise SystemExit(1)
        return

    # Apply mode: generate then symlink
    generate_hooks(check=False)
    generate_mcp(check=False)

    manual_steps: list[str] = []
    for ext_file in sorted(EXTENSIONS_DIR.glob("*.toml")):
        with open(ext_file, "rb") as f:
            ext = tomllib.load(f)
        print(f"  {ext['name']}")
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
