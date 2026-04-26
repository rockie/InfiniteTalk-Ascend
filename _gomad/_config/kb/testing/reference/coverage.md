---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Coverage Metrics

## What coverage measures

Line coverage reports the percentage of executable lines visited by at least one test. Branch coverage reports the percentage of conditional arms (both sides of each `if`, each `case`, each `?:`) visited by at least one test. Neither metric says anything about whether the tests *assert* the right behaviour — a test that runs the code but makes no meaningful assertion still counts as coverage.

Treat coverage as a proxy, not a goal. A high number with weak assertions is worse than a moderate number with strong ones, because it creates false confidence.

## Reasonable targets

- **Domain logic** (business rules, calculations, validation, parsers): 90 %+ line and branch coverage. These are the files where bugs cost real money; they also tend to be pure functions, which are cheap to test.
- **Glue code** (HTTP handlers, CLI entry points, wiring modules): 60–80 % is usually enough. These files are mostly string assembly and dependency lookup; the interesting logic has been extracted downward.
- **Security-sensitive code** (auth token issuance, permission checks, cryptographic primitives used to build higher-level abstractions): 100 % line and branch. Any uncovered branch is a potential bypass. Pair coverage with property-based tests where possible.
- **Generated code, third-party vendor directories, and migration scripts**: exclude from the coverage report entirely. Including them drags the total and tempts people to write meaningless tests to satisfy the threshold.

Set per-directory thresholds rather than one global number. A single global 80 % lets the domain layer drift down into 60 % while UI glue sits at 95 % — the exact opposite of what you want.

## Pitfalls to watch for

- **Coverage-maximising tests.** Someone notices a branch at 0 % coverage and writes a test that executes the branch without asserting on anything. Coverage goes up; bug-catching does not.
- **Ignoring the failure mode.** A line can be "covered" because it was reached with valid input, while the invalid-input branch that matters is never exercised. Branch coverage helps here; complete-path coverage would help more but is expensive to maintain.
- **Treating 100 % as aspirational for the whole codebase.** Past about 90 %, each additional percent costs disproportionately more effort and usually covers increasingly exotic paths. The team's time is better spent on stronger assertions in existing tests.

## What coverage reports are actually useful for

Two things, both reviewed manually rather than gated in CI:

- Spotting whole files that dropped to zero coverage. Usually means the test file was deleted, or the module moved and its tests did not follow.
- Spotting regression patterns inside a file — coverage on the happy path, none on the error path. That is a concrete prompt for the next test to write.

Use the numbers as conversation starters, not as success criteria. Code review judgement on whether a test actually catches regressions will always matter more than the percentage next to the file name.
