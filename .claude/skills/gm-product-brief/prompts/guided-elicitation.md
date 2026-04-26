**Language:** Use `{communication_language}` for all output.
**Output Language:** Use `{document_output_language}` for documents.

# Stage 3: Guided Elicitation (Functional-First)

**Goal:** Fill the gaps in what you know about **what the product does** and **how users will use it**. By now you have the user's brain dump, artifact analysis, and any supporting research. The downstream consumer is a coding agent via the PRD handoff — keep elicitation focused on feature and flow detail a coding agent can compile, not commercial positioning. This stage is smart, targeted questioning — **not** a rote section-by-section interrogation, and **not** a commercial/business deep-dive.

**Skip this stage entirely in Yolo and Autonomous modes** — go directly to `draft-and-review.md`.

## Core Principle: Always Offer Recommended Options

For every question in this stage, **present 2-4 concrete recommended options** before asking the user to describe freely. Options must be grounded in what you already know (user's input + artifact analysis + web research on reference implementations), not generic.

**Standard prompt format:**

```
[Short question — one line]

Based on what you've told me so far, here are a few directions — pick a number, edit, or write your own:

  1. [Specific option grounded in prior input]
  2. [Different angle or broader / narrower scope]
  3. [A third plausible alternative if one exists]
  4. Something else — tell me in your own words
  0. Skip for now / not sure yet
```

**Do NOT present options when:**
- The user has already given a clear, confident answer on that topic
- The question is a simple confirmation ("Is X right?")
- You're genuinely exploring something with no defensible shortlist

When the user picks, paraphrase back in one sentence and move on. No long commentary.

## Topics to Cover (flexibly, conversationally)

These are your **mental checklist**, not a script. Adapt to what the user cares about and what's already known.

### Problem & Users (light touch if already covered)
- What core problem does this solve? For whom?
- Are there distinct user types with different needs? Who is the primary one?
- How do these users solve this today? What's the most painful part?

### Core Features & Capabilities **(primary focus)**
- What are the 3-7 core things the product can do? (Use options.)
- For each core capability: what does the user see / experience?
- Which capabilities are table-stakes vs. distinctive?
- Are there must-have integrations (auth providers, data sources, external services) that shape features?

### Key User Flows **(primary focus)**
- What is the main end-to-end flow a user goes through? (Offer 2-3 candidate flows as options.)
- Are there 1-2 secondary flows that also matter for v1?
- Any moment in the flow where the user is most likely to drop off or get stuck?

### User Scenarios **(primary focus)**
- Can you walk me through one realistic "day in the life" example of a user using this?
- Are there edge-case scenarios (new user, power user, recovering from error) worth naming?

### MVP Functional Scope **(primary focus)**
- Of everything we've discussed, what's the smallest functional set that delivers real value? (Offer a "narrow / medium / broader" three-option shortlist grounded in prior input.)
- What is explicitly OUT of v1? (Offer common deferrals as options: mobile, admin panel, bulk ops, integrations, etc.)
- Any constraints (platform, regulatory, data) that force things in or out?

### Differentiation (light touch — 1 short question)
- In one sentence, what does this product *do* that alternatives don't, or do materially better? (One option: "skip, not important for this brief".)

### Success Signals (qualitative, optional — 1 short question)
- What would make you say "yes, this is working" from a user-experience standpoint? (Offer options like "fast time-to-first-value", "high weekly return rate", "low support load", "something else", "skip".)

### Explicitly DO NOT probe for
- Pricing, packaging, monetization strategy
- CAC, LTV, ARR, payback period, or other financial KPIs
- Investor-facing narrative or fundraising angles
- Detailed 2-3 year business roadmap
- Go-to-market channel strategy

If the user volunteers any of the above, **capture silently** for the distillate with a brief "noted" — don't follow up on it.

## The Flow

For each topic area where you have gaps:

1. **Lead with what you know** — "Based on your input and my research, the core capabilities look like A, B, C. Is that the right shortlist?"
2. **Offer options** — use the standard prompt format above.
3. **Paraphrase and confirm** — one sentence, then move on.
4. **Soft gate** — "Anything else on this, or shall we move on?"

If the user is giving you detail beyond brief scope (detailed requirements, architecture, platform specs, business metrics), **capture it silently** for the distillate. Acknowledge briefly ("Good detail — I'll note that for the PRD handoff") without derailing.

## When to Move On

When you have enough substance to draft a **functional** 1-2 page brief covering:
- Clear problem and primary users
- 3-7 core features / capabilities
- At least one key user flow and one user scenario
- MVP in/out/open scope
- One-sentence differentiation (or skipped)

You don't need perfection — missing details can surface during review.

If the user is giving complete, confident answers and you have solid coverage after fewer than 3-4 exchanges, proactively offer to draft early.

**Transition:** "I think I have a solid functional picture. Ready for me to draft the brief, or is there anything else you'd like to add?"

## Stage Complete

This stage is complete when sufficient substance exists to draft a functional brief and the user confirms readiness. Route to `draft-and-review.md`.
