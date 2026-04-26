# Domain-KB Retrieval Workflow

**Goal:** Retrieve the single best-matching `.md` file from an installed domain-knowledge-base pack using BM25-ranked scoring, OR produce an explicit "no match" / "pack not installed" output with an actionable fallback.

**Your Role:** Deterministic retrieval engine over `<installRoot>/_config/kb/<slug>/**/*.md`. Zero hidden behavior: if the match is weak, say so; if the slug is unknown, suggest; never silently auto-execute a similar-looking slug.

- Communicate in {communication_language}.
- Return the single best-matching file content on success (D-08). NOT excerpts. NOT top-N lists.
- When `{query}` is omitted, return a catalog listing in `<relative_path> — <H1 heading>` form (D-09), NOT the pack's own SKILL.md content.
- When no slug match: list Levenshtein suggestions at distance <= 3 and HALT — do NOT auto-execute, even at distance 1 (D-11).
- Below `NO_MATCH_FLOOR`: explicit "no match" message (D-10), NOT a weak hit.

---

## INITIALIZATION

### Configuration Loading

Load config from `{project-root}/_gomad/agile/config.yaml` only as needed for:

- `project_name`, `communication_language` (formatting cosmetics only)
- `<installRoot>` resolution — if unset, default to `{project-root}/_gomad`.

### Paths

- `{kb_root}` = `<installRoot>/_config/kb`
- `{pack_dir}` = `{kb_root}/{{domain_slug}}` (computed in step 2 via `discover-inputs.md`)

### Inputs

- `{{domain_slug}}` (required, caller-provided)
- `{{query}}` (optional, caller-provided; empty string triggers catalog-listing mode)

### Algorithmic Constants (hardcoded per D-10; no config override)

These constants are fixed in this file. There is no configuration surface of any kind — no external tuning mechanism, no runtime-environment knob, no configuration-file override. See Section "Why these constants are hardcoded" at the bottom for rationale.

- **BM25 parameters:**
  - `k1 = 1.2` (term-frequency saturation — standard Okapi default per STACK.md section 3)
  - `b = 0.75` (length-normalization strength — standard Okapi default)
- **NO_MATCH_FLOOR = 0.5** (empirical; tune if seed packs produce false negatives in v1.4+)
- **LEVENSHTEIN_MAX = 3** (D-11: suggestions only within edit distance <= 3)
- **Tokenization rule:** lowercase → split on non-alphanumeric runs → drop tokens shorter than 3 characters

---

## EXECUTION

<workflow>

<step n="1" goal="Validate inputs and slug shape">
  <check if="{{domain_slug}} is not provided">
    <output>🚫 Missing required parameter: {domain_slug}</output>
    <output>Usage: gm-domain-skill {domain_slug} [query]</output>
    <action>HALT</action>
  </check>

  <!-- T-10-04-01 / T-10-04-02: path-traversal guard. Reject before touching filesystem. -->
  <check if="{{domain_slug}} contains '/', '\\', '..', OR starts with '.' OR starts with '_'">
    <output>🚫 Invalid slug "{{domain_slug}}": slugs must not contain path separators, '..', or start with '.' / '_'.</output>
    <action>HALT</action>
  </check>

<action>If {{query}} is not provided, set {query} = "" (empty string — triggers catalog-listing mode in step 3).</action>
</step>

<step n="2" goal="Load pack state via discover-inputs.md">
  <action>Read and follow `./discover-inputs.md` to resolve {kb_root}, compute {pack_dir}, and populate {pack_found}, {pack_files}, {pack_files_abs}, {installed_slugs}.</action>
  <note>After this step: {pack_found} is true/false; on true, {pack_files} (relative) and {pack_files_abs} (absolute) are populated. On false, {installed_slugs} lists immediate subdirectories of {kb_root} for the Levenshtein fallback.</note>
</step>

<step n="3" goal="Branch on pack_found and query presence">
  <check if="{pack_found} is false">
    <action>GOTO step 6 (Levenshtein fallback per D-11)</action>
  </check>
  <check if="{query} is empty">
    <action>GOTO step 5 (catalog listing per D-09)</action>
  </check>
  <action>GOTO step 4 (BM25 retrieval per D-08)</action>
