# Discuss Story Workflow

**Goal:** Crystallize gray areas for a planned story BEFORE gm-create-story runs, producing `{planning_artifacts}/{{story_key}}-context.md` with 5 locked sections (domain, decisions, canonical_refs, specifics, deferred).

**Your Role:** Gray-area elicitation engine that surfaces acceptance-criteria edge cases, NFRs, data-model ambiguities, and downstream contracts BEFORE story drafting begins.

- Communicate all responses in {communication_language} and generate all documents in {document_output_language}
- Your purpose is NOT to re-ask PRD questions — it's to probe ambiguity in THIS story's scope that a coding agent would need resolved.
- **capture decisions, not discussion transcripts.** Be surgical. No verbose preambles. No re-statement of the question in the decision record.
- GROUND EVERY GRAY AREA in the target story's epics entry (acceptance criteria, technical requirements). Do NOT drift into generic interview questions.
- ZERO USER INTERVENTION except: initial story selection (if not auto-discoverable), gray-area multi-select, per-area focused Q&A, transition checks, final gate.

---

## INITIALIZATION

### Configuration Loading

Load config from `{project-root}/_gomad/agile/config.yaml` and resolve:

- `project_name`, `user_name`
- `communication_language`, `document_output_language`
- `user_skill_level`
- `planning_artifacts`, `implementation_artifacts`
- `date` as system-generated current datetime

### Paths

- `sprint_status` = `{implementation_artifacts}/sprint-status.yaml`
- `epics_file` = `{planning_artifacts}/epics.md`
- `prd_file` = `{planning_artifacts}/prd.md`
- `architecture_file` = `{planning_artifacts}/architecture.md`
- `ux_file` = `{planning_artifacts}/*ux*.md`
- `default_output_file` = `{planning_artifacts}/{{story_key}}-context.md`
- `checkpoint_file` = `{planning_artifacts}/{{story_key}}-discuss-checkpoint.json`

### Input Files

| Input | Description | Path Pattern(s) | Load Strategy |
|-------|-------------|------------------|---------------|
| prd | PRD (fallback - epics file should have most content) | whole: `{planning_artifacts}/*prd*.md`, sharded: `{planning_artifacts}/*prd*/*.md` | SELECTIVE_LOAD |
| architecture | Architecture (fallback - epics file should have relevant sections) | whole: `{planning_artifacts}/*architecture*.md`, sharded: `{planning_artifacts}/*architecture*/*.md` | SELECTIVE_LOAD |
| ux | UX design (fallback - epics file should have relevant sections) | whole: `{planning_artifacts}/*ux*.md`, sharded: `{planning_artifacts}/*ux*/*.md` | SELECTIVE_LOAD |
| epics | Enhanced epics+stories file with BDD and source hints | whole: `{planning_artifacts}/*epic*.md`, sharded: `{planning_artifacts}/*epic*/*.md` | SELECTIVE_LOAD |

---

## CHECKPOINT JSON SCHEMA

`{{checkpoint_file}}` (resolves to `{planning_artifacts}/{{story_key}}-discuss-checkpoint.json`) is written after EACH area's Q&A completes (D-05). Schema:

```json
{
  "story_key": "{{story_key}}",
  "timestamp": "ISO-8601 timestamp",
  "areas_completed": ["Area 1 label", "Area 2 label"],
  "areas_remaining": ["Area 3 label", "Area 4 label"],
  "decisions": {
    "Area 1 label": [
      {"question": "...", "answer": "...", "options_presented": ["..."]}
    ]
  },
  "deferred_ideas": ["..."],
  "canonical_refs": ["..."]
}
```

The checkpoint is deleted on successful `{{default_output_file}}` write (D-05 cleanup).

---

## EXECUTION

<workflow>

