# gm-domain-skill output templates

Four output modes, selected by the workflow branch. Each `<template-output>` tag in `workflow.md` references one of the block IDs below.

---

## Mode A — file_content_response (D-08 best-match)

{{top_file_content}}

---

_Source: {{top_file_relative_path}} ({{domain_slug}} pack)_
_Score: {{top_score}} (BM25, k1=1.2, b=0.75)_

---

## Mode B — catalog_listing_response (D-09 no query)

# {{domain_slug}} pack — contents

{{catalog_lines}}

---

_Pack installed at: {{pack_dir}}_
_Invoke `gm-domain-skill {{domain_slug}} "<query>"` to retrieve the best-matching file._

---

## Mode C — no_match_response (D-10)

No match for "{{query}}" in {{domain_slug}} pack.

Try `gm-domain-skill {{domain_slug}}` with no query to list available files.

---

## Mode D — pack_not_installed_response (D-11)

The pack "{{domain_slug}}" is not installed.

{{did_you_mean_line}}

Installed packs: {{installed_slugs_csv}}.

_(Per D-11: the skill does NOT auto-execute a suggested slug, even at edit distance 1. Re-invoke with the corrected slug.)_
