---
name: gm-epic-demo-story
description: 'Create a demo/verification story for a completed epic that defines a walkthrough flow and validates it via Chrome DevTools. Use when the user says "create epic demo story", "create demo story for epic [N]", "create verification story for epic", or wants to demonstrate and verify a completed epic through browser interaction.'
---

# Epic Demo Story Creator

Create a demo story for a completed epic: define a user walkthrough flow, then verify it via Chrome DevTools (MCP).

## Configuration

Load config from `{project-root}/_gomad/agile/config.yaml` and resolve:
- `{user_name}`, `{communication_language}`, `{document_output_language}`
- `{planning_artifacts}`, `{implementation_artifacts}`

## Workflow

### Step 1: Activate Scrum Master

Spawn a subagent and invoke `/gm:agent-pm` to load the Scrum Master (Bob) persona. All subsequent steps operate through Bob's persona.

### Step 2: Identify Target Epic

Ask the user which epic to create a demo story for, or auto-detect from user input (e.g. "epic 2").

Load the epic details from `{planning_artifacts}/*epic*.md` to understand:
- Epic scope and completed stories
- Key features and user-facing functionality
- Acceptance criteria that were met

### Step 3: Create Demo Story

Invoke `/gm-create-story` with the following story intent:

> **Story type:** Epic Demo / Verification
>
> **Purpose:** Demonstrate all completed features of Epic {N} through a sequential user walkthrough, then verify each step using Chrome DevTools MCP tools (screenshots, DOM inspection, network requests, console checks).
>
> **Story requirements:**
> 1. Define a complete user walkthrough that exercises all key features delivered in the epic
> 2. Each walkthrough step must include:
>    - User action (click, navigate, input, etc.)
>    - Expected visual result
>    - Chrome DevTools verification method (screenshot, DOM query, network check, etc.)
> 3. The walkthrough should follow a natural user journey, not a random feature checklist
> 4. Include setup/precondition steps (e.g. start dev server, seed data)
> 5. Reference the specific Chrome DevTools MCP tools to use: `take_screenshot`, `click`, `fill`, `navigate_page`, `evaluate_script`, `list_network_requests`, `get_console_message`, etc.
> 6. **Include an "Integration Smoke" task between environment setup and UI walkthrough.** Unit tests validate modules in isolation (mocked auth, mocked services); this task validates that modules are correctly wired together. Specifically:
>    - **Auth chain:** Perform the real login flow via API and use the resulting credential to call at least one representative endpoint per service — confirm the request is authenticated, authorized, and returns data (not 401/403/404). This catches auth middleware mismatches that mocked tests hide.
>    - **Request routing:** For each API the UI will call, make a direct HTTP request through the same path the frontend uses (proxy/gateway/load balancer) — confirm it reaches the correct backend. This catches proxy misconfiguration.
>    - **Data & config prerequisites:** Verify test accounts have expected roles, required secrets/keys are configured, and seed data is in the expected state. This catches environment drift between story development and demo time.
>    - **Contract alignment:** For at least one write operation, submit the request body in the exact format the frontend sends — confirm the backend accepts it without validation errors. This catches format mismatches (e.g., string vs number, enum naming) that pass when frontend and backend are tested independently.
>    - Any failure in this task must be diagnosed and fixed before proceeding to UI steps — these are integration seams that unit tests structurally cannot cover.

### Step 4: Review the Story

After the story is generated, review it from these angles:

1. **Requirements alignment** - Does the demo cover all key features of the epic?
2. **Technical feasibility** - Are the Chrome DevTools verification steps realistic and correct?
3. **Flow completeness** - Does the walkthrough represent a coherent user journey?
4. **Missing scenarios** - Are there important edge cases or states not covered?

If issues are found, discuss with Bob (Scrum Master) and iterate on the story until satisfactory.

### Step 5: Update Epics Document

Have Bob add a brief summary (1-2 lines) of the new demo story to the epics document at `{planning_artifacts}/*epic*.md`, under the relevant epic section. Keep it concise - just the story identifier and a one-line description.

