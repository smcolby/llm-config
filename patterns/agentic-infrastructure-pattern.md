# Agentic Infrastructure — Content Pattern

This document describes a harness-agnostic pattern for the *content* of agentic infrastructure: the instructions, rules, skills, personas, and templates that make AI coding assistants reliably good at software development across the full lifecycle. Coding, documentation, adversarial review, and testing are the first instantiated areas (with Python as the first instantiated language), but the architecture is built to absorb any development activity; the [coverage test](#coverage-test) below states the claim precisely.

It is written in the spirit of Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): principles first, named operations, deliberately abstract about implementation. Share it with an LLM and instantiate a version that fits your setup.

It is the companion to [cross-harness-config-pattern.md](cross-harness-config-pattern.md). The two divide cleanly:

- **cross-harness-config-pattern.md** is the *distribution* system: how canonical content reaches each harness (blocks, fences, symlinks, registries, verification).
- **agentic-infrastructure-pattern.md** (this document) is the *content architecture*: what that content is, how it is layered, scoped, activated, and kept healthy.

cross-harness-config-pattern.md answers "how does an instruction get to Claude Code and Copilot identically?" This document answers "which instructions should exist, at what scope, and when should the model see them?"

---

## Definitions

The pattern's vocabulary, in one place. Each term is developed fully in its own section; this table exists to orient a first read.

| Term | Definition |
|---|---|
| **Harness** | An AI coding assistant runtime (Claude Code, Copilot CLI, pi, Cursor). Each reads its own config formats; the pattern treats them as render targets |
| **Catalog** | The full set of canonical content this pattern manages: doctrine, rules, playbooks, personas, and seeds, stored harness-agnostically in one repo |
| **Doctrine** | Universal always-on instructions (style, guardrails, conventions). The most expensive tier, so the smallest: it carries a hard token ceiling |
| **Rule** | A scoped, conditional instruction file keyed to a language, stack, file pattern, or task. Activated when relevant rather than always. The new layer this pattern introduces |
| **Playbook** | A multi-step procedure delivered as a skill (e.g. adversarial review, test authoring). Loaded on demand, never resident |
| **Persona** | A stance and authority for delegated work (the critic, the tester). Carries no procedure and no domain constraints; those live in playbooks and rules |
| **Seed** | A repository instantiation template: starter `AGENTS.md`, rule selection, and tool configs for a project archetype, applied once at repo creation |
| **Activation tier** | When content enters context: `always` (every session), `scoped` (matching files in play), `requested` (description matches the task), `invoked` (explicit call) |
| **Degradation ladder** | The rule that a harness lacking native support for a tier renders content at a *lazier* tier, never an eagerer one |
| **Scope** | The glob patterns a `scoped` artifact attaches to |
| **Stack pin** | An explicit version range (`pytest>=8`) attached to any advice that is only true for that range; makes staleness auditable |
| **Anti-hallucination section** | A rule section enumerating banned patterns (deprecated APIs, phantom imports) next to their correct replacements; targets model failure modes directly |
| **Provenance stamp** | Frontmatter on a rule copy deployed into a repo, naming the catalog rule and commit it was rendered from; makes drift between repo and catalog mechanical to detect |
| **Enforcement pairing / hardening** | The principle that any directive a machine can check migrates out of prose into a deterministic gate (linter rule, type-checker setting, hook); rules retain only judgment content. Hardening is the triage pass that performs the migration |
| **Operation** | A named maintenance workflow run against the catalog: `ingest`, `seed`, `reseed`, `promote`/`demote`, `capture`, `verify`, `audit`. Each ships as a playbook in the catalog itself, except `verify`, which is deterministic tooling |

---

## Source survey

Four community ecosystems motivate this pattern. Each is mined for *what* it implements; the *how* (harness packaging, file formats, directory conventions) is discarded and re-derived to fit a cross-harness system.