</step>

<step n="4" goal="BM25 retrieval — pack found, query provided (D-08)">
  <critical>📊 BM25 SCORING — rank {pack_files_abs} by relevance to {query}; return single best-matching file content if top score > NO_MATCH_FLOOR; else explicit "no match" (D-10).</critical>

<action>INDEXING — for each file `f` in `{pack_files_abs}`, read full content into `{doc_content[f]}`, tokenize (lowercase → split on non-alphanumeric runs → drop tokens shorter than 3 chars), store tokens as `{doc_tokens[f]}` and length `|doc_tokens[f]|` as `{doc_len[f]}`. Compute `{avg_doc_len}` = mean of all `{doc_len[f]}` values. Let `N = |{pack_files_abs}|`.</action>

<action>QUERY TOKENIZATION — tokenize `{query}` with the SAME rule. Deduplicate the result. Store as `{query_tokens}`.</action>

  <check if="{query_tokens} is empty after tokenization">
    <!-- Query degraded to zero tokens (e.g. "a b" or punctuation-only). Fall through to catalog so caller gets actionable output. -->
    <output>Query "{query}" tokenizes to zero usable terms (min token length is 3 characters).</output>
    <action>GOTO step 5</action>
  </check>

<action>IDF — for each token `q` in `{query_tokens}`: let `n` = number of files `f` such that `q` appears in `{doc_tokens[f]}`. Compute IDF using the formula below. The `1 +` smoothing guarantees `idf[q] >= 0` even when `n = N`.</action>

```
idf[q] = log( 1 + (N - n + 0.5) / (n + 0.5) )
```

<action>SCORING (BM25 / Okapi) — for each file `f`: for each token `q` in `{query_tokens}`, count `tf[q][f]` = occurrences of `q` in `{doc_tokens[f]}`. Then sum the per-token contribution using the BM25 formula below, with `k1 = 1.2` and `b = 0.75`.</action>

```
                        tf[q][f] * (k1 + 1)
score[f] = Σ  idf[q] * ------------------------------------------------
           q           tf[q][f] + k1 * (1 - b + b * doc_len[f] / avg_doc_len)
```

<action>Sort files by `score[f]` descending; break ties alphabetically by relative path. Let `{top_file}` be the top file's absolute path, `{top_file_rel}` its relative path, `{top_score}` its score.</action>

  <check if="{top_score} <= NO_MATCH_FLOOR (where NO_MATCH_FLOOR = 0.5)">
    <!-- D-10: explicit no-match message, NOT a weak hit. -->
    <output>No match for "{query}" in {{domain_slug}} pack. Try `gm-domain-skill {{domain_slug}}` with no query to list available files.</output>
    <action>HALT</action>
  </check>

<action>Return `{doc_content[top_file]}` unmodified — D-08 requires full file content, NOT an excerpt, NOT a summary, NOT a top-N list.</action>
<action>Append a source-citation footer: `Source: {top_file_rel} ({{domain_slug}} pack) — Score: {top_score} (BM25, k1=1.2, b=0.75)`.</action>
<template-output file="stdout">file_content_response</template-output>
<action>Before returning, load `./checklist.md` and validate the output against Mode A integrity checks; apply any corrections required.</action>
<action>HALT with success</action>
</step>

<step n="5" goal="Catalog listing — pack found, no query (D-09)">
  <critical>📚 CATALOG LISTING — emit one line per .md file in the pack, in `<relative_path> — <H1 heading>` form. Do NOT return SKILL.md content wholesale; the listing itself is the intended UX.</critical>

<action>For each file `f` in `{pack_files}` (relative paths, sorted alphabetically): open the file; strip any YAML frontmatter block (content bounded by leading `---` / trailing `---`). Apply regex `/^#\s+(.+)$/m` to the post-frontmatter content; let `{h1}` be the first match's capture group, trimmed. If no match, set `{h1}` = "(no H1 heading)". Emit one line in the form `{f} — {h1}` (separator is an em-dash surrounded by single spaces).</action>

