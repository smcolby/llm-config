---
name: two-pass-development
description: >
  Two-pass development workflow with multi-persona criticism and
  human-in-the-loop approval: plan, approve, implement, test, adversarial
  critique, refine, approve, finish. Use for rigorous feature work, when
  asked for a plan-implement-critique cycle, or when acting as the
  Coordinator persona.
reviewed: 2026-06
---

# Two-Pass Development Workflow

A strict two-pass subroutine with persona switching and user-approval gates. The orchestrating stance (persona discipline, bias mitigation) comes from the Coordinator persona; persona stances come from their agent definitions; this skill supplies the procedure.

## Tool authority per persona

* **Read-only personas** (Planner, Critic, domain reviewers): read and search tools only; never edit files or execute state-changing commands.
* **Write/execute personas** (Executor, Tester): edit, write, and execute tools as the step requires.

## Pass 1: Initial implementation

1. **[PLANNER]** Analyze the request, search the codebase, and produce a step-by-step implementation architecture mapping the exact files to be created or modified.
2. **USER REVIEW:** Present the plan. **STOP AND WAIT FOR EXPLICIT APPROVAL.** Do not write code yet.
3. **[EXECUTOR]** Write the code exactly as planned; no scope creep.
4. **[TESTER]** Run the relevant test suites. On failure, route the stack trace back to the Executor and iterate until passing.

## Pass 2: Critique and refinement

5. **[CRITIC]** Audit the new codebase state per the Critic persona (adversarial-review skill + active rules). For domain-heavy changes, run the matching domain reviewer alongside: Machine Learning Expert for training loops and model architecture, Chemoinformatician for molecular data pipelines, Biologist for binding, inhibition, and cellular-assay interpretation, Medicinal Chemist for SAR and bioactivity data.
6. **[PLANNER]** If rejected, produce a Refinement Plan addressing the exact failures cited.
7. **USER REVIEW:** Present the Refinement Plan (or the clean bill of health). **STOP AND WAIT FOR EXPLICIT APPROVAL.**
8. **[EXECUTOR + TESTER]** Apply the approved refinements and re-test.

## Rules of engagement

* Do not skip steps and do not proceed through a user gate without explicit approval.
* Each persona judges only the artifacts in front of it: the Critic reviews the code as found, never the Executor's stated intentions.
* If a pass loops more than twice without converging, stop and surface the impasse to the user instead of iterating further.
