# Discover Inputs Protocol (Domain-KB Retrieval)

**Objective:** Load the installed domain-KB pack for a given slug, or produce a "pack not installed" signal for the workflow to branch on.

**Prerequisite:** This skill has exactly ONE input group — the installed KB directory. No PRD/epics/architecture/UX needed (unlike `gm-create-story`, which loads four input groups).

---

## Step 1: Resolve Pack Location

Resolve `{kb_root}` = `<installRoot>/_config/kb` — the directory where the installer landed `src/domain-kb/*` during `gomad install` (per STORY-11).

If `<installRoot>` is unset in the runtime context, resolve it from the config loaded in `workflow.md` INITIALIZATION (default: `{project-root}/_gomad/_config/kb`).

This is the ONLY directory the skill ever reads from. The skill never writes; filesystem access is strictly read-only and rooted at `{kb_root}`.

## Step 2: Validate Slug Shape (Traversal Guard)

Before touching the filesystem, reject any `{{domain_slug}}` that:

- Contains `/` or `\` (path-separator injection)
- Contains `..` as a substring (parent-directory traversal)
- Starts with `.` (hidden directory) or `_` (reserved/underscore-prefixed — skipped during the walk)

On any of these conditions, emit `🚫 Invalid slug "{{domain_slug}}": slugs must not contain path separators, "..", or leading "."/"_"`, set `{pack_found}` = false, and skip Step 3 — the workflow's Levenshtein fallback still runs against installed packs because the user may have typed a real-but-mangled slug.

## Step 3: Check Pack Existence

- If `{{domain_slug}}` is provided by the caller and passes Step 2:
  - Compute `{pack_dir}` = `{kb_root}/{{domain_slug}}`.
  - If `{pack_dir}` exists AND is a non-empty directory:
    - Set `{pack_found}` = true.
    - Enumerate all `.md` files under `{pack_dir}` recursively, **SKIPPING** any directory whose name starts with `.` or `_`.
    - Store relative paths (relative to `{pack_dir}`) in `{pack_files}` and absolute paths in `{pack_files_abs}`.
    - Record the count in `{pack_file_count}` for the success report.
  - If `{pack_dir}` does NOT exist, OR is empty, OR is not a directory:
    - Set `{pack_found}` = false.
    - Enumerate all immediate subdirectories of `{kb_root}` (skipping `.`/`_`-prefixed entries) and store names in `{installed_slugs}` — the list the workflow will pass to Levenshtein fallback.

## Step 4: Report Discovery Results

- On success (`{pack_found}` = true): `OK Loaded {{domain_slug}} pack: {pack_file_count} files discovered at {pack_dir}`.
- On pack-not-found (`{pack_found}` = false): `-- Pack {{domain_slug}} not installed. Installed packs: {installed_slugs} (for Levenshtein fallback)`.
- On slug-rejected (`{pack_found}` = false, Step 2 failure): also includes the rejection reason from Step 2.

This gives `workflow.md` the state it needs to branch between four behaviors:

- BM25 retrieval (pack found + query provided) — Mode A
- Catalog listing (pack found + no query) — Mode B
- No-match message (pack found + query with score <= `NO_MATCH_FLOOR`) — Mode C
- Levenshtein "did you mean" (pack not found) — Mode D
