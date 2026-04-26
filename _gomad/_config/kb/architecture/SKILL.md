---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Architecture Pack Overview

This pack is a pragmatic reference for structural decisions in application codebases — how to draw the boxes, where to place the lines between them, and when a given style is actually worth its indirection cost. Like the testing pack it shares this domain-kb space with, it is broad-shallow rather than narrow-deep: short subtopic files on the decisions that come up most often, not a textbook.

## When to use this pack

Reach for a file from this pack when you are:

- Structuring a new service and deciding between a flat file layout, layered architecture, or a port-and-adapter shape.
- Picking a module boundary for a new feature inside an existing application, especially when the wrong boundary would force a cross-cutting refactor later.
- Deciding whether to add an event-driven path, an asynchronous queue, or a second service — or whether the current monolith is perfectly fine.
- Designing an API surface and weighing REST, RPC, and GraphQL for a specific use case.
- Reviewing a design proposal and wanting a short, opinionated checklist of architectural smells to look out for.

If the question is "how do I test this?", load `../testing/SKILL.md` first and come back when the architectural decision is in focus.

## What's in this pack

- `anti-patterns.md` — Eight common structural mistakes and how to avoid each one.
- `reference/layered-architecture.md` — The dependency-direction rule and when layers pay off.
- `reference/hexagonal.md` — Ports and adapters, what "the core" means in practice, and where the overhead bites.
- `reference/modular-monolith.md` — Strict internal boundaries inside a single deployable, and the extract-to-service evolution path.
- `reference/event-driven.md` — Event shape, idempotency, debugging cost, and when the pattern is worth adopting.
- `reference/api-design.md` — Resource vs RPC shape, versioning, error contracts, pagination, and idempotency keys.
- `examples/layered-node-app.md` — A concrete directory layout for a layered Node.js service with a walked-through GET flow.
- `examples/hexagonal-port-adapter.md` — A `UserRepository` port with Postgres and in-memory adapters, wired at the edge.

## Principles the pack leans on

- **Dependency inversion by default.** Inner layers depend on abstractions; outer layers supply implementations. Direction matters more than layer count.
- **Explicit boundaries.** A module boundary that lives only in someone's head is not a boundary. Enforce it with file layout, linter rules, or the language's visibility system.
- **Avoid speculative abstraction.** Three concrete implementations suggest an interface. One concrete implementation with "maybe we'll need a second" is usually premature.
- **Match the architecture to the load-bearing risk.** For a CRUD app with one database, layered is fine. For a system with multiple infrastructure backends and tight testing requirements, hexagonal pays off. For a suite of related domains that share operational context, a modular monolith beats a distributed one.

## Not covered here

Database schema design, security architecture, infrastructure-as-code patterns, service mesh topology, and observability-driven design decisions are out of scope for this pack. They each deserve their own focused material when they become the binding constraint.
