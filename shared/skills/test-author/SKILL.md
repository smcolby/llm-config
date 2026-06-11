---
name: test-author
description: >
  Procedure for authoring Python test suites: derive cases from the
  contract, enumerate behaviors before writing code, choose example-based
  vs property-based strategies, and prove regression tests fail before the
  fix. Use when writing new tests, adding coverage, or reproducing a bug.
reviewed: 2026-06
---

# Test Author

Procedure for writing tests worth keeping. Conventions (fixtures, parametrize, naming, structure) come from the python-testing rule; this skill supplies the workflow.

## 1. Derive the contract

Before writing any test, state what the unit promises: inputs it accepts, outputs it guarantees, errors it raises, invariants it holds. If the contract is unclear from signatures and docstrings, that is the first finding; clarify it before testing it.

## 2. Enumerate behaviors

Build a behavior table before writing code:

| Behavior | Input class | Expected | Strategy |
|---|---|---|---|
| rejects expired token | expired JWT | raises AuthError | example |
| round-trips any valid config | arbitrary valid dict | parse(dump(x)) == x | property |

Cover: the contract's happy paths, each documented error, boundary values (empty, single, maximum), and every previously fixed bug in the area. Mark rows that framework guarantees or third-party libraries already cover, and delete them; do not test other people's code.

## 3. Choose the strategy per row

- **Example-based** (plain pytest + parametrize) for specific documented behaviors and error paths.
- **Property-based** (hypothesis) for pure functions with rich input spaces: round-trips, invariants, oracle comparisons. One property test replaces a page of examples.
- **No mocks for what you own**: prefer real objects and `tmp_path`; mock only true boundaries (network, clock, subprocess), with `autospec=True`.
- **Search before doubling**: before writing any mock, stub, or new fake, search the repo (`conftest.py`, test utilities, existing tests) for a lightweight real implementation or existing fake (a baseline model, an in-memory backend) and use it instead. The repo's own cheap real path beats any double.

## 4. Write and verify the tests themselves

- One behavior per test, named for the behavior, arrange/act/assert per the testing rule.
- Every new test must be seen to fail: for regression tests, run against the unfixed code (stash the fix or check out the parent commit) and confirm failure before confirming the fix passes. For new-feature tests, sabotage the assertion once if there is no unfixed state to run against.
- A test that cannot be made to fail is deleted, not committed.

## 5. Close out

- Run the full affected test set, not just the new tests; fix any order dependence you introduced.
- If you caught yourself repeating a past testing mistake, propose a capture into the python-testing rule.
