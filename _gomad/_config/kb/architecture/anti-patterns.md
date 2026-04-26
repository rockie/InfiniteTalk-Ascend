---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Architecture Anti-Patterns

Eight structural mistakes that recur across codebases. Each entry describes the smell in concrete terms, explains what it costs, and points at the replacement.

## Anti-pattern 1: Distributed monolith

A system is decomposed into several services, but each service synchronously calls several others to satisfy a single request. A failure in any service cascades; a slow service degrades all the rest; every deployment has to coordinate the version matrix across the whole fleet.

**Why it is bad:** you paid the operational cost of multiple services and received the coupling of a monolith. The worst of both worlds.

**Replace with:** either collapse back into one deployable and split along real domain seams later, or introduce asynchronous messaging where the call-chain is not genuinely required to be synchronous.

## Anti-pattern 2: Ambiguous module boundaries

Code is nominally organised into modules, but any module can reach into any other's internals. Private helpers get imported across the tree; schema objects belong to whichever module happens to have opened the file first.

**Why it is bad:** modules only reduce complexity if the boundary is enforced. If any file can depend on any other, you have a single module with misleading directory names.

**Replace with:** a small set of allowed public entry points per module, enforced by file layout, linter rules (e.g. import path bans), or the language's visibility system. If the team cannot state the public surface of a module in one sentence, it does not have one.

## Anti-pattern 3: Premature event-driven design

Every state change publishes an event, every module subscribes to half a dozen events, and nobody can trace a single request end to end without stitching together ten log lines.

**Why it is bad:** events are fantastic for decoupling producers from consumers when the coupling is actually in the way. When the coupling is nominal — one producer, one consumer, same process — events add indirection without removing anything real.

**Replace with:** a direct function call until the coupling hurts. Introduce events when there are two or more independent consumers, when the producer does not need to wait for consumption, or when the decoupling crosses a service boundary.

## Anti-pattern 4: God services

One service or module accretes every feature that does not have an obvious home. Over time it depends on every other module, every other module depends on it, and refactoring any of its internals becomes a multi-week project.

**Why it is bad:** the god service is both the most-changed and the hardest-to-change part of the system. Any change needs regression testing against everything.

**Replace with:** extract features along real domain lines — not along layer lines ("controllers over here, models over there"). Each extracted module should be able to describe its purpose without referencing five other modules.

## Anti-pattern 5: Leaky abstractions in API design

The API response exposes the underlying database column names, the ORM's lazy-loaded proxy objects, or the internal ID scheme ("UUID v4 because that's what the library gave us"). A client that works against this API tomorrow may break when the internal representation changes.

**Why it is bad:** the API is now a reflection of the current implementation, not a stable contract. Refactoring is a breaking change by default.

**Replace with:** an explicit output shape defined by the API, not inherited from the storage layer. A small amount of mapping code at the boundary is the price you pay for being able to evolve the inside without coordinating with every client.

## Anti-pattern 6: Shared database across services

Two nominally-independent services both connect to the same database and read/write the same tables. A schema change in service A silently breaks service B; neither team can deploy without checking with the other.

**Why it is bad:** the database is now a coupling point the architecture does not acknowledge. The services are still two codebases, but they are one system.

**Replace with:** one database per service, with explicit APIs between them. When that is too expensive to adopt immediately, at least designate one service as the owner of each table — the other service must read through the owner's API.

## Anti-pattern 7: Inheritance across unrelated concepts

A base class that was originally a reasonable abstraction grows over time to accommodate every subclass's special case. New subclasses inherit behaviour they do not want and have to override it back out.

**Why it is bad:** inheritance couples every subclass to every other, through the base. Changes to the base class affect classes that have nothing to do with each other.

**Replace with:** composition. A small number of focused helper objects that a class *uses* are almost always easier to reason about than a deep hierarchy the class *extends*.

## Anti-pattern 8: Synchronous call chains deeper than three hops

A request enters service A, which calls B, which calls C, which calls D. The latency is the sum; the availability is the product; a single slow dependency anywhere in the chain surfaces as "everything is slow".

**Why it is bad:** the failure surface grows multiplicatively, the latency budget evaporates, and the call graph becomes impossible to reason about without a tracer.

**Replace with:** collapse the chain where services are really just layers of the same domain; introduce asynchronous boundaries where the caller does not genuinely need the callee's response immediately; cache the upstream results where they are safe to cache.
