---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Testing Pack Overview

This pack gives a coding agent practical, opinionated reference material for writing and organising automated tests in a typical application codebase. It is deliberately broad-shallow: short subtopic files covering the decisions that come up most often, rather than a single long treatise.

## When to use this pack

Load a file from this pack when you are:

- Deciding whether a new piece of code should be covered by a unit test, an integration test, or an end-to-end test.
- Picking a mocking strategy and need to know which dependencies are worth mocking versus running for real.
- Diagnosing a flaky test and deciding whether the cause is the test, the code under test, or the environment.
- Choosing an E2E framework for a web UI or a CLI tool, and wanting a short set of reasonable defaults.
- Debating a coverage target with a collaborator and needing a grounded position on what the number actually means.

If you are architecting a whole module, prefer `../architecture/SKILL.md` first and come back here once you know where the seams will be.

## What's in this pack

- `anti-patterns.md` — Seven concrete testing mistakes and the single-line replacement for each.
- `reference/unit-tests.md` — Scope, structure, and naming for isolated function-level tests.
- `reference/integration-tests.md` — Module-boundary testing, database strategies, and fixture choices.
- `reference/e2e-tests.md` — Scope discipline, framework picks, and flakiness mitigation for end-to-end suites.
- `reference/mocking.md` — When to mock, when to let real code run, and how to avoid over-specifying behaviour.
- `reference/coverage.md` — What line coverage does and does not tell you, with sensible per-module targets.
- `examples/jest-setup.md` — Minimal Jest config for a CommonJS Node project, with an original worked example.
- `examples/playwright-e2e.md` — A Playwright skeleton with an invented login-flow scenario for a Node web app.

## Conventions

- Test files live next to the code they cover when the codebase uses colocated tests (e.g. `foo.js` + `foo.test.js`), or under a sibling `__tests__/` directory when the project prefers grouping.
- One logical behaviour per test. If the test description uses "and", split it into two.
- Tests describe behaviour, not implementation. The phrase "it should call the method" is almost always a smell; "it should return the total including tax" is almost always better.
- Use `describe` to name the unit under test; use `it` to name the observable behaviour for a specific input or state.

## Not covered here

Load tests, performance benchmarks, security fuzzing, mutation testing, and contract testing between services are outside this pack's scope. They each benefit from their own reference material once they become load-bearing for the project.
