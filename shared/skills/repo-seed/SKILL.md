---
name: repo-seed
description: >
  Stand up or refresh a repository's agentic infrastructure from the
  enchiridion catalog: detect languages and stack, ask the unresolved axis
  questions, render provenance-stamped rules, and instantiate AGENTS.md
  plus tool configs from a seed archetype. Use when creating a new repo,
  adding agent config to an existing repo, or bringing a seeded repo up to
  date with the catalog (reseed).
reviewed: 2026-06
---

# Repo Seed / Reseed

Deploys catalog content into a repository as committable, provenance-stamped copies. The catalog lives in the enchiridion repository (resolve it via the real path of this SKILL.md); seeds live in `shared/seeds/`, rules in `shared/rules/`, and the renderer is `tools/render_rules.py`.

## Seed (new or unseeded repo)

### 1. Detect first

Inspect before asking anything:

- **Languages**: file extensions present (or planned, for an empty repo).
- **Stack**: `pyproject.toml` / lockfiles / imports (FastAPI, NumPy, etc.).
- **Test framework**: test dirs, pytest config, imports.
- **Environment manager**: `uv.lock` → uv; `pixi.toml` → pixi; `environment.yml` → conda; none → uv (the default for new projects).
- **Harnesses in use**: `.cursor/`, `.github/copilot-*` or `.github/instructions/`, `.claude/`, existing `AGENTS.md`. For rule deployment the footprint is the harness's rule directory (`.cursor/rules/`, `.github/instructions/`, `.claude/rules/`): its presence means the repo already uses repo-local rules for that harness, so render there without asking.
- **Existing instruction files**: `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`. If harness-branded files exist without `AGENTS.md`, offer two paths and never create a second freestanding instruction file: **consolidate** (move content into a new `AGENTS.md`, shrink the branded files to one-line pointers) or **conform** (treat the existing file as the repo's canonical and apply the seed template's sections to it instead). Conform is the default for repos the user does not own.

### 2. Ask only what detection could not resolve

At most four questions, detected values offered as defaults:

1. Purpose archetype: `python-library`, `python-cli`, `python-service`, `data-science`, or `blog-analysis` (a lightweight analysis repo whose deliverable is a featured `blogpost.md`; pick the closest, and mixed repos take the dominant one).
2. Strictness posture: adopt the seed's full gate config, or start lenient (gates warn, tighten later).
3. Environment manager, only when detection is ambiguous or the repo is empty: uv (default), pixi, or conda. When conda is detected, confirm rather than assume: the team may be mid-migration.
4. Target harness formats, only when no rule-directory footprint is detectable: Cursor project rules, Copilot instructions, Claude Code project rules, or none (AGENTS.md only). Context for the Claude option: the catalog already deploys scoped rules globally through the `~/.claude/rules` symlink, so repo-local `.claude/rules/` copies add value only for collaborators and CI without the catalog; default to none for solo repos. pi has no scoped-rule mechanism; there the global `rules` skill activates by description match.

### 3. Deploy per the selection matrix

| Content | Action |
|---|---|
| Seed `AGENTS.md` | Instantiate from `shared/seeds/<archetype>/AGENTS.md`, filling project specifics; repo-owned after creation. Templates assume uv; when the env-manager axis resolves to pixi or conda, rewrite the Environment section for that manager while preserving the discipline (one declared manifest, a committed lockfile, no ad-hoc installs) |
| `lang/*` rules for detected languages | For Cursor: render `.mdc` via `python tools/render_rules.py --format mdc --out <repo>/.cursor/rules <rule files>`. For Copilot CLI: render `.instructions.md` via `--format copilot --out <repo>/.github/instructions`. For Claude Code (when repo-local rules were selected or detected): render via `--format claude --out <repo>/.claude/rules`; the renderer skips `requested`/`invoked` tiers, which have no Claude representation and stay with the `rules` skill. For pi: the global `rules` skill activates rules by description match; instead, append a rules hint to the repo `AGENTS.md` (see note below) |
| `stack/*` rules matching detected dependencies | Same per-harness treatment as lang rules, after confirming with the user |
| Tool configs | Merge `shared/seeds/<archetype>/pyproject-fragment.toml` into the repo's `pyproject.toml` (never clobber existing sections; reconcile) and add the pre-commit config. The fragment is gate config only (ruff/pyright/pytest), valid under any environment manager |
| Doctrine, playbooks, `task/*` rules | Never deployed; they stay global |

Rendered rule copies carry a `provenance:` stamp (canonical path @ catalog commit) injected by the renderer; do not strip it.

**AGENTS.md rules hint**: every seeded repo gets a `## Coding rules` section in `AGENTS.md`; its content depends on what was deployed. Never enumerate individual rule names: the list rots as rules are added or retired, and `AGENTS.md` is repo-owned so reseed cannot rewrite it.

When repo-local rule directories were deployed, point at the directories so any agent (including one without the catalog or native glob activation) finds them deterministically:

```markdown
## Coding rules

Scoped coding rules are committed under `.claude/rules/` (and `.cursor/rules/`
or `.github/instructions/` where present). Before editing files matching a
rule's `paths`/`globs` frontmatter, read that rule.
```

When no rule directory was deployed (pi-only or AGENTS.md-only repos), the rules live only in the catalog, so point at the router skill instead; this hint works only on machines with the catalog wired:

```markdown
## Coding rules

Rules from the enchiridion catalog apply to this repo via the `rules` skill.
Consult its index and read the matching rule before editing files in scope.
```

### 4. Close out

Run the repo's gates once (`ruff check`, `pyright`, `pytest` if tests exist) so the user sees the baseline; list what was deployed and what was skipped; remind the user to commit.

## Reseed (already-seeded repo)

1. Find deployed copies by their `provenance:` stamps (`.cursor/rules/` for Cursor, `.github/instructions/` for Copilot CLI, `.claude/rules/` for Claude Code). For pi repos, check the `AGENTS.md` rules hint section instead.
2. For each, compare against the current canonical rule; collect diffs.
3. Present diffs grouped by rule; the user approves per rule. Approved: re-render and re-stamp. Declined: add `diverged: true` to the copy's frontmatter so future reseeds stop re-proposing it.
4. Re-run detection: new languages or dependencies since seeding mean new rules to offer; removed ones mean copies to retire.
5. AGENTS.md is repo-owned and never overwritten by reseed; at most, suggest additions.