<step n="1" goal="Determine target story">
  <check if="{{story_path}} is provided by user or user provided the epic and story number such as 2-4 or 1.6 or epic 1 story 5">
    <action>Parse user-provided story path: extract epic_num, story_num, story_title from format like "1-2-user-auth"</action>
    <action>Set {{epic_num}}, {{story_num}}, {{story_key}} from user input</action>
    <action>GOTO step 2</action>
  </check>

  <action>Check if {{sprint_status}} file exists for auto discover</action>
  <check if="sprint status file does NOT exist">
    <output>No sprint status file found and no story specified</output>
    <output>
      **Required Options:**
      1. Run `sprint-planning` to initialize sprint tracking (recommended)
      2. Provide specific epic-story number to discuss (e.g., "1-2-user-auth")
      3. Provide path to story documents if sprint status doesn't exist yet
    </output>
    <ask>Choose option [1], provide epic-story number, path to story docs, or [q] to quit:</ask>

    <check if="user chooses 'q'">
      <action>HALT - No work needed</action>
    </check>

    <check if="user chooses '1'">
      <output>Run sprint-planning workflow first to create sprint-status.yaml</output>
      <action>HALT - User needs to run sprint-planning</action>
    </check>

    <check if="user provides epic-story number">
      <action>Parse user input: extract epic_num, story_num, story_title</action>
      <action>Set {{epic_num}}, {{story_num}}, {{story_key}} from user input</action>
      <action>GOTO step 2</action>
    </check>

    <check if="user provides story docs path">
      <action>Use user-provided path for story documents</action>
      <action>GOTO step 2</action>
    </check>
  </check>

  <check if="no user input provided">
    <critical>MUST read COMPLETE {{sprint_status}} file from start to end to preserve order</critical>
    <action>Load the FULL file: {{sprint_status}}</action>
    <action>Parse the development_status section completely</action>
    <action>Find the FIRST story (by reading in order from top to bottom) where:
      - Key matches pattern: number-number-name (e.g., "1-2-user-auth")
      - NOT an epic key (epic-X) or retrospective (epic-X-retrospective)
      - Status value equals "backlog"
    </action>

    <check if="no backlog story found">
      <output>No backlog stories found in sprint-status.yaml — all stories are created, in progress, or done.</output>
      <action>HALT</action>
    </check>

    <action>Extract epic_num, story_num, story_title from the matched key</action>
    <action>Set {{story_key}} (e.g., "1-2-user-authentication")</action>
    <action>GOTO step 2</action>
  </check>
</step>

<step n="2" goal="Detect existing state — checkpoint and/or context.md">
  <action>Check existence of {{checkpoint_file}} and {{default_output_file}}</action>

  <check if="both checkpoint and context.md exist">
    <!-- D-07: context.md wins, stale checkpoint deleted -->
    <action>Delete {{checkpoint_file}} (stale — a completed discussion supersedes a resume token)</action>
    <output>Stale discussion checkpoint detected ({{default_output_file}} already exists). Deleted checkpoint; treating as re-opening a completed discussion.</output>
    <action>GOTO step 3b (Update/View/Skip)</action>
  </check>

  <check if="only checkpoint exists">
    <!-- D-05: Resume / Start fresh -->
    <action>Load checkpoint: areas_completed[], areas_remaining[], decisions{}</action>
    <ask>
      header: "Resume"
      question: "Found interrupted discussion checkpoint ({N} areas completed out of {M}). Resume where you left off?"
      options:
        - "Resume" — Load checkpoint, skip completed areas, continue from remaining
        - "Start fresh" — Delete checkpoint, re-identify gray areas from scratch
    </ask>
    <check if="user chose Resume">
      <action>Load decisions{} into in-memory accumulator</action>
      <action>Set {{areas_selected}} = areas_completed ∪ areas_remaining; set working pointer to areas_remaining</action>
      <action>GOTO step 5 (skip to remaining areas)</action>
    </check>
    <check if="user chose Start fresh">
      <action>Delete {{checkpoint_file}}</action>
      <action>GOTO step 3a (identify gray areas)</action>
    </check>
  </check>

  <check if="only context.md exists">
    <!-- D-06: Update / View / Skip -->
    <action>GOTO step 3b</action>
  </check>

  <check if="neither exists">
    <action>Load shared inputs now</action>
    <action>Read fully and follow `./discover-inputs.md` to load all input files (prd, architecture, ux, epics) per the Input Files table above</action>
    <note>Available content: {epics_content}, {prd_content}, {architecture_content}, {ux_content}</note>
    <action>GOTO step 3a (fresh discussion)</action>
  </check>
</step>

<step n="3a" goal="Identify gray areas grounded in the target story">
  <critical>Ground every gray area in the target story's epics entry — not generic interview questions.</critical>
  <action>If inputs not yet loaded, read fully and follow `./discover-inputs.md` to load all input files</action>
  <action>From {epics_content}, extract story {{epic_num}}-{{story_num}} entry: acceptance criteria, technical requirements, dependencies</action>
  <action>Cross-reference against {prd_content}, {architecture_content}, {ux_content} to surface contradictions, underspecified edges, and unresolved design questions</action>
  <action>Enumerate 3-5 gray areas with concrete labels (e.g., "AC#2 edge: empty input vs whitespace vs script tags", NOT "Input validation approach")</action>
  <note>Each gray area must cite at least one concrete source (AC number, architecture section, UX wireframe) — no speculative areas.</note>
  <action>Store enumerated gray areas as {{candidate_gray_areas}}</action>
  <action>GOTO step 4</action>
</step>

