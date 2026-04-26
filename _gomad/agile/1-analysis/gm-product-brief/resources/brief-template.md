# Product Brief Template (Functional-First)

This is a flexible guide for a **feature- and function-first** product brief — adapt it to serve the product's story. Merge sections, add new ones, reorder as needed. The product determines the structure, not the template.

**Focus of this brief:** what the product does, who it serves, and the core functional scope of the first version. The downstream consumer is a coding agent (via the gm-create-prd handoff), so prose is concrete and capability-oriented — not a stakeholder pitch. Business/commercial concerns (pricing, GTM, financial metrics, investor narrative) are explicitly **not** the focus and belong in a separate business brief or the distillate.

## Sensible Default Structure

```markdown
# Product Brief: {Product Name}

## Summary

[2-3 short paragraphs: What is this product? Who is it for? What are the core capabilities?
A reader should walk away able to describe what the product does in one sentence.]

## The Problem

[What pain exists? Who feels it? How are they coping today? What's the cost of the status quo?
Be specific — real scenarios, real frustrations, real consequences.]

## Target Users

[Primary users — vivid but brief. Who are they, what do they need, what does success look like for them
in terms of the tasks they are trying to complete? Secondary users if relevant.]

## Core Features & Capabilities

[The 3-7 core capabilities that define this product. For each:
- **Name** — short, verb-oriented ("Capture a lead", "Reconcile an invoice")
- **What it does** — one or two lines, user-observable behavior
- **Why it matters** — the user value delivered

Keep this concrete but not a detailed spec — that is the PRD's job.]

## Key User Flows

[2-4 end-to-end flows that show how users actually move through the product.
Narrative or short numbered steps. For example:
"A sales rep receives a new lead → opens the lead detail → triggers an AI enrichment →
  reviews suggested outreach → sends the first message in one click."
These flows anchor the feature list in real user experience.]

## User Scenarios

[1-3 concrete "day in the life" scenarios showing the product in use.
Name a user, give them a situation, walk through what they do and what changes for them.]

## What Makes This Different

[1-2 short paragraphs. The functional angle that makes this product distinctive —
what it does that alternatives don't, or does materially better. Keep it brief —
this is NOT a competitive analysis section.]

## MVP Functional Scope

### In
[Bulleted list of features/flows/capabilities explicitly in the first version.]

### Out
[Bulleted list of features/flows/capabilities explicitly deferred. Be specific — "no mobile app in v1"
is more useful than "mobile is out of scope".]

### Open / To be decided
[Items where the user is genuinely unsure — flag them rather than forcing a premature decision.]

## Constraints & Considerations

[Platform, integration, data, compliance, or user-environment constraints that shape
the functional scope. Keep it factual — not a risks register.]

## Success Signals (qualitative)

[3-5 short bullets describing what "this is working" looks like from a **user/product** perspective.
Examples: "Users complete onboarding in under 5 minutes without support",
"Users return at least weekly after their first successful task".
Avoid detailed business KPIs (revenue, CAC, LTV) — those belong in a business brief.]

## Vision (brief)

[1 short paragraph. Where this goes in the next 1-2 releases, from a **product capability** standpoint.
Not a long-term business roadmap.]
```

## Adaptation Guidelines

- **For B2B products:** Consider adding a short "Buyer vs User" note if the feature set is shaped by non-user stakeholders.
- **For platforms/marketplaces:** Consider a "Roles & Interactions" section that shows how different user types interact through the product.
- **For technical products:** May need a brief "Functional Architecture" section (keep it at the capability level, not the tech-stack level).
- **For regulated industries:** Consider a "Compliance Capabilities" section that lists features required by regulation — still framed as features, not policy text.
- **If scope is well-defined:** Merge "MVP Functional Scope" and "Vision" into a single "Roadmap Thinking" section.
- **If the product is an internal tool or research project:** Drop "What Makes This Different" — it rarely applies.

The brief should be 1-2 pages. If it's longer, you're putting in too much detail — that's what the distillate is for. Detailed business/commercial content belongs elsewhere entirely.
