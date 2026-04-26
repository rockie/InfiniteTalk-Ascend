---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Event-Driven Architecture

## Concept

In an event-driven architecture, producers emit events when meaningful things happen, and consumers react asynchronously. The producer does not know which consumers will handle the event, or whether any will at all. The coupling between producer and consumer is expressed entirely through the event schema, not through a direct call.

The pattern shines when the producer genuinely does not need the consumer's response, and when the set of consumers is expected to grow over time. It hurts when it is adopted reflexively for flows where a direct function call would have been perfectly adequate.

## Event shape

A well-formed event reads as a description of something that already happened:

- **Past-tense, domain vocabulary.** `OrderPlaced`, not `PlaceOrder`. `PaymentAuthorised`, not `AuthorisePayment`. The tense signals that the producer is reporting history, not requesting an action.
- **Self-contained payload.** The consumer should be able to act on the event without immediately turning around to query the producer for more data. Include the identifier of the aggregate (`orderId`), the fields other modules routinely need (`customerId`, `totalCents`, `currency`), and the timestamp the event occurred at.
- **Schema versioned.** Events live longer than any single consumer. Design the schema so that fields can be added without breaking old consumers, and so that old events can be replayed against new code if needed.

Resist the temptation to make events commands ("EmailSendRequested"). Those belong on a queue with one specific recipient, not on a broadcast bus.

## Ordering and idempotency

Two properties the consumer almost always needs:

- **Ordering.** Most buses guarantee ordering only within a partition key — typically the aggregate ID. Order events per aggregate, not globally. If the consumer depends on global ordering, it usually wants something else (a database with a monotonic version column) instead.
- **Idempotency.** Delivery is almost always at-least-once, which means the consumer will see some events more than once. Each consumer must behave correctly on a repeat: skip the second processing, or make the update safe to apply twice. An `eventId` column with a uniqueness constraint is the simplest implementation.

A consumer that is not idempotent and not ordered is not production-ready, regardless of how carefully the producer is written.

## Debugging cost

The honest trade-off: asynchronous event-driven code is harder to debug than synchronous code. A bug report for a broken flow may require correlating logs from three services, inspecting a queue's dead-letter topic, and reconstructing the consumer's state at the time the event arrived.

Partially mitigate the cost with:

- **Distributed tracing.** Propagate a correlation ID through the event payload and into every consumer's logs. A decent tracer lets you reconstruct the flow of one request across all the async hops.
- **Dead-letter queues.** Failed consumers should not lose events; they should park the event for inspection. A weekly "dead-letter review" meeting is cheap and catches real bugs.
- **Replayable event logs.** If the bus retains events for a window (hours or days), a consumer with a bug can be fixed and then replayed against the stored events.

## When to use event-driven

- Fan-out patterns where one producer has many independent consumers (`OrderPlaced` → billing, fulfilment, analytics, audit).
- Cross-domain integration where you want to decouple the domains' release cycles — billing can change its internals freely as long as `OrderPlaced` stays stable.
- Long-running workflows where a synchronous call would time out or hold a connection unnecessarily.

## When to prefer a direct call

- One producer, one consumer, same process. An event adds a queue and nothing else.
- The producer needs the consumer's response — events by definition do not return a value.
- The correctness of the flow depends on strong consistency (read-your-writes). Asynchronous delivery usually does not give you that.

A good heuristic: if you can describe the flow as "A happens, and then B reacts to A, and nothing really depends on how long the reaction takes", an event fits. If you find yourself saying "A needs to know whether B succeeded before continuing", a direct call is almost always right.
