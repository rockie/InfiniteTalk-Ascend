# 🎯 Domain-KB Retrieval Output Quality Checklist

## Mission: Verify the output matches the expected mode and contract

You are an independent validator running in a **FRESH CONTEXT**. Confirm the `gm-domain-skill` output satisfies the STORY-06 and STORY-07 contracts — specifically the four decision-locked behaviors D-08 (single best-file return), D-09 (catalog listing), D-10 (no-match floor), and D-11 (Levenshtein halt-not-auto-execute).

**Your purpose is NOT just to validate — it's to catch silent integrity failures that would erode caller trust.** A weak BM25 hit returned as if it were strong, a truncated file passed off as "the full file", or an auto-executed Levenshtein suggestion are all production-grade defects.

---

## **🚀 HOW TO USE THIS CHECKLIST**

### When running from the gm-domain-skill workflow

- The workflow framework will automatically:
  - Load this checklist immediately before HALT in each of steps 4, 5, and 6.
  - Load the pending output (not yet emitted to the caller).
  - Load workflow variables from `./workflow.md`.
  - Execute the systematic validation below against the active mode.

### When running in a fresh context

- User provides the output text being reviewed and the mode (A/B/C/D).
- Load the matching mode section below; skip the others.
- Proceed with systematic analysis.

### Required inputs

- **Pending output**: The text the workflow is about to emit.
- **Mode indicator**: Which of A/B/C/D the workflow selected.
- **Workflow variables**: `{{domain_slug}}`, `{{query}}`, `{pack_files}`, `{installed_slugs}`, `{top_score}` — whichever apply.

---

## SYSTEMATIC VALIDATION

### Mode detection

- [ ] The output corresponds to EXACTLY ONE of four modes:
  - **Mode A**: `file_content_response` (D-08 — pack found + query present + `{top_score}` > `NO_MATCH_FLOOR`)
  - **Mode B**: `catalog_listing_response` (D-09 — pack found + query empty)
  - **Mode C**: `no_match_response` (D-10 — pack found + query present + `{top_score}` <= `NO_MATCH_FLOOR`)
  - **Mode D**: `pack_not_installed_response` (D-11 — pack not found or slug rejected by traversal guard)

### Mode A integrity (file_content_response)

- [ ] Returned content is the **FULL file content** (not an excerpt, not a summary, not the first N lines)
- [ ] Source citation includes BOTH the relative path AND the `{{domain_slug}}` pack name
- [ ] Score in the citation is > 0.5 (`NO_MATCH_FLOOR`) — otherwise Mode C should have fired instead
- [ ] Only **ONE** file returned (D-08 explicitly forbids top-N lists)
- [ ] The returned file is an actual file in `{pack_files_abs}` (not fabricated)

### Mode B integrity (catalog_listing_response)

- [ ] Every line matches the `<relative_path> — <H1 heading>` format (em-dash separator surrounded by single spaces)
- [ ] Relative paths are relative to `{pack_dir}` root (not absolute paths, not duplicating the slug prefix)
- [ ] Includes SKILL.md in its alphabetical slot if the pack contains one (SKILL.md is a pack file; NOT excluded, NOT privileged)
- [ ] Order is alphabetical by relative path
- [ ] Line count matches `|{pack_files}|` (no silently dropped files)
- [ ] Files whose H1 is missing show `(no H1 heading)` — not a blank heading

### Mode C integrity (no_match_response)

- [ ] Includes the `{{query}}` text **verbatim** (for debuggability — the caller needs to see what was scored)
- [ ] Includes the `{{domain_slug}}` identifier
- [ ] Suggests the catalog-listing fallback invocation (so the caller has a concrete next step)
- [ ] Does NOT include the top candidate file's content (per D-10: explicit "no match", NOT a weak hit)

### Mode D integrity (pack_not_installed_response)

- [ ] Lists Levenshtein suggestions ONLY at distance <= 3 (`LEVENSHTEIN_MAX`) — D-11
- [ ] Does NOT **auto-execute** the suggested slug, even if only one suggestion is at distance 1 (D-11 safety rule)
- [ ] Falls back to full `{installed_slugs}` list when no suggestions are within distance 3
- [ ] Invites user re-invocation with the corrected slug — never claims the skill "proceeded anyway"
- [ ] When the input slug was rejected by the traversal guard (`/`, `\`, `..`, leading `.` / `_`), the output is the rejection message from step 1 — NOT a Levenshtein suggestion against the invalid slug

---

## IF GAPS FOUND

Report each failed check with the specific line in the output and the decision ID (D-08 / D-09 / D-10 / D-11) it violates. Do NOT attempt to auto-correct — retrieval output integrity is load-bearing, and silent corrections would defeat the purpose of having a validator.

If a CRITICAL-severity gap is found (e.g., Mode A returned excerpted content, or Mode D auto-executed a suggestion), the workflow MUST abort and surface the validation failure to the caller rather than emit the broken output.