<action>Order: alphabetical by relative path. SKILL.md (if present in the pack) appears in its alphabetical slot — it is NOT excluded, but it is NOT privileged either.</action>
<action>Prepend a header: `# {{domain_slug}} pack — contents` and a footer inviting query invocation.</action>
<template-output file="stdout">catalog_listing_response</template-output>
<action>Before returning, load `./checklist.md` and validate the output against Mode B integrity checks.</action>
<action>HALT with success</action>
</step>

<step n="6" goal="Levenshtein fallback — pack not found (D-11)">
  <critical>🔤 LEVENSHTEIN SUGGESTION — list slugs with edit distance <= 3 and HALT. Do NOT auto-execute, even at distance 1 (D-11 safety rule — user re-invocation is required).</critical>

<action>LEVENSHTEIN DISTANCE — define `lev(a, b)` between two strings `a`, `b` as the minimum number of single-character edits (insertion / deletion / substitution, each cost 1) to transform `a` into `b`. Compute via the standard O(|a|·|b|) dynamic-programming table described by the recurrence below.</action>

```
dp[i][0] = i
dp[0][j] = j
dp[i][j] = min(
  dp[i-1][j]   + 1,                               // deletion
  dp[i][j-1]   + 1,                               // insertion
  dp[i-1][j-1] + (a[i-1] != b[j-1] ? 1 : 0)       // substitution
)
lev(a, b) = dp[|a|][|b|]
```

<action>For each slug `s` in `{installed_slugs}`: compute `d = lev({{domain_slug}}, s)`. If `d <= LEVENSHTEIN_MAX` (= 3), append `(s, d)` to `{suggestions}`.</action>

<action>Sort `{suggestions}` by `d` ascending, then alphabetically by `s`. Extract names only into `{suggestion_names}`.</action>

  <check if="{suggestions} is non-empty">
    <output>The pack "{{domain_slug}}" is not installed. Did you mean: {suggestion_names} (comma-separated)?</output>
    <output>(Based on Levenshtein distance <= 3 against installed packs.)</output>
    <note>Per D-11: the skill does NOT auto-execute the suggested slug, even if only one suggestion is at distance 1. The user must re-invoke with the corrected slug.</note>
  </check>

  <check if="{suggestions} is empty">
    <output>The pack "{{domain_slug}}" is not installed. Installed packs: {installed_slugs} (comma-separated).</output>
  </check>

<template-output file="stdout">pack_not_installed_response</template-output>
<action>Before returning, load `./checklist.md` and validate the output against Mode D integrity checks (verify no auto-execute, verify distance <= 3 rule).</action>
<action>HALT (non-success signal — caller decides whether to retry with a suggested slug).</action>
</step>

</workflow>

---

## Why these constants are hardcoded (D-10)

`NO_MATCH_FLOOR`, `k1`, `b`, and `LEVENSHTEIN_MAX` are hardcoded here with short rationales. These constants are load-bearing — the skill provides no configuration surface whatsoever (no external tuning mechanism, no runtime-environment knob, no configuration-file override). Rationale:

- **Zero-new-deps ethos extends to zero-new-config-surface.** Every knob is a deferred decision users have to make; v1.3 prefers sane defaults over configurability.
- **v1.3 seed packs are small.** D-12 caps initial scope at ~2 packs with ~10 files each; tuning is speculative without real-world telemetry.
- **Revisit in a patch release with concrete data.** If empirically wrong post-v1.3 (false-negative reports from real users, not speculation), bump `NO_MATCH_FLOOR` in a patch release with a short CHANGELOG entry citing the seed data. Same for `LEVENSHTEIN_MAX` if 3 proves too lax/strict.

The design deliberately trades a theoretical tuning surface for a simpler, more predictable contract.

---

## References

- Decision IDs: D-08 (single-best-file return), D-09 (catalog listing format), D-10 (no-config-surface + no-match floor), D-11 (Levenshtein halt-not-auto-execute).
- STACK.md section 3 — BM25 / Okapi reference implementation (~50 LOC Python pseudocode) that this prose describes at algorithmic parity.
- PITFALLS.md sections 4-G (typo fallback) and 4-H (length normalization — handled by BM25 `b` parameter).
- Validation: `./checklist.md` Modes A/B/C/D; each step invokes the matching mode before HALT.
