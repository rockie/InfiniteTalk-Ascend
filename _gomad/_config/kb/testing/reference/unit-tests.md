---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Unit Tests

## Scope

A unit test exercises a single function, method, or class in isolation from I/O, the clock, the network, and any durable state. If the test needs a filesystem, a database, a socket, or a spawned process to run, it is no longer a unit test — that is an integration test, which has different trade-offs and a different place in the pyramid.

## Structure

Use the Arrange–Act–Assert shape. A blank line between the three phases makes the intent scannable:

- **Arrange** — build the input, the collaborator fakes, and the initial state.
- **Act** — make exactly one call to the function under test.
- **Assert** — check the return value and any observable side effect.

Tests with two Act steps usually describe two different behaviours; splitting them into two tests is almost always the right move.

## When to write a unit test

Write a unit test for every pure function that has branching logic, input validation, or a non-trivial return type. Examples include a tax calculator, a parser, a predicate used in filtering, a reducer, or any function with an `if`, `switch`, `?:`, or early return.

Also write one whenever you are fixing a bug. The regression test locks the correct behaviour in place before the fix, which proves the fix actually changes behaviour rather than just coincidentally not throwing.

## When to skip a unit test

- Trivial getters and setters that do nothing but return a field.
- Framework-generated boilerplate, route wiring, or dependency-injection scaffolding with no behaviour of its own.
- Thin adapters that only forward a call to another well-tested layer.

If you are unsure whether the code is trivial, try to write the test. If the test body turns out to be "call the function, assert it returned the same argument back", you have your answer.

## Naming

A readable unit test name answers three questions: what is under test, what happens, and under what condition. A convention that works in most frameworks:

```
describe('Calculator', () => {
  it('returns 0 when no operands are provided', () => { ... });
  it('returns the sum when two positive integers are provided', () => { ... });
  it('throws RangeError when the sum would overflow MAX_SAFE_INTEGER', () => { ... });
});
```

Avoid `it('works')`, `it('handles input')`, and `it('does the thing')`. A failing test with a vague name forces the reader to open the body; a failing test with a specific name often tells you what regressed from the failure message alone.

## Fast feedback

Unit tests should run in milliseconds. If a single unit test takes more than ~100 ms, look for accidental I/O (a real file read, an HTTP client that resolves DNS, a real timer) before assuming the code is slow. Fast unit tests are the reason you can run them on every save; the moment they become slow, people stop running them.
