---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Modular Monolith

## Concept

A modular monolith is a single deployable — one process, one binary, one build artefact — divided internally into strict modules that behave as if they were separate services. Each module owns its data, exposes a narrow public API to the others, and keeps its internals truly private. The system ships as one unit, but the team works on it as if the pieces were loosely coupled.

The phrase is a deliberate answer to the binary of "monolith vs microservices". It says: most of the benefits people want from microservices — clear ownership, domain isolation, independent reasoning — can be had without the operational weight of a distributed system.

## The module contract

The shape that makes a modular monolith work:

- **Public API.** Each module exports a small set of entry points — use-case functions, command handlers, or an interface — that other modules are allowed to call. Everything else is private by convention and, where possible, by tooling.
- **Private internals.** Helper functions, internal data structures, database tables owned by the module. No other module references these directly.
- **Owned storage.** Each module owns its database tables (or its own schema). Cross-module reads go through the owning module's public API, not through the database.
- **Typed events (optional).** When modules need to react to each other asynchronously, they communicate via events defined in a shared event contract, not by reaching into each other's code.

Enforce the contract with whatever tooling your ecosystem offers: import-path restrictions, package visibility, architecture-test suites (e.g. "no file under `billing/internal/` may be imported from outside `billing/`").

## Why a modular monolith, not microservices

- **Operational simplicity.** One deployable means one set of logs, one database connection pool, one health check, one migration pipeline. The operational surface area scales slowly with the team.
- **Transaction boundaries are cheap.** Cross-module operations that need to be atomic can use a single database transaction. The same operation across two services requires sagas, outbox patterns, or compensating actions — all of which have their own failure modes.
- **Low latency between modules.** A function call is nanoseconds. An HTTP hop is milliseconds. If the modules talk to each other a lot, the network cost adds up fast.
- **Low cost of rearranging boundaries.** If a module boundary turns out to be wrong, moving the code is a refactor. In microservices, the same mistake requires coordinated deploys and data migrations.

## Where it breaks down

The monolithic shape starts to hurt when:

- A single module has a genuinely different scaling profile from the rest (e.g. a batch job that needs 8× the CPU of the web tier for three hours a night).
- Different modules have different availability requirements and you do not want one module's incident to take down the others.
- Separate teams need to deploy independently and the joint release cadence becomes a bottleneck.

At that point, extract the module. Done right, the extraction is straightforward: the public API is already a small, typed surface; the database tables are already in a dedicated schema; the call sites are explicit. The extract-to-service migration is the reward for disciplined internal boundaries.

## Evolution path

- Start with the modular monolith as the default. One deployable, strict internal boundaries.
- As modules mature and their interfaces stabilise, add typed events for the asynchronous flows.
- When a module hits one of the breakdown conditions above, extract it into its own service — with the monolith left in place for everything that does not yet justify the split.

The goal is not "eventually we will have microservices". It is "we keep the options open, at low cost, for as long as reasonably possible".
