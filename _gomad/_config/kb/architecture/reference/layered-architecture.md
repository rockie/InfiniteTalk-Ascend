---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Layered Architecture

## Typical layers

A layered architecture divides the codebase into horizontal layers, each with a well-defined responsibility:

- **Presentation** — receives input from the outside (HTTP requests, CLI args, UI events), validates shape, and renders responses. No business decisions live here.
- **Application** — orchestrates work across the domain to satisfy a use case. Coordinates transactions, calls into domain services, and hands the result back to the presentation layer.
- **Domain** — the business rules. Entities, value objects, invariants, and the vocabulary the team uses when they talk about the problem. This layer does not know about HTTP, databases, or message queues.
- **Infrastructure** — concrete implementations of I/O concerns. Database drivers, HTTP clients for third parties, filesystem operations, clock access.

Not every codebase needs four layers. Three (presentation / application+domain / infrastructure) is more common in practice, and two (presentation / everything else) is enough for a small CRUD app.

## The dependency rule

Layered architecture is *only* useful if the dependency direction is enforced. The rule: **outer layers depend on inner layers, never the reverse.** Presentation may import from application and domain; domain may not import from presentation or infrastructure.

Dependency inversion handles the awkward cases. When the domain needs to persist an entity, it defines an interface (say, `OrderRepository`) that describes *what* it needs. The infrastructure layer provides a concrete implementation that satisfies the interface. The domain depends on the abstraction; the infrastructure depends on the domain's abstraction. No cycle.

If the compiler, the linter, or the test suite cannot tell you when the rule is violated, it will be violated — usually quietly, under deadline pressure. Enforce it with tooling: allowed-imports rules, module visibility settings, or a custom check in CI.

## When a layered architecture is a good fit

- CRUD-dominant applications where the business logic is shallow and most features follow a similar "read request → validate → mutate state → render response" shape.
- Teams new to domain-driven design who benefit from the training wheels of a clear "where does this code belong?" answer.
- Codebases where most of the accidental complexity lives in I/O, not in the business rules themselves.

## When to prefer something else

- Highly decoupled modules that should evolve independently — a modular monolith with per-module layering is often a better fit.
- Plugin-style extensibility where the application is a thin framework and most of the interesting behaviour lives outside the core — hexagonal architecture expresses this more cleanly.
- Strongly event-driven systems where the primary abstraction is the message, not the call — a layered shape fights the grain.

## Common mistakes

- **Letting ORMs leak upward.** The moment a route handler receives an entity whose lazy-loaded relationship triggers a database query during rendering, the layers have merged. Map to a plain DTO at the application boundary.
- **Putting HTTP status codes in the application layer.** `throw new NotFoundError()` inside a domain service couples the domain to a transport decision. Throw domain-specific errors; translate to HTTP in the presentation layer.
- **A "utilities" or "shared" folder that everything depends on.** The dumping ground breaks the dependency rule. Either the code belongs in a specific layer, or it should live in its own small, focused module.
