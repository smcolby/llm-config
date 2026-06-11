---
name: doc-author
description: >
  Procedure for writing and maintaining Python documentation: docstring
  coverage passes, executable examples, syncing prose docs with code, and
  changelog discipline. Use when documenting an API, updating a README,
  or bringing docs in line with changed code.
---

# Doc Author

Procedure for documentation work. Format conventions (NumPy docstring sections, type phrasing, example style) come from the python-docs rule; this skill supplies the workflow.

## 1. Inventory the surface

List the public surface in scope: modules, classes, functions someone outside the package can reach. For a change-driven docs pass, the surface is everything the change touched plus anything whose documented behavior the change altered.

## 2. Docstring pass

For each item in the surface, in order:

1. Missing docstring on public item: write it (contract, not implementation).
2. Existing docstring vs current signature and behavior: fix every disagreement; a wrong docstring outranks a missing one as a defect.
3. Sections per the python-docs rule: summary line, Parameters, Returns, Raises as applicable; loose readable types in prose, precise types in the signature.

## 3. Examples pass

- Every `Examples` section must execute as written; run them (doctest or copy into a scratch session). An example that errors is a bug to fix now, not to annotate.
- Prefer one realistic example over several trivial ones; add an edge-case example only when it changes how the API is used.

## 4. Prose sync pass

- README: does the install story and first-success path still work as written? Run the commands if the change plausibly affected them.
- Generated API docs, tutorials, and architecture notes that mention the changed surface: update in the same change.
- Changelog: one user-facing entry per behavior change, written for the user (what changed, why it matters); skip internal refactors.

## 5. Close out

Docs land in the same commit or branch as the code they describe; never as a follow-up promise. If the same documentation defect keeps recurring across sessions, propose a capture into the python-docs rule.
