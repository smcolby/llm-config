---
name: adversarial-review
description: >
  Staged adversarial code review: correctness, security, tests, docs, and
  style passes with a severity rubric and findings-only output. Use when
  reviewing a diff or pull request, auditing recent changes, or acting as
  the Critic persona.
reviewed: 2026-06
---

# Adversarial Review

A staged review procedure. The reviewer's stance (adversarial, findings-only, verdict contract) comes from the Critic persona; domain constraints come from the active coding rules; this skill supplies the procedure.

## Setup

1. Establish the review surface: the diff, branch, or file set under review. Review what changed plus anything the change makes stale (callers, docs, tests of changed behavior).
2. Load the rule index (`rules` skill) and read every rule whose scope matches files in the review surface. Each rule directive is a check.

## Passes

Run in order; do not merge passes. Note findings as you go, with file and line references.

1. **Correctness** — does the change do what it claims? Trace the happy path and every branch. Hunt: off-by-one, None/empty handling, error paths that swallow, state mutations with non-local effects, concurrency assumptions.
2. **Security** — apply the python-security rule (or language equivalent) even when not auto-scoped: boundary validation, secrets in code or logs, subprocess and deserialization safety, injection surfaces.
3. **Tests** — do tests exist for the changed behavior, do they comply with the testing rule, and would they fail if the change were reverted? A test that cannot fail is a finding. Tautological tests, unbound mocks, and inter-test dependence are findings.
4. **Docs** — docstrings present and accurate for changed public surface, examples still execute, prose docs and changelog updated in this change if behavior moved.
5. **Style and rules sweep** — remaining directives from active rules and doctrine not covered above. Do not re-litigate what a configured linter already enforces; a passing gate is a passed check.

## Severity rubric

| Severity | Meaning |
|---|---|
| blocker | Incorrect behavior, data loss, security hole, or a test that lies |
| major | Violates a rule directive or contract; works today, costs soon |
| minor | Worth fixing, does not endanger correctness |
| nit | Style residue not caught by a gate; batch these, never block on them |

## Output

- Findings only, ordered by severity: `severity | file:line | what is wrong | which rule/pass it violates`. No praise, no restating what is fine.
- When acting as the Critic, follow with the enumerated `[YES]`/`[NO]` check list and the verdict per the persona contract.

## Exit criteria

The review is complete when every pass has run over every file in the surface and every finding has severity, location, and a violated check named. If the surface was too large to review honestly, say so and name what was skipped; never silently sample.

## Closing capture step

Before finishing: for any finding you have made before (same mistake, different day), propose a capture: a new directive (anti-hallucination entry where applicable) in the narrowest rule that covers it, or a lint gate if a machine could have caught it. One sentence per proposal; the user decides.
