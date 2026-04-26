---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Integration Tests

## Scope

An integration test exercises more than one unit together — typically a module boundary where the interesting behaviour lives. Examples include an HTTP handler that parses a request, calls a service, and persists to a database; or a repository method that issues a real SQL query against a test database.

The rule of thumb: use real dependencies when they are cheap, deterministic, and fast to set up. Substitute them when they cross a process boundary you do not control (external HTTP APIs, paid services, cloud infrastructure, user email inboxes).

## Database strategy

Two patterns cover almost every case.

**Per-test transaction rollback.** Each test opens a transaction in its setup, runs the code under test, makes its assertions, and rolls the transaction back in its teardown. No test commits. This is fast, does not require seed data to be reset, and isolates tests from each other cleanly. It does not work for code that relies on committed visibility across connections — most CRUD code is fine.

**Per-suite seed and per-test truncate.** On suite start, run migrations and load a fixed seed. Each test truncates the relevant tables in its setup. This is slower than transaction rollback but handles code paths that must see committed data. Pair it with disciplined fixture building so tests do not accidentally rely on previous-test leftovers.

Whatever pattern you pick, avoid depending on rows that a previous test created. That is the `shared mutable fixture` anti-pattern in a different outfit.

## External API strategy

- **Record/replay** — run the real API once, record the HTTP traffic (there are libraries for most stacks), and replay it on subsequent runs. Keeps tests deterministic; catches schema drift when you re-record on a schedule.
- **Sandbox environments** — some providers (payment processors, email gateways) offer sandbox endpoints that accept the same requests as production and return synthetic responses. Prefer this for code paths that depend on realistic response shapes.
- **Hand-rolled fakes** — implement the smallest possible in-process fake of the remote service. Cheap and fast, but drifts out of sync with the real API, so pair it with a small smoke test that hits the real service on a schedule.

Avoid hitting the live external API in normal CI runs. It turns every unrelated CI failure into a three-way debug between your code, the network, and someone else's uptime.

## Fixtures vs factories

Static fixtures (a JSON file of test users, a SQL dump) are readable but rot quickly and become load-bearing in surprising ways. Factories (functions that build an object with sensible defaults and accept overrides for the relevant fields) tend to age better:

- Each test declares the attributes it actually cares about.
- Schema changes flow through one factory rather than N fixture files.
- New tests become short and readable — "a user with `role: 'admin'`" rather than "whatever was in `seed-users.json`".

Use fixtures for bulk reference data that the code assumes exists (e.g. the 50 ISO country codes). Use factories for everything else.

## When to prefer an integration test over an E2E test

If the behaviour lives in one service and the E2E version would cost you a browser, a real network hop, and a multi-step login flow, the integration test is almost always the better buy. Reserve E2E tests for flows that genuinely cross the whole system, and cover the rest at the integration layer.
