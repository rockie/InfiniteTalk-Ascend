# Story Discussion Context Quality Checklist

## **Critical Mission: Verify the discussion captured decisions, not transcripts**

You are an independent quality validator in a **FRESH CONTEXT**. Your mission is to review the `{{story_key}}-context.md` file produced by `gm-discuss-story` and verify it meets the output contract set by the 5-section template and the D-04 "decisions, not transcripts" rule.

---

## SYSTEMATIC VALIDATION

### 1. Structural Checks

- [ ] File starts with H1 heading `# {{story_key}} Context`
- [ ] All 5 XML-wrapped sections are present (opening + closing tags):
  - [ ] `<domain>` ... `</domain>`
  - [ ] `<decisions>` ... `</decisions>`
  - [ ] `<canonical_refs>` ... `</canonical_refs>`
  - [ ] `<specifics>` ... `</specifics>`
  - [ ] `<deferred>` ... `</deferred>`
- [ ] Section ORDER matches template: domain → decisions → canonical_refs → specifics → deferred
- [ ] No other top-level XML wrappers exist (no inventing new sections — downstream parsers key on these 5 names)

### 2. Content Discipline (per D-04 — captures decisions, not transcripts)

- [ ] `<decisions>` contains concrete resolved answers (bullets or `question → answer` form), NOT verbose paragraphs of dialogue
- [ ] Every decision cites a specific source (AC number, architecture section, file path) where applicable
- [ ] `<canonical_refs>` lists file paths / section anchors — NOT generic phrases like "see the architecture doc"
- [ ] `<deferred>` items are explicit with a one-sentence reason (not "TBD" or "maybe later")
- [ ] No verbatim quotes of the user's question text padding out the decision record
- [ ] No re-statement of PRD content that was simply copied over

### 3. Scope Discipline

- [ ] Content is grounded in THIS story's epic entry (acceptance criteria, technical requirements) — not generic interview answers
- [ ] No gray areas from OTHER stories in the same epic
- [ ] No decisions that contradict the shared inputs (PRD/architecture/UX) without noting the contradiction

### 4. Re-run Safety

- [ ] No `{{story_key}}-discuss-checkpoint.json` file exists alongside `{{story_key}}-context.md` (D-05 cleanup — stale checkpoint should be deleted after successful write)

---

## IF GAPS FOUND

If any checkbox fails, present the issues to the user:

1. List each failed check with the specific file/line
2. Offer: "Apply all fixes / Select fixes to apply / Skip fixes and close"
3. On "Apply all" or "Select": return to workflow step 7 to re-render the affected sections
4. On "Skip": leave `{{story_key}}-context.md` as-is; note gaps in the output summary

---

## Success Criteria

- All 5 sections present, in canonical order, with XML wrappers intact
- `<decisions>` reads as resolved answers, not chat transcripts
- `<canonical_refs>` cites real file paths / section anchors
- `<deferred>` items have explicit reasons
- No stale discuss-checkpoint left behind
