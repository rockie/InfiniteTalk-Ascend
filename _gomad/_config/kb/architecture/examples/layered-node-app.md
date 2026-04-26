---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Example: Layered Node.js App

A walk-through of a small layered Node.js service that exposes a handful of HTTP endpoints for a fictional library-catalogue app. The example is invented for this pack — the domain, the entities, and the code shape were chosen to illustrate the pattern, not copied from any specific project.

## Directory layout

```
src/
├── routes/                 # Presentation layer — HTTP framework glue
│   ├── books.js
│   └── index.js
├── services/               # Application layer — use-case orchestration
│   └── books.js
├── repositories/           # Infrastructure layer — database access
│   └── books.js
├── models/                 # Domain layer — entities and invariants
│   └── book.js
├── errors.js               # Domain-level error types
└── app.js                  # Composition root — wires everything together
```

Four layers: `routes` (presentation), `services` (application), `repositories` (infrastructure), `models` (domain). Each file imports only from its layer or from a layer closer to the centre.

## Example flow: `GET /books/:id`

### Route (presentation)

`src/routes/books.js`:

```javascript
const { Router } = require('express');
const { NotFoundError } = require('../errors');

function booksRouter(booksService) {
  const router = Router();

  router.get('/:id', async (req, res, next) => {
    try {
      const book = await booksService.findById(req.params.id);
      res.json(book.toPublicJson());
    } catch (err) {
      if (err instanceof NotFoundError) {
        res.status(404).json({ error: 'book_not_found', message: err.message });
        return;
      }
      next(err);
    }
  });

  return router;
}

module.exports = { booksRouter };
```

Notice that `booksRouter` receives `booksService` as an argument. The route does not new-up the service or the repository; the composition root does. The route knows HTTP; the service knows the use case; the error translation lives here because HTTP status codes are a presentation concern.

### Service (application)

`src/services/books.js`:

```javascript
const { NotFoundError } = require('../errors');

function createBooksService(booksRepository) {
  return {
    async findById(id) {
      const book = await booksRepository.findById(id);
      if (!book) {
        throw new NotFoundError(`book ${id} does not exist`);
      }
      return book;
    },
  };
}

module.exports = { createBooksService };
```

The service translates "no record" into a domain error. It does not know about HTTP status codes; it does not know whether the repository is talking to Postgres, SQLite, or an in-memory map.

### Repository (infrastructure)

`src/repositories/books.js`:

```javascript
const { Book } = require('../models/book');

function createBooksRepository(db) {
  return {
    async findById(id) {
      const row = await db.oneOrNone('SELECT id, title, author, published_at FROM books WHERE id = $1', [id]);
      if (!row) return null;
      return Book.fromRow(row);
    },
  };
}

module.exports = { createBooksRepository };
```

The repository knows the SQL dialect and the row shape. It returns a domain `Book` (not a raw row), so the service never sees a database concern.

### Model (domain)

`src/models/book.js`:

```javascript
class Book {
  constructor({ id, title, author, publishedAt }) {
    if (!title || title.length === 0) {
      throw new Error('book title is required');
    }
    this.id = id;
    this.title = title;
    this.author = author;
    this.publishedAt = publishedAt;
  }

  static fromRow(row) {
    return new Book({
      id: row.id,
      title: row.title,
      author: row.author,
      publishedAt: row.published_at,
    });
  }

  toPublicJson() {
    return {
      id: this.id,
      title: this.title,
      author: this.author,
      publishedAt: this.publishedAt?.toISOString() ?? null,
    };
  }
}

module.exports = { Book };
```

The model enforces its invariants in the constructor. `fromRow` handles the one-way mapping from the database representation; `toPublicJson` handles the one-way mapping to the HTTP response.

### Composition root

`src/app.js`:

```javascript
const express = require('express');
const { createBooksRepository } = require('./repositories/books');
const { createBooksService } = require('./services/books');
const { booksRouter } = require('./routes/books');

function buildApp({ db }) {
  const booksRepository = createBooksRepository(db);
  const booksService = createBooksService(booksRepository);

  const app = express();
  app.use(express.json());
  app.use('/books', booksRouter(booksService));
  return app;
}

module.exports = { buildApp };
```

`app.js` is the only file that knows how the layers plug together. Tests can build an app with an in-memory repository by substituting `createBooksRepository` with a fake implementation that satisfies the same shape.

## Where validation lives

Two places, for different kinds of validation:

- **Shape validation at the route entrypoint.** `req.params.id` must be a non-empty string; `req.body` must match the expected JSON schema. Fail fast with 400 before any service code runs.
- **Domain invariants in the model.** A `Book` requires a non-empty title. The constructor enforces it; nothing downstream has to check again.

Keep the two kinds of checks separate. Shape validation talks about HTTP; domain invariants talk about books.

## What NOT to put in the service layer

- HTTP status codes. `throw new HttpError(404)` belongs in the route; the service throws a `NotFoundError` and lets the presentation layer translate.
- SQL. The service does not care whether the repository is speaking Postgres or a fake in-memory map.
- Request or response objects. The service takes primitive values and domain entities; it never touches `req` or `res`.

The discipline is worth it. When the day comes that the service needs to be exposed over a CLI, a message consumer, or a GraphQL resolver, no amount of refactoring is required — the service is already transport-agnostic.