<step n="3b" goal="Update / View / Skip (D-06)">
  <ask>
    header: "Existing context"
    question: "{{default_output_file}} already exists. What now?"
    options:
      - "Update" — Load existing decisions as pre-filled, continue discussion
      - "View" — Display current context.md, then re-prompt Update/Skip
      - "Skip" — Exit without changes
  </ask>
  <check if="user chose Update">
    <action>Parse existing {{default_output_file}} sections into pre-filled decision accumulator</action>
    <action>Read fully and follow `./discover-inputs.md` to load all input files</action>
    <action>GOTO step 3a (identify new or remaining gray areas)</action>
  </check>
  <check if="user chose View">
    <output>{{display {{default_output_file}} content}}</output>
    <ask>Choose: Update / Skip</ask>
    <action>Re-branch per the above (Update → GOTO step 3a; Skip → HALT)</action>
  </check>
  <check if="user chose Skip">
    <action>HALT — no changes</action>
  </check>
</step>

<step n="4" goal="User multi-selects gray areas">
  <!-- Analog: discuss-phase.md:594-620 -->
  <ask>
    header: "Discuss"
    question: "Which areas do you want to discuss for story {{story_key}}?"
    multiSelect: true
    options: [each entry from {{candidate_gray_areas}} as a label with 1-2 probing questions in the description]
    recommended: [highlight the area with the most cross-doc contradictions OR most acceptance-criteria edge cases]
  </ask>
  <note>Do NOT include "skip" or "you decide" options. User ran this command to discuss.</note>
  <action>Set {{areas_selected}} = user's selections</action>
  <action>If accumulator empty (no Resume path): set {{areas_completed}} = []; set {{decisions}} = {}; set {{deferred_ideas}} = []; set {{canonical_refs}} = []</action>
</step>

<step n="5" goal="Per-area Q&A loop with transition checks">
  <action>FOR EACH area IN {{areas_selected}} NOT IN {{areas_completed}}:</action>
  <action>  Ask ~4 focused questions with 2-3 concrete options each</action>
  <note>Concrete = specific values, file paths, library names — never abstract like "your preference". Each question must advance the story's scope, not re-ask PRD-level questions.</note>
  <action>  Append { question, answer, options_presented } to decisions[area] after each answer</action>
  <action>  After the ~4 questions for this area finish (or user moves on), append area to {{areas_completed}}</action>
  <action>  Write checkpoint JSON to {{checkpoint_file}} (i.e. `{planning_artifacts}/{{story_key}}-discuss-checkpoint.json`) with current accumulators (D-05)</action>
  <ask>transition: "More questions about [area], or move to next?"</ask>
  <check if="user says more">
    <action>Continue Q&A on same area (append more decisions; keep area in {{areas_completed}} — the next transition will decide again)</action>
  </check>
  <check if="user says next OR area's 4 questions done">
    <action>Loop to next area in {{areas_selected}}</action>
  </check>
  <action>When {{areas_selected}} fully processed, GOTO step 6</action>
</step>

<step n="6" goal="Final gate">
  <ask>
    header: "Ready to close discussion?"
    question: "Ready to generate context.md, or explore more gray areas?"
    options:
      - "Ready for context" — Write context.md and exit
      - "Explore more" — Re-open step 3a to add new gray areas
  </ask>
  <check if="user chose Explore more">
    <action>GOTO step 3a (identify additional gray areas; append to {{candidate_gray_areas}})</action>
  </check>
  <check if="user chose Ready for context">
    <action>GOTO step 7</action>
  </check>
</step>

<step n="7" goal="Adaptive mapping to 5 sections + write context.md">
  <!-- D-03: adaptive mapping by semantic fit -->
  <action>Map each accumulated decision into one of 5 sections by content semantics:
    - domain: story boundary/scope clarifications
    - decisions: concrete resolved answers (question → answer)
    - canonical_refs: file paths, links, source citations (AC#, architecture section)
    - specifics: user-framed ideas, quotes, or references
    - deferred: items user explicitly deferred out of this story
  </action>
  <note>Mapping is by content semantics, NOT by a fixed category → section lookup table. capture decisions, not discussion transcripts.</note>
  <action>Initialize from template.md: {{default_output_file}}</action>
  <template-output file="{default_output_file}">context_header</template-output>
  <template-output file="{default_output_file}">domain</template-output>
  <template-output file="{default_output_file}">decisions</template-output>
  <template-output file="{default_output_file}">canonical_refs</template-output>
  <template-output file="{default_output_file}">specifics</template-output>
  <template-output file="{default_output_file}">deferred</template-output>
  <action>Save {{default_output_file}}</action>
  <action>Delete {{checkpoint_file}} (i.e. `{planning_artifacts}/{{story_key}}-discuss-checkpoint.json`) — D-05 cleanup, discuss-phase.md:949 analog</action>
</step>

<step n="8" goal="Validate + finalize">
  <action>Validate the newly created {{default_output_file}} against `./checklist.md` and apply any required fixes</action>
  <output>
    **Discussion context captured, {user_name}!**

    - Story: {{story_key}}
    - File: {{default_output_file}}
    - Sections populated: [list of non-empty sections]

    **Next step:** Run `gm-create-story` — it will auto-load this context via discover-inputs.md.
  </output>
</step>

</workflow>
