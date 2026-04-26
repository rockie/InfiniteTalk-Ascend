---
source: original
license: MIT
last_reviewed: 2026-04-25
---

# Playwright E2E Test Example

A minimal Playwright setup for a Node web application running locally at `http://localhost:3000`. The example scenario — a sign-in flow for an invented note-taking app — was written for this pack; it is not copied from any real tutorial.

## Install and configuration

Install Playwright as a dev dependency and generate the browser binaries once per machine:

```bash
npm install --save-dev @playwright/test
npx playwright install
```

Create `playwright.config.js` at the project root:

```javascript
// playwright.config.js
const { defineConfig, devices } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'npm run start:test',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
```

Notable choices:

- `retries: 1` **only in CI**. Local runs should fail loudly on flake so you notice and fix it. CI gets one retry to absorb rare network blips.
- `trace: 'retain-on-failure'` captures a DOM snapshot timeline only when a test fails. `trace: 'on'` retains traces for every test and fills up disk fast.
- `webServer` tells Playwright to boot the app for the test run and tear it down afterward. The `npm run start:test` script should start the server against a *test* database — never production.

## Example test

`e2e/sign-in.spec.js`:

```javascript
const { test, expect } = require('@playwright/test');

test.describe('Sign-in flow', () => {
  test('an existing user can sign in with valid credentials', async ({ page }) => {
    await page.goto('/sign-in');

    // Fill the form
    await page.getByLabel('Email').fill('alice@example.test');
    await page.getByLabel('Password').fill('correct horse battery staple');
    await page.getByRole('button', { name: 'Sign in' }).click();

    // Assert we landed on the notes dashboard
    await expect(page).toHaveURL(/\/notes/);
    await expect(page.getByRole('heading', { name: 'Your notes' })).toBeVisible();
    await expect(page.getByText(/signed in as alice/i)).toBeVisible();
  });

  test('an invalid password shows a form error and keeps us on the sign-in page', async ({ page }) => {
    await page.goto('/sign-in');

    await page.getByLabel('Email').fill('alice@example.test');
    await page.getByLabel('Password').fill('wrong');
    await page.getByRole('button', { name: 'Sign in' }).click();

    await expect(page.getByRole('alert')).toHaveText(/email or password is incorrect/i);
    await expect(page).toHaveURL(/\/sign-in/);
  });
});
```

Two scenarios, one happy path and one error path, both on the critical login surface. That is the right density for an E2E suite — thorough where it matters, silent on everything else.

The tests query by accessible role and label (`getByRole('button', { name: 'Sign in' })`) rather than by CSS selectors or test IDs. This style is more robust to markup changes and doubles as a rough accessibility smoke test.

## Running headed vs headless

- `npx playwright test` — headless, fast, suitable for CI and everyday local runs.
- `npx playwright test --headed` — opens a real browser window so you can watch the test drive the UI. Useful when debugging a new test.
- `npx playwright test --debug` — pauses on the first line and opens the inspector; step through the test one action at a time.

## Screenshot and trace on failure

When a test fails, Playwright writes the screenshot, video, and trace into `test-results/` under the failing test's directory. Run `npx playwright show-trace path/to/trace.zip` to open an interactive timeline with every action, DOM snapshot, and network event captured. This is usually faster than adding `console.log` calls.

## Parallelism and sharding

Playwright runs test files in parallel across worker processes by default. The config caps CI at 2 workers, which tends to give the best wall-clock runtime without overloading the test database. For very large suites, split across multiple CI jobs using `--shard=1/4`, `--shard=2/4`, etc.; each shard runs a deterministic slice of the suite and reports separately.

## Seeding the test database

The example assumes `alice@example.test` already exists with the right password. Two options in practice:

- A seed script that runs before the suite and re-inserts a small fixture user set. Cheapest to set up.
- A Playwright global setup hook that calls an internal HTTP endpoint (test-only) to insert fixtures for each test's needs.

Whichever you pick, keep seed data minimal — the smallest fixture set that covers the critical paths.