| Source | What it implements | What we take |
|---|---|---|
| [PatrickJS/awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules) | Hundreds of stack- and task-scoped rule files: per-framework best practices, per-tool testing rules, anti-hallucination rules that ban deprecated/phantom APIs, "full stack" packs combining rules + instructions + generation skills | The rule *catalog shape*: rules are scoped to a stack or a task, follow a consistent anatomy (expertise line, principles, layered do/don't directives, pinned dependency versions), and anti-hallucination rules are a distinct, valuable rule species |
| [tugkanboz/awesome-cursorrules](https://github.com/tugkanboz/awesome-cursorrules) | The MDC rule architecture: frontmatter metadata (`description`, `globs`, `alwaysApply`), four activation types (Always, Auto Attached, Agent Requested, Manual), nested rule directories, template files referenced from rules, migration away from one monolithic rules file | The *activation model*: rules carry metadata describing when they apply, and a harness (or the model itself) loads them conditionally instead of always. This is the core idea this pattern generalizes across harnesses |
| [danielrosehill/Agents.md-Templates](https://github.com/danielrosehill/Agents.md-Templates) | A library of `AGENTS.md` templates organized by axis (project type, purpose, stack, operator role), used to seed new repositories with proven context: environment setup, operating model, typical tasks | The *seeding operation*: per-repo instruction files are instantiated from a curated template library rather than written from scratch, and templates are classified along explicit axes |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | A cross-vendor skill ecosystem: official skills by language and domain, security skills, a per-harness skill path table, and explicit quality standards (third-person keyword-rich descriptions, progressive disclosure budgets, no absolute paths, scoped tools) | The *quality bar*: measurable authoring standards for on-demand content, and confirmation that skills are the one content type with a near-uniform format across all major harnesses |

---

## The context budget principle

Always-on context is the scarcest resource in the system. Every token in a global instruction file is paid in every session, dilutes attention on the tokens that matter, and competes with the actual task. The monolithic config file (one giant `.cursorrules`, one sprawling `CLAUDE.md`) fails for exactly this reason: all rules active all the time, regardless of relevance.

Every layer in this pattern exists to move content *out* of the always-on tier into the cheapest tier that still gets it seen at the right moment:

- A pytest convention does not belong in global instructions; it belongs in a rule that activates when test files are in play.
- A FastAPI guideline does not belong in a Python rule; it belongs in a stack rule that activates only in FastAPI repos.
- A 300-line review procedure does not belong in any rule; it belongs in a skill loaded when review is requested.

The discipline: **content earns its tier.** Promotion toward always-on requires evidence that the content is needed in essentially every session. The default direction of travel is downward, toward narrower scope and lazier loading.

---

## The five content layers

The architecture has five layers of LLM-facing content, ordered from broadest scope and eagerest loading to narrowest scope and laziest loading. (Extensions, third-party tools needing per-harness wiring, are a mechanism rather than content, and remain covered by cross-harness-config-pattern.md.)

| Layer | What it is | Scope | Loaded | Exists in llm-config today |
|---|---|---|---|---|
| **1. Doctrine** | Universal behavioral instructions: style, safety guardrails, writing and git conventions, tool routing | Global, every session | Always | Yes: `shared/blocks/` |
| **2. Rules** | Scoped, conditional guidance keyed to a language, stack, file pattern, or task: "when touching Python tests, these conventions apply" | Per language / stack / file pattern / task | Conditionally, by scope match or relevance | **No: this is the new layer** |
| **3. Playbooks (skills)** | Multi-step procedures with progressive disclosure: how to run an adversarial review, how to author a test suite | Per procedure | On demand, by description match or explicit invocation | Yes: `shared/skills/` |
| **4. Personas (agents)** | Stances and authorities for delegated work: the critic, the tester, the planner | Per delegated task | When spawned | Yes: `shared/agents/` |
| **5. Seeds** | Repository instantiation templates: starter `AGENTS.md`, starter rule selections, starter tool configs for a given project archetype | Per new repository | Once, at repo creation | **No: new layer** |

### Coverage test

The layers claim to cover software development writ large, and the claim is checkable: **any development activity decomposes into a stance (persona), a procedure (playbook), constraints (rules), and a scope (tier plus globs).** If an activity ever resists this decomposition, the architecture needs a new layer; until then, new activities are new artifacts in existing layers. Spot checks across the lifecycle:

| Activity | Decomposition |
|---|---|
| Debugging / incident response | Debugging playbook (hypothesis-driven, reproduce-first) + existing personas; no new layer |
| Refactoring / dependency migration | Migration playbook + stack rules with version pins on both sides of the migration |
| Performance work | Profiling playbook + a `task/performance` rule (measure before optimizing, budgets) |
| Architecture / design | ADR-authoring playbook + seed templates carrying the decision-record convention |
| Release engineering | Release playbook + doctrine git conventions + a `task/release` rule (changelog, versioning) |
| CI/CD and infra-as-code | Stack rules (the pipeline DSL is a stack) + scoped activation on workflow files |
| Database / data migrations | Stack rule + migration playbook; anti-hallucination entries for the ORM's deprecated APIs |

The instantiated catalog (see [Python instantiation](#python-instantiation)) covers coding, documentation, review, and testing first because those were the seeding priorities; the rows above enter the catalog through the same operations as everything else.

The layers compose. A persona supplies the stance ("you are an adversarial reviewer; find problems, do not praise"), a playbook supplies the procedure (review passes, severity rubric, output format), and rules supply the domain constraints the reviewer checks against (the Python testing rule defines what a healthy test looks like; the critic enforces it). Keeping stance, procedure, and domain knowledge in separate artifacts means each is reusable: the same critic persona runs a security review with a different playbook, and the same testing rule serves both the author writing tests and the critic judging them.

---

## Activation tiers

Generalizing the MDC model, every piece of content declares one of four activation tiers. The tier is canonical metadata; how each harness honors it is a rendering concern.

| Tier | Semantics | MDC equivalent |
|---|---|---|
| `always` | In context every session | `alwaysApply: true` |
| `scoped` | Activated when work touches matching files, languages, or directories | `globs:` auto-attach |
| `requested` | Model pulls it in when its description matches the task at hand | Agent Requested |
| `invoked` | Loaded only on explicit user or agent invocation | Manual `@rule` |

Harness support for these tiers is uneven, which is precisely why the tier must be declared canonically and rendered per harness:

| Harness capability | `always` | `scoped` | `requested` | `invoked` |
|---|---|---|---|---|
| Native scoped rules (Cursor `.cursor/rules/*.mdc`, Copilot `*.instructions.md` with `applyTo`) | native | native | native | native |
| Directory-scoped instruction files (Claude Code nested `CLAUDE.md`/`AGENTS.md`) | native | emulated via placement | via skill description | via skill |
| Skills only (any harness with a skill directory) | inline in instructions | degraded to `requested` | native | native |

**Tier degradation ladder:** when a harness cannot honor a tier natively, degrade *downward* (lazier), never upward. A `scoped` Python testing rule on a harness without glob rules becomes a `requested` skill with a strong description ("Apply when writing or modifying pytest tests..."), never an `always` block. Degrading upward is how monolithic config files re-emerge.

---

## Rule architecture

Rules are the new layer, so they get the full treatment.

### Canonical schema

One rule per file, canonical body harness-agnostic, metadata in frontmatter. Mirroring the agent mechanism in cross-harness-config-pattern.md: the body is byte-identical everywhere; frontmatter is rendered per harness from the canonical fields.

```markdown
---
name: python-testing
description: >
  Pytest conventions for Python test suites: fixtures, parametrization,
  structure, and coverage policy. Apply when creating or modifying tests,
  conftest.py, or test configuration.
tier: scoped
scope: ["**/test_*.py", "**/tests/**", "**/conftest.py"]
stack: ["pytest>=8"]
reviewed: 2026-06
---

(rule body)
```

Field semantics:

- `name` — slug, unique across the rule catalog.
- `description` — third person, states *what* and *when*, loaded with matchable keywords ("pytest fixtures parametrization", never "testing stuff"). On harnesses that degrade `scoped` to `requested`, the description *is* the activation mechanism, so it carries the full weight.
- `tier` — one of the four activation tiers.
- `scope` — glob patterns, used by harnesses with native scoped rules and ignored (in favor of `description`) elsewhere.
- `stack` — explicit version pins for every framework or library the rule's advice depends on. A rule that says "use lifespan context managers" is correct for one FastAPI version range and wrong outside it; the pin makes the dependency auditable.
- `reviewed` — date of last human/agent audit against the pinned stack. Stale rules are worse than no rules: they confidently assert outdated APIs.

### Rule anatomy

The community catalog converges on a consistent body shape, and it works:

1. **Expertise line** — one sentence establishing the frame ("You are an expert in Python, pytest, and test architecture"). One sentence costs almost nothing, reliably shifts vocabulary and rigor toward the domain, and every mature catalog converges on it.
2. **Principles** — 3 to 7 priority-ordered commitments. These resolve conflicts: when two directives collide, the higher principle wins.
3. **Directives by layer** — concrete, imperative do/don't items grouped by concern (structure, naming, error handling, performance). Each directive is checkable: a reviewer can point at code and say "violates directive 4."
4. **Anti-hallucination section** (where applicable) — enumerated *banned* patterns next to their correct replacements: deprecated APIs, phantom imports, plausible-but-wrong idioms the model is known to produce for this stack. This rule species (pioneered in the community catalogs for NestJS and Next.js/Supabase) directly targets the model's failure mode rather than the human's, and is among the highest-value content per token in the system.
5. **References** — pointers to templates or canonical examples, loaded on demand rather than inlined.

No motivational filler, no restating what the model already does correctly. A rule is a diff against default model behavior: if removing a directive changes nothing, remove it.

### Rule taxonomy

Rules organize along two axes, mirroring the community catalogs:

```
rules/
├── lang/           # Language-scoped: conventions for a language wherever it appears
│   └── python/
│       ├── core.md          # idioms, typing, naming, error handling
│       ├── testing.md       # pytest conventions
│       ├── docs.md          # docstring and documentation conventions
│       ├── packaging.md     # uv, pyproject, lockfile, src layout
│       └── security.md      # input validation, secrets, subprocess hygiene
├── stack/          # Stack-scoped: opt-in per repo, version-pinned
│   ├── fastapi.md
│   ├── numpy-scipy.md
│   └── ...
└── task/           # Task-scoped: activated by what you're doing, not what you're touching
    ├── adversarial-review.md
    ├── test-authoring.md
    └── doc-authoring.md
```

`lang/` rules are broadly applicable and travel with the language. `stack/` rules are opt-in (a repo declares its stack; only matching rules activate) and carry the strictest version pins. `task/` rules are usually thin: when a task rule grows a procedure, it graduates into a playbook (skill) and the rule shrinks back to constraints.

### Precedence

When directives conflict across layers, resolution is declared once rather than improvised per incident:

1. Doctrine guardrails (safety, security, destructive-action rules) are inviolable; no narrower rule may relax them.
2. Otherwise, narrower scope wins: a `stack/` rule overrides a `lang/` rule, which overrides doctrine style preferences. Narrower rules encode more specific knowledge of the context, so they are more likely to be right where they apply.
3. `task/` rules constrain only the task they describe and never override structural rules.

A conflict that precedence cannot resolve cleanly is a catalog bug: `ingest` and `audit` must surface it as a forced decision (rewrite one of the rules), never leave it to per-session model judgment.

---

## Per-repository deployment

The catalog is global and canonical, but the artifacts that make `scoped` rules work are repository files: Cursor reads `.cursor/rules/*.mdc` from the project, Copilot reads `.github/instructions/*.instructions.md` from the project, and the repo's `AGENTS.md` is by definition local. Global wiring (cross-harness-config-pattern.md's symlink discipline) cannot reach them. Deployment into repositories is therefore a first-class part of the pattern, with four commitments:

**Copy with provenance, never symlink.** Repo rules must be committable artifacts of the repo: collaborators and CI do not have the catalog, and a symlinked rule would silently vanish for them. Each rendered copy carries a provenance stamp in its frontmatter:

```yaml
provenance: rules/lang/python/testing @ <catalog commit>
```

Provenance makes drift mechanical to detect: `reseed` (see Operations) diffs each repo copy against the catalog version its stamp names, proposes updates, and records intentional divergence instead of overwriting it. This mirrors the rendered-agents discipline from cross-harness-config-pattern.md (generated files committed, drift visible) rather than its symlink discipline. The accepted tradeoff: repos lag the catalog until reseeded, which is the price of portability; `audit` flags stale provenance stamps.

**Detect first, ask second.** Robust coverage comes from inspection rather than interrogation. Seeding begins by detecting what it can: languages from file extensions, stack from `pyproject.toml` and lockfiles, harnesses in use from existing config directories, test framework from imports and config. Only what detection cannot resolve becomes a question, and the questions map onto the seed axes: purpose (library / CLI / service / data-science), strictness posture, and target harnesses when none are detectable. Three or four questions at most, with detected values offered as defaults.

**Selection matrix.** What deploys where is principled rather than decided fresh per repo:

| Content | Deploys to repos? | Reason |
|---|---|---|
| Doctrine | Never | Global, always-on; travels with the harness, not the repo |
| `lang/*` rules | Yes, per detected language | `scoped` activation requires project-level rule files on most harnesses |
| `stack/*` rules | Yes, detected then confirmed | Opt-in by the repo's actual dependencies |
| `task/*` rules, playbooks | Never | `requested`/`invoked` tiers activate by description; global skill wiring suffices |
| Seed `AGENTS.md` | Yes, once | The repo's own context file: template-instantiated, then repo-owned |
| Tool configs (ruff, pyright, pytest, pre-commit) | Yes, once | Part of the seed archetype |

Only `scoped`-tier rules need repo deployment, and only rendered for harnesses whose scoped support is project-level.

**One renderer.** The interview and selection are judgment work and belong in a playbook; the canonical-rule-to-harness-format rendering is deterministic and lives in one shared implementation used by `seed`, `reseed`, and `verify` alike, per cross-harness-config-pattern.md's generator-verifier principle.

---

## Authoring standards

Adopted from the VoltAgent quality criteria and extended; these apply to rules and playbooks alike, and are mechanically lintable:

| Standard | Test |
|---|---|
| Third-person, keyword-rich description stating what and when | Description contains concrete nouns an agent can match against a task |
| Progressive disclosure | Frontmatter ≤ ~100 tokens; body ≤ 500 lines; large resources (schemas, long examples) referenced, never inlined |
| No absolute paths | No machine-specific paths; `$HOME`-style variables or relative paths only |
| Scoped tools | Playbooks declare only the tools they need; no blanket grants |
| One concern per artifact | A rule covering two stacks is two rules; narrow scopes also keep concurrent activation small when several rules match one file |
| Hardened where possible | No prose directive that current tooling can enforce; checkable directives live in tool config with at most a one-line pointer in the rule (see Enforcement pairing) |
| Checkable directives | Each directive is falsifiable against a concrete diff |
| Version pins explicit | Any stack-dependent advice cites the version range it is true for |
| Reviewed date present | Every rule and playbook carries `reviewed:`; audit (see Operations) flags stale ones |
| Diff against default behavior | No directive that restates what the model does unprompted. Model-relative: re-evaluated when the model changes |

These standards are the rule-layer analogue of cross-harness-config-pattern.md's "blocks are universal or they are not blocks": invariants simple enough to verify mechanically, strict enough to keep the catalog healthy.

---

## Enforcement pairing

Everything in this pattern is advice, and advice is open-loop: a rule shifts the probability of compliance but bounds nothing. The only closed-loop elements in the toolchain are deterministic gates: linters, type checkers, test runners, pre-commit hooks, CI, harness permission hooks. Enforcement pairing connects the two: **any directive a machine can check migrates out of prose into a gate; rules retain only what requires judgment.** This is the closest the pattern can get to "make no mistakes."

The migration is a per-directive triage, called hardening:

1. **Classify**: machine-checkable now, partially checkable, or judgment-only.
2. **Map** to the concrete vehicle: a linter rule code, a banned-API entry, a type-checker setting, a pre-commit hook, a CI check.
3. **Verify the gate fires**: write a deliberately violating snippet and confirm the tool catches it before removing any prose. Hardening without this step is deleting advice and hoping.
4. **Handle partial coverage honestly**: "bare assert, never `self.assertEqual`" hardens completely (ruff `PT009`); "no logic between act and assert" does not, because no linter sees intent. Partially coverable directives keep prose for exactly the uncovered residue.
5. **Relocate**: enforced directives land in the seed's tool configs, deploying through the same provenance/reseed mechanism; the rule body shrinks to judgment content plus at most a one-line pointer ("naming and import hygiene are enforced by ruff; do not fight it").

Hardening is never a standing process; it runs at the moments content enters or gets reviewed:

- **Adoption sweep**: one pass over the existing catalog (and doctrine) when the pattern is first implemented.
- **`ingest` and `capture`**: new content is triaged on the way in, so soft directives that could have been gates never accumulate.
- **`audit`**: re-triage, because enforceability is a moving target; linters ship new rule families constantly, so a judgment-only directive from last year may have a rule code today.

The net effect is a one-way flow: prose drains into deterministic config as tooling capability grows, and rules asymptotically approach pure judgment content. A rule trends toward small because its checkable content graduated, never because it was trimmed for length.

For Python the leverage is unusually high. Auditing the appendix rule against current tooling: the banned `@pytest.yield_fixture`, `tmpdir`, and assertion-method patterns are ruff `PT` codes; `os.path` bans are the `PTH` ruleset; deprecated typing aliases are `UP` codes; `shell=True` and secret hygiene are `S` (bandit) codes; NumPy docstring format is the `D` ruleset with `convention = "numpy"`; full annotations are pyright strict mode. Roughly half the rule is expressible as ~15 lines of `pyproject.toml` (see the hardened companion in the appendix).

One caveat, stated plainly: gates act post-generation. The linter does not stop the model writing the bad line; it catches it when the agent runs lint or pre-commit and self-corrects, closing the loop within the session. That is far stronger than advice and weaker than prevention. True write-time prevention (blocking hooks) exists on some harnesses and belongs to the extensions layer, used sparingly.

---

## Python instantiation

The pattern is general; this is the *first* concrete catalog it produces, covering the initial priority areas (coding, documentation, adversarial review, testing) for the first language. It is a worked example of instantiation, never the extent of coverage: further languages, stacks, and lifecycle activities (see the coverage test) enter through `ingest` and `capture` as need arises. Each row is one artifact in the appropriate layer.

### Doctrine (exists; one addition)

`code-style`, `writing-conventions`, `git-conventions`, `execution-guardrails`, tool-routing blocks. Already correct: universal, small, always-on. The single addition is the capture nudge, one sentence: when you correct the same agent mistake twice, propose capturing it.

### Rules (new)

| Rule | Tier / scope | Content sketch |
|---|---|---|
| `lang/python/core` | `scoped` on `**/*.py` | Full type annotations with modern syntax; guard clauses and early returns, happy path last; descriptive names with auxiliary verbs; module and package naming; logging over print; dataclasses/Pydantic over bare dicts at boundaries; anti-hallucination list (e.g. deprecated `typing` aliases, `os.path` where `pathlib` is standard) |
| `lang/python/testing` | `scoped` on test globs | Pytest only; fixtures over setup methods; `parametrize` over loops; `tmp_path` over manual temp handling; one behavior per test, named for the behavior; no inter-test dependence; coverage policy and what not to test; property-based testing (hypothesis) for pure functions with rich input spaces |
| `lang/python/docs` | `scoped` on `**/*.py` + docs globs | NumPy-style docstrings (already doctrine; the rule carries the *full* section-by-section spec so doctrine stays small); examples must be executable; README and API docs updated in the same change as the code they describe |
| `lang/python/packaging` | `scoped` on `pyproject.toml`, lockfiles | uv for environments and installs; `pyproject.toml` as single source of project metadata; src layout; exact-pin lockfile policy; ruff + pyright as the standing lint/type gate |
| `lang/python/security` | `requested` | Validate at system boundaries only; secrets never in code or committed config; `subprocess` without `shell=True`; pinned-dependency audit habits |
| `stack/*` | `scoped`, opt-in per repo | Version-pinned framework rules (FastAPI, NumPy/SciPy, etc.), ingested from community catalogs via the ingest operation as needed |

Tier choices follow the budget principle. `core`, `testing`, `docs`, and `packaging` are `scoped` because their directives bear on essentially every edit to their matching files. `security` is `requested` because its directives concentrate at system boundaries and judgment points; paying for it on every `.py` touch fails the relevance test, while a strong description ("apply when handling user input, secrets, subprocess calls...") gets it loaded at exactly those points.

### Playbooks (new skills)

| Playbook | Invocation | Content sketch |
|---|---|---|
| `adversarial-review` | requested/invoked | Staged passes (correctness → security → tests → docs → style), severity rubric, findings-only output format (no praise), explicit instruction to check directives from active rules, exit criteria, closing capture step (propose a capture for any recurring finding) |
| `test-author` | requested/invoked | Derive cases from the contract, enumerate behaviors in a table before writing code, choose example-based vs property-based per case, verify tests fail before the fix when reproducing bugs |
| `doc-author` | requested/invoked | Docstring coverage pass, executable examples, sync check between code and prose docs, changelog discipline |

### Personas (exist; recomposed)

`critic`, `tester`, `planner`, `executor`, `coordinator` already exist as agents. The change is compositional: persona bodies shed procedure (which moves into playbooks) and domain constraints (which move into rules), keeping only stance, authority, and output contract. The critic persona plus the `adversarial-review` playbook plus the active Python rules together produce a Python adversarial review; swap the rules and the same persona reviews TypeScript.

### Seeds (new)

| Seed | Axis | Contents |
|---|---|---|
| `python-library` | purpose | `AGENTS.md` template (env setup with uv, operating model, typical tasks), rule selection (`lang/python/*`), starter `pyproject.toml` + ruff/pyright/pytest/pre-commit config |
| `python-cli` | purpose | As above, plus CLI conventions (argument parsing, exit codes, stdout/stderr discipline) |
| `python-service` | purpose + stack | As above, plus a stack rule opt-in (e.g. FastAPI) |
| `data-science` | purpose | Notebook hygiene, uv-managed env, data/artifact gitignore policy, experiment logging conventions |

Seeds are classified along the axes from the template-library ecosystem: purpose (what the repo is for), stack (what it is built with), and role (who the agent is acting as, mainly for non-coding seeds like sysadmin contexts).

---

## Operations

Named operations, in the LLM Wiki spirit: each is a workflow an agent executes against the catalog. The catalog is healthy when these run routinely; it rots when they don't.

The operations are self-hosting: each ships as a playbook in the catalog itself (layer 3, with the standard description and tier), except `verify`, which is deterministic Python with no judgment in it. Nothing tells the LLM ambiently how to maintain the catalog; the procedure for an operation enters context only while the operation runs, by the same activation machinery as any other skill. What sets each in motion:

| Operation | Trigger |
|---|---|
| `ingest` | Invoked or requested: "add this source to the catalog" matches the skill description |
| `seed` / `reseed` | Invoked: repo creation, or "bring this repo up to date with the catalog" |
| `promote` / `demote` | Proposed from within `audit` and drift reconciliation; rarely invoked directly |
| `capture` | Embedded as the closing step of review playbooks, plus one standing sentence in doctrine (see `capture`) |
| `verify` | Pre-commit hook and CI; runs on every commit |
| `audit` | Scheduled on a calendar interval, plus event-triggered: a model upgrade or a stack version bump is an audit trigger |

### ingest(source)

Adopt an external artifact (community rule, vendor skill, blog post's checklist) into the catalog:

1. Classify into a layer (doctrine / rule / playbook / persona / seed) and tier.
2. Strip harness packaging; normalize to the canonical schema.
3. Harden: apply the enforcement-pairing triage; any directive that can be a gate enters tool config, never the rule body.
4. Dedupe against doctrine and existing rules: anything the catalog already says is dropped; anything that *contradicts* the catalog forces a decision, never silent coexistence.
5. Pin versions for every stack-dependent claim; set `reviewed:` to today.
6. Record provenance (source URL) in the frontmatter or commit message.

Ingest is also the de-bloat filter: most community rules fail the "diff against default behavior" standard for current frontier models, and ingest is where that content dies instead of entering the catalog.

### seed(repo, axes)

Instantiate agentic infrastructure for a new repository, per the deployment section: detect languages, stack, harnesses, and test framework; ask only the axis questions detection could not resolve; render the selected rules with provenance stamps; instantiate the seed's `AGENTS.md` and tool configs. The repo starts with proven context instead of an empty file.

### reseed(repo)

Propagate catalog improvements to an already-seeded repo: compare each deployed copy against the catalog version its provenance stamp names, present the diff, apply approved updates, re-stamp. Divergence the user keeps is recorded in the stamp (`diverged: true`) so reseed stops re-proposing it. Reseed is also the recovery path when detection inputs change: a new language appears in the repo, a stack dependency is added or dropped.

### promote(artifact) / demote(artifact)

Move content between layers and tiers as evidence accumulates:

- A scoped rule directive needed in every session regardless of language → promote to doctrine.
- A doctrine paragraph relevant only when writing Python → demote to `lang/python/*`.
- A task rule that has grown procedure → extract the procedure to a playbook, demote the remainder.
- Default direction is downward; promotion requires demonstrated cross-session need.

This is the content-layer analogue of cross-harness-config-pattern.md's drift reconciliation: improvements made in the heat of work get deliberately re-homed rather than accreting where they landed.

### capture(failure)

Close the loop from observed agent failures to catalog content. When an agent repeatedly makes the same mistake (a deprecated API, a phantom import, a convention violation review keeps catching), capture it as a directive, usually an anti-hallucination entry in the narrowest rule that covers it. Capture is the highest-value source of anti-hallucination content because it targets the failure modes of *your* models on *your* code rather than the community's, and it is the cheapest form of evaluation the catalog has: a rule earns its place by the failures it stops. A catalog that only ingests is secondhand; a catalog that captures is evidence-based.

Capture's first question is the hardening triage: a mistake a machine can catch becomes a gate, never prose. And because failures are observed mid-work, when no maintenance skill is loaded, capture is wired into the moments failures are visible rather than left to chance: the `adversarial-review` playbook closes with "propose a capture for any recurring finding," and doctrine carries exactly one standing sentence ("when you correct the same agent mistake twice, propose capturing it"). That sentence passes the doctrine promotion test because capture opportunities arise in any session.

### verify()

Mechanical lint of the catalog, runnable in pre-commit alongside the congruence checks from cross-harness-config-pattern.md:

- Schema: required frontmatter fields present and well-formed.
- Budgets: frontmatter and body length within progressive-disclosure limits; doctrine total within its hard ceiling (see Non-goals).
- Hygiene: no absolute paths, no unscoped tool grants, unique names, valid globs.
- Description quality heuristics: third person, contains scope keywords.

### audit()

Periodic (scheduled or prompted) review for semantic staleness, which verify() cannot catch:

- Every rule whose `reviewed:` date exceeds the audit interval gets re-checked against its pinned stack's current state.
- Stack pins compared against what is actually installed in active repos; divergence flags the rule.
- Anti-hallucination lists re-validated: yesterday's banned deprecated API may be today's removed one (drop it) or may have new siblings (add them).
- Provenance stamps in seeded repos compared against the catalog; long-stale stamps flag a reseed.
- Every prose directive re-triaged for hardening: tooling capability grows, and a judgment-only directive from the last audit may have a lint rule now.
- Model upgrades trigger an off-schedule audit. Rules are diffs against a specific model's default behavior, so a new model makes some rules redundant (the defaults caught up; delete them) and opens new failure modes (capture targets moved). Treat a model upgrade exactly like a dependency upgrade.

---

## Integration with the cross-harness spec

This section sketches how the pattern lands in llm-config; the actual migration is follow-up work against cross-harness-config-pattern.md.

- **New canonical directories:** `shared/rules/` (taxonomy as above) and `shared/seeds/`. Both follow the existing canonical-source discipline: bodies are harness-agnostic, frontmatter is rendered.
- **Rules render like agents, not like blocks.** The agent mechanism (canonical body + per-harness frontmatter rendering, driven by registry sub-tables) is the right mechanism for rules: Cursor gets `.mdc` with `globs`/`alwaysApply`, Copilot gets `*.instructions.md` with `applyTo`, harnesses without native scoped rules get the degradation ladder (skill rendering with description-based activation). The registry grows a `[harnesses.<name>.rules]` sub-table declaring the target format and tier-degradation policy per harness. The delivery path then splits by scope: global-capable renderings (degraded skills, global instruction additions) wire through bootstrap as usual, while project-level formats (`.cursor/rules/`, `.github/instructions/`) deploy through `seed`/`reseed`, both paths calling the same renderer.
- **Adding a harness with native rules (e.g. Cursor) is a registry entry**, exactly as cross-harness-config-pattern.md prescribes for any new harness: declare its rule directory, instruction file, and rendering policy; sync and bootstrap pick it up.
- **Playbooks are ordinary skills** and ride the existing skill symlink mechanism unchanged.
- **Seeds and repo deployment are playbook work.** Seeds are never wired into harnesses; `seed` and `reseed` ship as skills (the interview and selection require judgment), and the deterministic renderer they call is a small Python tool shared with `verify()`.
- **verify() extends `tools/verify.py`**; every other operation ships as a playbook riding the existing skill mechanism, per the trigger matrix in Operations. The audit schedule is a harness scheduling feature or a calendar reminder; it needs no infrastructure in this repo.

---

## Non-goals

- **No rule marketplace mirroring.** The community catalogs are quarries, never dependencies; everything enters through ingest or stays out. Vendored rule packs that update upstream are a supply-chain and quality liability.
- **No per-harness rule content.** Rule bodies are byte-identical everywhere, same invariant as blocks. If two harnesses need different *content* (rather than different packaging), it is two rules.
- **No always-on growth by default.** Doctrine carries a hard token ceiling enforced by `verify()`: default 2,500 tokens across all doctrine blocks, tunable per instance, but a number must be declared and linted. Net additions to doctrine require a demotion or removal candidate to be considered first.
- **No procedure in rules, no constraints in playbooks.** The layer boundaries are load-bearing; blurring them recreates the monolith one paste at a time.

---

## Appendix: worked example rule

The canonical `lang/python/testing` rule in full: the anchor for the rule anatomy and the shape `ingest` normalizes external content toward. (The `provenance` stamp shown in the deployment section is added at render time, never authored here.)

```markdown
---
name: python-testing
description: >
  Pytest conventions for Python test suites: structure, fixtures,
  parametrization, naming, and coverage policy. Apply when creating or
  modifying tests, conftest.py, or pytest configuration.
tier: scoped
scope: ["**/test_*.py", "**/*_test.py", "**/tests/**", "**/conftest.py"]
stack: ["pytest>=8", "hypothesis>=6"]
reviewed: 2026-06
---

You are an expert in Python test architecture with pytest.

## Principles

1. A test exists to catch a regression; a test that cannot fail on a real
   bug gets deleted.
2. Tests document behavior: the name states the behavior, the body
   demonstrates it.
3. Independence is absolute: any subset of tests passes in any order.
4. Test code is production code: the same style and review standards apply.

## Structure

- One behavior per test, named for the behavior:
  test_rejects_expired_token, never test_token_2.
- Arrange, act, assert, in that order, separated by blank lines; no logic
  between act and assert.
- Group tests in classes only when they share fixtures, never for
  namespacing alone.
- Test files parallel the source layout: src/pkg/auth.py is tested by
  tests/test_auth.py.

## Fixtures and parametrization

- Fixtures over setup methods or module-level state; narrowest scope that
  works (function scope unless proven otherwise).
- tmp_path and monkeypatch over manual temp dirs and attribute patching.
- pytest.mark.parametrize over loops in test bodies; ids= for non-obvious
  cases.
- conftest.py holds only fixtures used by more than one file.

## Coverage policy

- Cover the contract, the edge cases, and every fixed bug; a regression
  test lands with the fix and is shown to fail before it.
- Do not test framework guarantees, third-party libraries, or trivial
  accessors.
- Property-based tests (hypothesis) for pure functions with rich input
  spaces; example-based otherwise.

## Anti-hallucination

| Banned | Correct |
|---|---|
| unittest.TestCase subclasses in new code | plain pytest functions |
| self.assertEqual and friends | bare assert (pytest introspection) |
| @pytest.yield_fixture | @pytest.fixture (yield is native) |
| tmpdir fixture (py.path) | tmp_path (pathlib.Path) |
| pytest.warns(None) | pytest.warns(SpecificWarning) |
| mutating os.environ directly | monkeypatch.setenv / delenv |
```

### Hardened companion

Enforcement pairing drains the rule's checkable directives into the seed's tool config. The companion `pyproject.toml` fragment for the rule above:

```toml
[tool.ruff.lint]
select = [
  "PT",   # flake8-pytest-style: yield_fixture, tmpdir, assertion methods, parametrize style
  "PTH",  # pathlib over os.path
  "UP",   # deprecated typing aliases and syntax upgrades
  "S",    # bandit: shell=True, hardcoded secrets
  "D",    # pydocstyle
  "TID",  # banned-api enforcement
]

[tool.ruff.lint.pydocstyle]
convention = "numpy"

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"unittest.TestCase".msg = "Use plain pytest functions"

[tool.pyright]
typeCheckingMode = "strict"
```

With the companion deployed and its gates verified to fire, the entire anti-hallucination table and parts of the fixtures section would drain from the rule's prose at the next audit; the rule is shown pre-hardening above so the anatomy is visible in one place. What survives hardening is the judgment residue: one behavior per test, names stating behavior, arrange/act/assert discipline, and the coverage policy.
