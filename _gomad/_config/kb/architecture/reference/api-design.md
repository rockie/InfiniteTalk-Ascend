---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# API Design Fundamentals

## Resource vs RPC vs query shape

Three broad shapes cover almost every API design choice:

- **Resource-oriented (REST).** The API exposes nouns; the verbs are a fixed set (typically `GET`, `POST`, `PUT`, `PATCH`, `DELETE`). Good fit for CRUD-heavy domains where most operations are obvious variants of create/read/update/delete on well-defined entities. Scales predictably to dozens of entities; starts to strain when the domain has a lot of "verb-shaped" operations that do not map cleanly to a noun.
- **RPC-oriented (gRPC or JSON-RPC).** The API exposes verbs directly — `TransferFunds`, `ApprovePurchaseOrder`, `RecomputeRanking`. Good fit for domains where the operations are the primary abstraction. Typically paired with a typed schema (protobufs, OpenAPI) so both sides agree on the contract.
- **Query-oriented (GraphQL).** Clients declare the shape of the data they want; the server resolves it. Good fit when many different clients need many different projections of the same underlying data, and over-fetching or under-fetching becomes a real bottleneck. Cost: caching, authorisation, and pagination each become the API designer's problem rather than the HTTP layer's.

Do not pick a style because it is fashionable. Pick it because the operations in your domain are shaped like it.

## Versioning

Three common approaches; each has a failure mode:

- **URL versioning (`/v1/orders`, `/v2/orders`).** Simple and explicit. Works poorly when only a small part of the API changes — you either clone the whole tree or end up with a zoo of versions.
- **Header versioning (`Accept: application/vnd.myapp.v2+json`).** Keeps URLs stable. Harder to discover (no URL is a living documentation prompt), and clients sometimes forget the header and accidentally get an old version.
- **Field-level versioning.** The API does not version; individual fields do. New field appears, old field remains until a documented deprecation window has passed. Requires discipline to actually retire old fields, but produces the longest-lived single-surface API.

Whichever you pick, write down the lifecycle: what triggers a new version, how long old versions stay supported, and how clients are notified of deprecations. The client's surprise-radar is the real cost of versioning, not the technical machinery.

## Error contract

A usable error response has three components:

- **A status code** (for HTTP APIs, the HTTP status). Used by infrastructure — load balancers, retry logic, logs — without needing to parse the body.
- **A machine-readable error type.** A stable, documented string like `"order_not_found"` or `"payment_declined_insufficient_funds"`. Clients branch on this, not on the human message.
- **A human-readable message.** For developers reading logs. Does not need to be localised; does not need to be user-safe (that is the client's job).

Optional but valuable: a `requestId` the caller can reference in a support conversation, and a `details` object for field-level validation errors (`{ field: 'email', reason: 'invalid_format' }`).

Avoid the common mistake of returning HTTP 200 with `{ "error": "..." }` in the body. Intermediate infrastructure has no way to tell a successful request from a failed one; retries and alerts break.

## Pagination

Two approaches cover most needs:

- **Offset pagination (`?offset=40&limit=20`).** Easy to implement, easy to jump to a specific page. Fails when the underlying dataset changes between requests — an insert shifts subsequent pages and the client sees duplicates or gaps.
- **Cursor pagination (`?cursor=abc123&limit=20`).** The server returns a cursor pointing at the next page's starting key (usually encoding the last row's sort value and ID). Stable under inserts and deletes. Does not support "jump to page 17" but that is almost never a real requirement in APIs.

Prefer cursors for any list that clients will page through in order; prefer offsets only when random page access is a genuine requirement (typically admin dashboards, not end-user APIs).

## Idempotency for POST

A `POST` that creates a resource is not naturally idempotent — if the client retries after a timeout, it might create two resources. Solve with an `Idempotency-Key` header: the client generates a unique key per logical request; the server records the key and the response on first processing, and on any repeat with the same key returns the original response without re-executing. Keep the key → response map with a reasonable TTL (24 hours is typical).

This is especially important for any request that moves money, triggers notifications, or has any side effect that is expensive to undo.
