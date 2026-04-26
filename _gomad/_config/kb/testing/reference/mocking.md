---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Mocking Strategies

## When to mock

Mock at the edges of your process. Good candidates:

- **External I/O** — HTTP clients, database drivers, message queue clients, file-system reads/writes of real files.
- **The clock** — code that asks the OS for the current time, or schedules work for later.
- **Randomness** — UUID generators, secure-token generators, any source of entropy your test wants to pin down.
- **Environment-derived values** — process arguments, environment variables, feature flags retrieved from a remote source.

The common thread: anything that makes the same code return a different answer on two runs is a candidate for a test double.

## When not to mock

Do not mock code you own. A service that calls a helper function should be tested with the real helper running — otherwise the test proves only that the two modules can be wired together, not that the wiring is correct. If the helper itself is expensive, refactor it so the expensive part is at the edge, then mock the edge.

Do not mock pure functions. `parseDate`, `formatCurrency`, `hashPassword` — these have no side effects and no dependencies, so there is nothing to stand in for. If you find yourself mocking a pure function, you are probably trying to dodge a failing assertion rather than write a better test.

Do not mock trivial value objects. A mock for a `Point { x, y }` struct is almost always longer than the struct itself and adds nothing.

## Mock vs stub vs fake

The words get used interchangeably in the wild; pick one set of definitions and stick with them inside your codebase.

- **Stub** — returns a canned value for a specific call, with no behaviour of its own. `stub(api, 'fetchUser').returns({ id: 1 })`. Useful for controlling inputs into the code under test.
- **Mock** — a stub plus recorded call information. Lets you assert that a specific function was called with specific arguments. Useful for verifying outbound effects (e.g. "we sent a receipt email").
- **Fake** — a working in-memory implementation of a real dependency. An `InMemoryUserRepository` that stores users in a `Map` and implements the full `UserRepository` interface is a fake. Heavier to build than a stub but often dramatically easier to reuse across tests.

Prefer fakes when the dependency has enough behaviour that building one fake pays off over many tests. Prefer stubs when you only need to control a single call.

## Verification — state over interaction

An assertion like "we called `emailService.send` with arguments X" is an *interaction* assertion. It is fragile: any refactor that keeps the behaviour correct but calls a slightly different method will break the test.

Prefer *state* assertions where the mock behaves as a fake: "after calling `signup`, the in-memory outbox contains one email addressed to `alice@example.com`". This is easier to read, easier to refactor under, and catches real bugs (missing email, wrong recipient) rather than incidental ones.

Use interaction assertions sparingly — only when the side effect has no observable state (e.g. a fire-and-forget metric).

## Two common pitfalls

- **Over-mocking.** A test with ten mocks and no real code running tests the mocks, not the code. If the test body is longer than the code under test, reconsider.
- **Divergent mocks.** A stub that returns `{ id: 1, name: 'x' }` when the real API returns `{ id: 1, name: 'x', email: 'e' }` will pass locally and break in production the moment the new field matters. Generate mocks from the same schema as the real client, or pin them to a snapshot of real traffic, to keep them honest.
