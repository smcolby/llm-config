---
name: catalog-ingest
description: >
  Adopt external content (community rules, vendor skills, blog checklists,
  style guides) into the enchiridion catalog: classify, normalize, harden,
  dedupe, pin, and record provenance. Use when asked to add a source,
  rule set, or best-practices document to the catalog.
reviewed: 2026-06
---

# Catalog Ingest

Procedure for bringing external content into the catalog. The catalog lives in the enchiridion repository (resolve it via the real path of this SKILL.md). Most external content should die here rather than enter; ingest is the de-bloat filter.

## Procedure

Apply per candidate directive or artifact, not per source document:

1. **Classify** into a layer and tier:
   - Universal behavior needed every session → doctrine block (`shared/blocks/`). Rare; requires a demotion candidate since doctrine has a hard token ceiling.
   - Scoped guidance keyed to language/stack/files → rule (`shared/rules/lang|stack|task/`).
   - Multi-step procedure → playbook (`shared/skills/`).
   - Stance for delegated work → agent (`shared/agents/`).
   - Repo-creation material → seed (`shared/seeds/`).
2. **Strip and normalize**: remove harness packaging (cursorrules headers, vendor framing); rewrite to the canonical schema and the catalog's voice. For rules: frontmatter `name`, `description` (third person, what + when, matchable keywords), `tier`, `scope`, `stack`, `reviewed`.
3. **Harden** (enforcement-pairing triage):
   - Classify each directive: machine-checkable now, partially checkable, judgment-only.
   - Map checkable ones to a concrete gate (ruff rule code, banned-api entry, pyright setting, pre-commit hook) and put the gate in the seeds' tool configs, never in rule prose.
   - Verify the gate fires: write a violating snippet, confirm the tool catches it, then drop the prose (keep at most a one-line pointer).
   - Partially checkable directives keep prose for exactly the uncovered residue.
4. **Dedupe and reconcile**: anything doctrine or an existing rule already says is dropped. Anything that contradicts the catalog forces a decision now (rewrite one side); never let contradictions coexist.
5. **Filter against default behavior**: drop every directive that merely restates what the current model does unprompted. If unsure, test with a quick generation. Most community content dies at this step; that is the step working.
6. **Pin and stamp**: version-pin every stack-dependent claim in `stack:`; set `reviewed:` to the current month; record the source URL in the commit message.

## Close out

Run `python tools/sync.py --rules --apply` and `python tools/verify.py` from the repo root; commit the canonical files and any regenerated router index together, citing the source.
