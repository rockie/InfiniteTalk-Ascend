---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Testing Anti-Patterns

A short list of testing mistakes that show up repeatedly in real codebases. Each one includes a one-line replacement so you can course-correct quickly.

## Anti-pattern 1: Testing implementation details

Asserting that a private method was invoked, or that the code took a particular internal path, couples the test to the current implementation. Any refactor that preserves behaviour still breaks the test, which teaches the team that tests are an obstacle rather than a safety net.

**Replace with:** assertions on observable output — the return value, the state of an injected collaborator, or the contents of a persisted record.

## Anti-pattern 2: Mocking code you own

Stubbing your own modules to "isolate" a test hides real integration bugs. If the test passes but the integrated code breaks, the test was not protecting anything useful.

**Replace with:** letting your own code run end-to-end within the test's scope, and mocking only at the edges where I/O, randomness, or time cross your process boundary.

## Anti-pattern 3: Shared mutable fixtures

Tests that read and write a module-scoped fixture order-depend on each other. They pass in isolation, pass in the original order, and fail when a test runner re-shuffles them or runs a subset.

**Replace with:** per-test setup that builds a fresh fixture each time, or an explicit factory function that returns a new instance on every call.

## Anti-pattern 4: Sleep-based waits in asynchronous tests

`await sleep(500)` is a confession that the test does not know what it is waiting for. Fast machines pass; slow CI runners fail at 2 a.m.

**Replace with:** an explicit condition wait — poll for a predicate, await a specific promise, or use the framework's built-in "wait for element / wait for event" helpers with a time budget.

## Anti-pattern 5: Snapshot tests covering volatile output

Snapshotting generated HTML, ISO timestamps, UUIDs, or console output produces a test that flips between green and red based on incidental details. Reviewers stop reading the snapshot diff and rubber-stamp the update, which defeats the point.

**Replace with:** targeted assertions on the fields that matter, with a snapshot only for stable structural output (a normalised AST, a canonicalised config shape).

## Anti-pattern 6: One giant E2E suite that blocks every deploy

A suite that takes forty minutes and fails flakily on 5 % of runs ends up being bypassed. Teams add `--no-verify` or skip the job under deadline pressure, and then the suite catches nothing.

**Replace with:** a small, trusted, critical-path E2E suite that runs in under five minutes, plus a broader nightly suite that is allowed to fail-and-ticket rather than block.

## Anti-pattern 7: Assertion-less tests

A test body that exercises code but never calls `expect` or `assert` passes whenever the code does not throw. It reports as "covered" while proving nothing about correctness.

**Replace with:** at least one assertion that distinguishes correct from incorrect output. If there is nothing to assert, there is nothing to test — delete the test.

## Anti-pattern 8: Chasing 100 % line coverage

Teams occasionally adopt "100 % line coverage" as a proxy for "high-quality tests". The result is usually shallow tests that execute every branch without meaningfully checking behaviour — often written to satisfy the threshold rather than to catch bugs.

**Replace with:** a per-module target (higher for domain logic, lower for glue code) and a secondary check that new tests contain real assertions. Coverage is a floor, not a ceiling, and never a goal on its own.