### Step 6: Update Sprint Status

Have Bob ensure the new demo story appears in `{implementation_artifacts}/sprint-status.yaml` with appropriate status tracking.

### Step 7: Generate Regression E2E Tests (If applicable to this epic)

After the demo story is executed and verified, offer to convert the verified walkthrough into automated E2E tests that can run in CI. This turns a one-time demo into a reusable regression safety net.

**When to offer:** After Step 6, if the project has a test framework (Playwright, Cypress, etc.) or if the demo story exercised UI flows.

**How to generate:**

1. Invoke `/gm-qa-generate-e2e-tests` with scope set to the epic's verified user journeys
2. Use the demo story's task sequence as the test scenario outline — each task maps to a test case
3. The integration smoke results from the demo story become API-level test assertions
4. The Chrome DevTools walkthrough steps become browser-level test steps

**What the generated tests should cover:**

- **Integration smoke as test fixtures:** The auth chain, routing, and contract checks from the demo story's integration smoke task become `beforeAll` / setup steps in the test suite — if these fail, the whole suite skips with a clear diagnostic
- **Happy path per AC:** Each acceptance criterion gets one test case that replays the verified user journey
- **No flaky waits:** Use the same semantic locators (roles, labels, text) that Chrome DevTools used during the demo

**What to skip:**

- Don't generate tests for features that were only verified via `curl` / terminal (keep those as API tests, not E2E)
- Don't generate negative/edge-case tests from the demo — the demo covers happy paths; edge cases are a separate testing concern

**Rationale:** A demo story without regression tests is a proof-of-work that decays immediately. Converting verified journeys into automated tests means future stories can't silently break what the demo proved works.

### Step 8: Generate UAT Document

After the demo story is created (and optionally executed), generate a **User Acceptance Testing** document at `{output_folder}/uat-epic-{N}.md` for the user to perform manual validation.

**UAT document structure:**

```markdown
# UAT: Epic {N} — {Epic Title}

> 生成自: Story {X.Y} ({demo story file})
> 日期: {date}
> 状态: [ ] 未开始 / [ ] 进行中 / [ ] 通过 / [ ] 未通过

## 环境准备

{Simplified prerequisites — no Chrome DevTools references, just "启动开发服务器" etc.}

## 测试用例

### TC-{N}.1: {Feature Name} (AC: #{ac_number})

**前置条件:** {what must be true before this test}

| 步骤 | 操作 | 预期结果 | 通过? |
|------|------|----------|-------|
| 1 | {user action in plain language} | {expected outcome} | [ ] |
| 2 | ... | ... | [ ] |

**备注:** {any gotchas or known limitations}

---

{Repeat for each AC / feature group}

## 汇总

| 测试用例 | 结果 |
|----------|------|
| TC-{N}.1 {name} | [ ] 通过 / [ ] 未通过 / [ ] 跳过 |
| ... | ... |

**总体结论:** [ ] Epic {N} 验收通过 / [ ] 需要修复后重测
```

**Generation rules:**

1. **No technical jargon** — translate Chrome DevTools steps into plain user actions ("点击按钮", "输入文字", "检查页面显示")
2. **One test case per AC** (or per logical feature group if ACs are granular)
3. **Include known limitations** from the demo story's Dev Notes as 备注
4. **Include setup steps** simplified for non-technical users (just URLs and click paths, no CLI commands beyond `pnpm dev`)
5. **Mark skipped items** from the demo story as "跳过 (原因: ...)" in the summary table
6. **If the demo story has already been executed**, pre-fill the summary table with results from the Dev Agent Record (but keep checkboxes unchecked — the UAT is for the user's own validation)

## Notes

- All communication in `{communication_language}`, all output documents in `{document_output_language}`
- The demo story is meant to be executed by a dev agent using Chrome DevTools MCP, not manually
- The UAT document is meant for human testers — keep it simple and actionable
- Prioritize the happy path walkthrough; edge case verification is secondary
- Step 7 (E2E test generation) applies when the epic includes UI or API flows worth guarding against regression
