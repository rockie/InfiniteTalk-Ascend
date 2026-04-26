---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Hexagonal Architecture (Ports and Adapters)

## The idea in one paragraph

The core of the application — the domain logic — is surrounded by *ports*, which are interfaces the core uses to talk to the outside world. Adapters are concrete implementations of those ports that bridge to real infrastructure: a database, an HTTP client, a message queue, a keyboard. The core never imports an adapter directly; it only knows about the ports it declared.

The name "hexagonal" is incidental — the shape was drawn as a hexagon to avoid implying top/bottom layering. Any number of sides works.

## Ports

A port is an interface owned by the core. It describes *what* the core needs, not *how* the need is satisfied. Examples:

- `UserRepository.findByEmail(email) → User | null`
- `Clock.now() → Date`
- `PaymentGateway.charge(amount, source) → ChargeResult`

Two qualities distinguish a good port from an accidental abstraction:

- **It is named in the domain's vocabulary.** `UserRepository`, not `PgUserDAO`. `PaymentGateway`, not `StripeClient`.
- **Its methods take domain types and return domain types.** No HTTP status codes, no SQL result sets, no library-specific exceptions leak through.

## Adapters

An adapter is a concrete class or module that implements a port by talking to real infrastructure. For `UserRepository` you might have:

- `PostgresUserRepository` — issues SQL against a connection pool.
- `InMemoryUserRepository` — stores users in a `Map`, used in unit tests.
- `HttpUserRepository` — calls out to a remote user service's REST API.

Each adapter lives in the infrastructure layer, depends on the port (defined in the core), and knows nothing about the other adapters. Swapping one for another requires changing one line in the dependency-injection wiring, not touching the core.

## Where hexagonal pays off

- **Swappable infrastructure.** If the application might move from Postgres to DynamoDB, or from a self-hosted SMTP server to a transactional-email service, the port keeps the core unchanged.
- **Testing.** The in-memory adapter is a real implementation, not a mock — it behaves like a database would, minus the latency and the schema migration headache. Tests become fast and deterministic without resorting to a mocking library.
- **Multiple front ends.** A core with a `CreateOrder` use case can expose the same behaviour via HTTP, via CLI, or via a message consumer, by attaching three input adapters to the core. No duplication of the use case.

## Where the overhead bites

- **Trivial applications.** A 200-line script that reads a CSV and writes a JSON file does not need a `CsvReader` port and a `JsonWriter` port. The indirection is all cost and no benefit.
- **Teams unfamiliar with dependency inversion.** The up-front cost of "why does the core define the interface the infrastructure implements?" can be steep. Pair hexagonal adoption with deliberate teaching rather than announcing it as a rule.
- **Premature abstraction.** Introducing a port with one implementation and no concrete test benefit is speculation. Wait until the second implementation is a real requirement, then extract the port.

## Relationship to layered architecture

Hexagonal is a refinement of layered. Both say "outer depends on inner"; hexagonal goes further and insists that the dependency is expressed through an explicit port owned by the inner. In practice many codebases start layered, notice the leak where the domain imports from infrastructure, introduce a port to invert that dependency, and end up with a hexagonal flavour without ever making the switch explicit.
