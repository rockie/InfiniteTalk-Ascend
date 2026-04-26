**Language:** Use `{communication_language}` for all output.
**Output Language:** Use `{document_output_language}` for documents.
**Output Location:** `{planning_artifacts}`

# Stage 4: Draft & Review

**Goal:** Produce the executive product brief and run it through multiple review lenses to catch blind spots before the user sees the final version.

## Step 1: Draft the Executive Brief

Use `../resources/brief-template.md` as a guide — adapt structure to fit the product's story.

**Writing principles:**
- **Functional-first** — the reader should leave knowing what the product *does* and *for whom*. 1-2 pages.
- **Lead with the problem and users**, then move quickly into core capabilities and key user flows.
- **Concrete over abstract** — specific capabilities, real scenarios, named flows over generic claims.
- **Confident voice** — describe the product as built, not as hedged aspiration.
- **Do NOT pad with commercial content** — no pricing, no financial KPIs, no investor narrative, no multi-year business roadmap. If the user supplied such content, it goes into the distillate instead.
- Write in `{document_output_language}`

**Create the output document at:** `{planning_artifacts}/product-brief-{project_name}.md`

Include YAML frontmatter:
```yaml
---
title: "Product Brief: {project_name}"
status: "draft"
created: "{timestamp}"
updated: "{timestamp}"
inputs: [list of input files used]
---
```

## Step 2: Fan Out Review Subagents

Before showing the draft to the user, run it through multiple review lenses in parallel.

**Launch in parallel:**

1. **Skeptic Reviewer** (`../agents/skeptic-reviewer.md`) — "Where is the brief vague about features or flows? Which assumptions about user behavior are untested? What functional risks or edge cases are unacknowledged?"

2. **Feature Coverage Reviewer** (`../agents/opportunity-reviewer.md`) — "What features, flows, user types, or scenarios are under-covered or missing? Is the MVP in/out list internally consistent? Are constraints translated into features?"

3. **Contextual Reviewer** — You (the main agent) pick the most useful third lens based on THIS specific product, keeping the focus **functional** (not commercial). Choose the lens that addresses the SINGLE BIGGEST functional risk the other two reviewers won't naturally catch. Examples:
   - For healthtech: "Clinical-workflow and safety-critical flow reviewer"
   - For devtools: "Developer-experience friction reviewer (setup, failure modes, docs)"
   - For marketplace: "Cross-role interaction reviewer — does the product feature-set support both sides of the market?"
   - For enterprise: "Admin, permissioning, and audit-flow reviewer"
   - For data-heavy products: "Data quality, empty-state, and error-recovery reviewer"
   - **When domain is unclear, default to:** "Onboarding and first-run experience reviewer" — examines whether a first-time user can reach the core value through the features as described.
   Describe the lens, run the review yourself inline.

   **Do not** pick investor, GTM, pricing, or commercial-risk lenses — those are out of scope for this brief.

### Graceful Degradation

If subagents are unavailable:
- Perform all three review passes yourself, sequentially
- Apply each lens deliberately — don't blend them into one generic review
- The quality of review matters more than the parallelism

## Step 3: Integrate Review Insights

After all reviews complete:

1. **Triage findings** — group by theme, remove duplicates
2. **Apply non-controversial improvements** directly to the draft (obvious gaps, unclear language, missing specifics)
3. **Flag substantive suggestions** that need user input (strategic choices, scope questions, feature-prioritization decisions)

## Step 4: Present to User

**Headless mode:** Skip to `finalize.md` — no user interaction. Save the improved draft directly. (In autonomous mode, Stage 3 guided elicitation is skipped entirely; the flow is `SKILL → contextual-discovery → draft-and-review → finalize`.)

**Yolo and Guided modes:**

Present the draft brief to the user. Then share the reviewer insights:

"Here's your product brief draft. Before we finalize, my review panel surfaced some things worth considering:

**[Grouped reviewer findings — only the substantive ones that need user input]**

What do you think? Any changes you'd like to make?"

Present reviewer findings with brief rationale, then offer: "Want me to dig into any of these, or are you ready to make your revisions?"

**Iterate** as long as the user wants to refine. Use the "anything else, or are we happy with this?" soft gate.

## Stage Complete

This stage is complete when: (a) the draft has been reviewed by all three lenses and improvements integrated, AND either (autonomous) save and route directly, or (guided/yolo) the user is satisfied. Route to `finalize.md`.
