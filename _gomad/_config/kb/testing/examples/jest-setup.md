---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Jest Setup for a CommonJS Node Project

This walk-through sets up Jest for a plain Node project using CommonJS modules. The example code is a deliberately small `discount` helper invented for this pack — no dependencies on any external library under test.

## Minimal configuration

Add Jest as a dev dependency and declare the test script in `package.json`:

```json
{
  "name": "invoice-utils",
  "version": "0.1.0",
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  },
  "jest": {
    "testEnvironment": "node",
    "testMatch": ["**/*.test.js"],
    "clearMocks": true,
    "coverageThreshold": {
      "global": { "branches": 80, "functions": 80, "lines": 80, "statements": 80 }
    }
  },
  "devDependencies": {
    "jest": "^29.0.0"
  }
}
```

Three points worth calling out:

- `testEnvironment: 'node'` skips the browser/jsdom bootstrapping. A Node project that does not touch the DOM does not pay the startup cost.
- `clearMocks: true` resets mock state between tests automatically, which removes a whole class of "test A left a stub behind that broke test B" bugs.
- `coverageThreshold` causes `jest --coverage` to exit non-zero if coverage drops below the declared floors. Start with a low threshold and ratchet up.

## Example code under test

`src/discount.js`:

```javascript
function applyDiscount(priceCents, percentOff) {
  if (!Number.isInteger(priceCents) || priceCents < 0) {
    throw new TypeError('priceCents must be a non-negative integer');
  }
  if (typeof percentOff !== 'number' || percentOff < 0 || percentOff > 100) {
    throw new RangeError('percentOff must be between 0 and 100');
  }
  const discounted = Math.round(priceCents * (1 - percentOff / 100));
  return discounted;
}

module.exports = { applyDiscount };
```

## Example test file

`src/discount.test.js`:

```javascript
const { applyDiscount } = require('./discount');

describe('applyDiscount', () => {
  it('returns the original price when percentOff is 0', () => {
    expect(applyDiscount(1000, 0)).toBe(1000);
  });

  it('returns zero when percentOff is 100', () => {
    expect(applyDiscount(1000, 100)).toBe(0);
  });

  it('rounds to the nearest cent', () => {
    // 12345 * (1 - 0.1) = 11110.5, rounds up to 11111
    expect(applyDiscount(12345, 10)).toBe(11111);
  });

  it('throws TypeError for a non-integer price', () => {
    expect(() => applyDiscount(10.5, 5)).toThrow(TypeError);
  });

  it('throws RangeError for a negative percentOff', () => {
    expect(() => applyDiscount(1000, -1)).toThrow(RangeError);
  });
});
```

Five tests, one behaviour each, clear names. The rounding test explains *why* the expected value is what it is — when a future reader asks "why 11111 and not 11110?", the comment answers it without forcing them to run a calculator.

## Running a single test or file

During development, running the whole suite is usually overkill:

- `npx jest src/discount.test.js` — runs just this file.
- `npx jest -t 'rounds to the nearest cent'` — runs tests whose name matches the pattern, across every file.
- `npx jest --watch` — re-runs affected tests on save, with keyboard shortcuts for filtering.

## Coverage reporting

`npm run test:coverage` produces a text summary on stdout and a detailed HTML report under `coverage/lcov-report/index.html`. Open the HTML report, click into `discount.js`, and look for red lines — those are branches your tests did not reach.

Add `coverage/` to `.gitignore`; the report is a local artefact, not something to commit.

## When to move beyond this setup

This configuration is enough to get useful signal for a small library. Grow it when you have a concrete reason — a TypeScript build step, a custom test environment, a setup hook that seeds a local database. Avoid adding configuration on speculation; every setting is something the next reader has to understand.
