#!/usr/bin/env python3
"""registry.py — load tools/harnesses.toml, the single source of harness topology.

Every tool that needs harness wiring (sync.py, report.py, bootstrap.py) reads
it through this module. Placeholder substitution for generated files is
defined once in render_template(): bootstrap.py renders with it and report.py
verifies against it, so generator and verifier can never disagree.
"""

import tomllib
from pathlib import Path

REPO = Path(__file__).parent.parent
HOME = Path.home()
REGISTRY_PATH = REPO / "tools/harnesses.toml"


def load() -> dict:
    """Return the parsed registry TOML."""
    with REGISTRY_PATH.open("rb") as f:
        return tomllib.load(f)


def harnesses() -> dict[str, dict]:
    """Return the per-harness wiring table."""
    return load()["harnesses"]


def skills() -> list[str]:
    """Return shared skill names wired into every harness with a skill_dir."""
    return load().get("skills", [])


def agent_configs() -> dict[str, dict]:
    """Return agent frontmatter rendering rules for harnesses that declare them."""
    return {h: conf["agents"] for h, conf in harnesses().items() if "agents" in conf}


def expand(p: str) -> Path:
    """Expand a registry path: '~/...' is home-relative, anything else repo-relative."""
    if p.startswith("~/"):
        return HOME / p[2:]
    return REPO / p


def render_template(src: Path) -> str:
    """Render a generated-file template, substituting machine-specific placeholders."""
    text = src.read_text()
    return text.replace("__REPO__", str(REPO)).replace("__HOME__", str(HOME))
