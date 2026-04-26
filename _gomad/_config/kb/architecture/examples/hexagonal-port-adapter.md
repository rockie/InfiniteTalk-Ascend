---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Example: Hexagonal Port + Adapter in Node.js

A concrete walk-through of the ports-and-adapters pattern in a small Node.js service. The scenario — a user-registration flow that persists to a data store — was invented for this pack; the code does not mirror any specific real project.

## The port interface

The core defines *what* it needs. In CommonJS without a type system, the "interface" is a documented contract — a JSDoc block or a plain comment — plus an in-memory adapter that serves as the reference implementation.

`src/core/ports/user-repository.js`:

```javascript
/**
 * UserRepository port
 *
 * Contract:
 *   findByEmail(email: string): Promise<User | null>
 *   save(user: User): Promise<void>
 *
 * Implementations MUST behave as if each call is atomic with respect to
 * concurrent callers. Implementations MUST NOT throw on a successful save.
 * Implementations MUST NOT mutate the supplied User instance.
 */
module.exports = {};
```

If the project is in TypeScript, this file is an `export interface UserRepository { ... }`. The substance is the same — the core declares the contract; no adapter is imported here.

## Two adapters

### Production adapter — Postgres

`src/infrastructure/adapters/postgres-user-repository.js`:

```javascript
const { User } = require('../../core/domain/user');

function createPostgresUserRepository(db) {
  return {
    async findByEmail(email) {
      const row = await db.oneOrNone(
        'SELECT id, email, display_name, created_at FROM users WHERE email = $1',
        [email.toLowerCase()],
      );
      if (!row) return null;
      return new User({
        id: row.id,
        email: row.email,
        displayName: row.display_name,
        createdAt: row.created_at,
      });
    },

    async save(user) {
      await db.none(
        `INSERT INTO users (id, email, display_name, created_at)
         VALUES ($1, $2, $3, $4)
         ON CONFLICT (id) DO UPDATE SET
           email = EXCLUDED.email,
           display_name = EXCLUDED.display_name`,
        [user.id, user.email.toLowerCase(), user.displayName, user.createdAt],
      );
    },
  };
}

module.exports = { createPostgresUserRepository };
```

The adapter knows the SQL dialect, handles the case-insensitive email comparison, and maps between row shapes and the domain `User`. Nothing about HTTP or any particular use case.

### Test adapter — in-memory

`src/infrastructure/adapters/in-memory-user-repository.js`:

```javascript
function createInMemoryUserRepository() {
  const byId = new Map();
  const byEmail = new Map();

  return {
    async findByEmail(email) {
      const id = byEmail.get(email.toLowerCase());
      return id ? byId.get(id) : null;
    },

    async save(user) {
      byId.set(user.id, user);
      byEmail.set(user.email.toLowerCase(), user.id);
    },

    // Helper for tests — not part of the port
    _snapshot() {
      return [...byId.values()];
    },
  };
}

module.exports = { createInMemoryUserRepository };
```

Note: `_snapshot` is a test-only affordance, prefixed to mark it as not part of the port. Tests can assert on the stored state without going through the public API.

## The core service uses the port

`src/core/use-cases/register-user.js`:

```javascript
const { randomUUID } = require('node:crypto');
const { User } = require('../domain/user');

class EmailAlreadyRegisteredError extends Error {
  constructor(email) {
    super(`email already registered: ${email}`);
    this.code = 'email_already_registered';
  }
}

function createRegisterUser({ userRepository, clock }) {
  return async function registerUser({ email, displayName }) {
    const existing = await userRepository.findByEmail(email);
    if (existing) {
      throw new EmailAlreadyRegisteredError(email);
    }
    const user = new User({
      id: randomUUID(),
      email,
      displayName,
      createdAt: clock.now(),
    });
    await userRepository.save(user);
    return user;
  };
}

module.exports = { createRegisterUser, EmailAlreadyRegisteredError };
```

The use case depends on two ports — `userRepository` and `clock`. It does not know which adapter is behind them. Swapping Postgres for the in-memory implementation, or swapping the system clock for a fixed-time fake, is transparent.

## Wiring at the edge

The composition root is the one place that knows which adapter satisfies which port.

`src/app.js`:

```javascript
const { createPostgresUserRepository } = require('./infrastructure/adapters/postgres-user-repository');
const { createSystemClock } = require('./infrastructure/adapters/system-clock');
const { createRegisterUser } = require('./core/use-cases/register-user');

function buildApp({ db }) {
  const userRepository = createPostgresUserRepository(db);
  const clock = createSystemClock();

  const registerUser = createRegisterUser({ userRepository, clock });

  // ... attach registerUser to an HTTP handler or CLI command here ...
  return { registerUser };
}

module.exports = { buildApp };
```

## Test benefit

In a unit test, swap in the in-memory adapters:

`test/register-user.test.js`:

```javascript
const { createRegisterUser, EmailAlreadyRegisteredError } = require('../src/core/use-cases/register-user');
const { createInMemoryUserRepository } = require('../src/infrastructure/adapters/in-memory-user-repository');

function createFixedClock(isoTimestamp) {
  const instant = new Date(isoTimestamp);
  return { now: () => instant };
}

describe('registerUser', () => {
  it('persists a new user with the provided email and display name', async () => {
    const userRepository = createInMemoryUserRepository();
    const clock = createFixedClock('2026-04-25T10:00:00Z');
    const registerUser = createRegisterUser({ userRepository, clock });

    const user = await registerUser({ email: 'alice@example.test', displayName: 'Alice' });

    expect(user.email).toBe('alice@example.test');
    expect(user.displayName).toBe('Alice');
    expect(userRepository._snapshot()).toHaveLength(1);
  });

  it('throws EmailAlreadyRegisteredError when the email is taken', async () => {
    const userRepository = createInMemoryUserRepository();
    const clock = createFixedClock('2026-04-25T10:00:00Z');
    const registerUser = createRegisterUser({ userRepository, clock });

    await registerUser({ email: 'alice@example.test', displayName: 'Alice' });

    await expect(registerUser({ email: 'alice@example.test', displayName: 'Alice Two' }))
      .rejects.toBeInstanceOf(EmailAlreadyRegisteredError);
  });
});
```

No database, no mocking library, no magic. The test reads like the behaviour it is asserting, runs in milliseconds, and breaks only when a real behavioural change occurs in the use case.

## Where the overhead shows

Two concrete trade-offs to be aware of:

- **The port is an extra file.** For a truly trivial feature, that is overhead. Introduce the port when there is a second implementation that genuinely needs to exist (typically "we want a fast test double") or when the infrastructure is likely to change.
- **The adapter lives elsewhere in the file tree.** Jumping between "what does this call do?" and "which adapter is wired in?" is one more indirection than a direct call would be. Worth it when the core needs to stay transport-and-storage-agnostic; unnecessary otherwise.

As a rule of thumb: apply the pattern where the port's stability matters more than the adapter's flexibility, and skip it where the code is already talking directly to one specific backend that is not going to change.
