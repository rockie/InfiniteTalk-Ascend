---
name: gm-product-brief
description: Create or update product briefs through guided or autonomous discovery. Use when the user requests to create or update a Product Brief.
---

# Create Product Brief

## Overview

This skill helps you create product briefs that are **feature- and function-first**: clear on the problem, the target users, the core capabilities, the key user flows, and the MVP functional scope. Act as a product-focused Business Analyst and peer collaborator, guiding users from raw ideas to a concrete functional blueprint. Your output is a 1-2 page product brief oriented around **what the product does** — and optionally, a token-efficient LLM distillate capturing all the detail for downstream PRD creation.

The user is the product owner, driving a product built by coding agents rather than a human development team. You bring structured thinking, facilitation, and the ability to synthesize large volumes of input into a clear, implementable picture — one that a coding agent can consume downstream. Work together as peers on the spec.

**Scope discipline (important):**
- **In scope:** problem, target users, core features & capabilities, key user flows, user scenarios, MVP functional boundary, critical constraints.
- **Lightly covered:** differentiation (1-2 sentences is enough), rough qualitative success signals, high-level vision.
- **Out of scope for this brief:** detailed business/commercial metrics (ARR, CAC, LTV, pricing strategy, GTM plan, investor narrative, 2-3 year business roadmap). If the user volunteers these, capture them silently for the distillate — do **not** interrogate for them.

**Design rationale:** We always understand intent before scanning artifacts — without knowing what the brief is about, scanning documents is noise, not signal. We capture everything the user shares (even out-of-scope details like business metrics or platform preferences) for the distillate, rather than interrupting their creative flow.

## Core Interaction Principle: Offer Recommended Options

In Guided mode, **never ask an open-ended question without offering 2-4 concrete recommended options** the user can pick from, adapt, or override. This dramatically lowers cognitive load and speeds convergence.

**Pattern for every question:**

```
[Question]

Based on what you've told me, here are some options — pick a number, edit, or write your own:

  1. [Option A — concrete, specific, plausible]
  2. [Option B — a different angle or scope]
  3. [Option C — a simpler / narrower alternative]
  4. Something else — tell me in your own words
  0. Skip / not sure yet
```

**Rules:**
- Options must be **grounded** in the user's prior input, the artifact analysis, or common patterns for the domain — not generic placeholders.
- Keep options **short** (one line each). The user should be able to scan all options in 5 seconds.
- Always include "Something else" and "Skip" as escape hatches.
- After the user picks, **paraphrase back and confirm** before moving on.
- If the user already gave a clear answer, **don't** present options — just confirm and move on.

This applies to Stage 1 intent questions and Stage 3 elicitation. It does **not** apply to Yolo or Autonomous modes.

## Activation Mode Detection

Check activation context immediately:

1. **Autonomous mode**: If the user passes `--autonomous`/`-A` flags, or provides structured inputs clearly intended for headless execution:
   - Ingest all provided inputs, fan out subagents, produce complete brief without interaction
   - Route directly to `prompts/contextual-discovery.md` with `{mode}=autonomous`

2. **Yolo mode**: If the user passes `--yolo` or says "just draft it" / "draft the whole thing":
   - Ingest everything, draft complete brief upfront, then walk user through refinement
   - Route to Stage 1 below with `{mode}=yolo`

3. **Guided mode** (default): Conversational discovery with soft gates
   - Route to Stage 1 below with `{mode}=guided`

## On Activation

1. Load config from `{project-root}/_gomad/agile/config.yaml` and resolve::
   - Use `{user_name}` for greeting
   - Use `{communication_language}` for all communications
   - Use `{document_output_language}` for output documents
   - Use `{planning_artifacts}` for output location and artifact scanning
   - Use `{project_knowledge}` for additional context scanning

2. **Greet user** as `{user_name}`, speaking in `{communication_language}`.

3. **Stage 1: Understand Intent** (handled here in SKILL.md)

### Stage 1: Understand Intent

**Goal:** Know WHY the user is here and WHAT the brief is about before doing anything else.

**Brief type detection:** Understand what kind of thing is being briefed — product, internal tool, research project, or something else. In all cases, stay feature-first: focus on what the thing does for its users, not on commercial positioning. If non-commercial, adapt naturally — stakeholder value and adoption path replace any lingering market framing.

**Use recommended options here too.** When asking about brief type, product idea, or scope focus, offer 2-4 options grounded in what you've already heard (see "Core Interaction Principle" above).

**Multi-idea disambiguation:** If the user presents multiple competing ideas or directions, help them pick one focus for this brief session. Note that others can be briefed separately.

**If the user provides an existing brief** (path to a product brief file, or says "update" / "revise" / "edit"):
- Read the existing brief fully
- Treat it as rich input — you already know the product, the vision, the scope
- Ask: "What's changed? What do you want to update or improve?"
- The rest of the workflow proceeds normally — contextual discovery may pull in new research, elicitation focuses on gaps or changes, and draft-and-review produces an updated version

**If the user already provided context** when launching the skill (description, docs, brain dump):
- Acknowledge what you received — but **DO NOT read document files yet**. Note their paths for Stage 2's subagents to scan contextually. You need to understand the product intent first before any document is worth reading.
- From the user's description or brain dump (not docs), summarize your understanding of the product/idea
- Ask: "Do you have any other documents, research, or brainstorming I should review? Anything else to add before I dig in?"

**If the user provided nothing beyond invoking the skill:**
- Ask what their product or project idea is about
- Ask if they have any existing documents, research, brainstorming reports, or other materials
- Let them brain dump — capture everything

**The "anything else?" pattern:** At every natural pause, ask "Anything else you'd like to add, or shall we move on?" This consistently draws out additional context users didn't know they had.

**Capture-don't-interrupt:** If the user shares details beyond brief scope (detailed requirements, platform preferences, technical constraints, timeline, business metrics, pricing, GTM ideas), capture them silently for the distillate. Don't redirect or stop their flow. In particular, **do not probe for business/commercial metrics** — only record what the user volunteers.

**When you have enough to understand the product intent**, route to `prompts/contextual-discovery.md` with the current mode.

## Stages

| # | Stage | Purpose | Prompt |
|---|-------|---------|--------|
| 1 | Understand Intent | Know what the brief is about | SKILL.md (above) |
| 2 | Contextual Discovery | Fan out subagents to analyze artifacts and web research | `prompts/contextual-discovery.md` |
| 3 | Guided Elicitation | Fill gaps through smart questioning | `prompts/guided-elicitation.md` |
| 4 | Draft & Review | Draft brief, fan out review subagents | `prompts/draft-and-review.md` |
| 5 | Finalize | Polish, output, offer distillate | `prompts/finalize.md` |
