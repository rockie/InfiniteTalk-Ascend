# Step 4: User Journey Mapping

**Progress: Step 4 of 13** - Next: Domain Requirements

## MANDATORY EXECUTION RULES (READ FIRST):

- 🛑 NEVER generate content without user input

- 📖 CRITICAL: ALWAYS read the complete step file before taking any action - partial understanding leads to incomplete decisions
- 🔄 CRITICAL: When loading next step with 'C', ensure the entire file is read and understood before proceeding
- ✅ ALWAYS treat this as collaborative discovery between PM peers
- 📋 YOU ARE A FACILITATOR, not a content generator
- 💬 FOCUS on mapping ALL user types that interact with the system
- 🎯 CRITICAL: No journey = no functional requirements = product doesn't exist
- ✅ YOU MUST ALWAYS SPEAK OUTPUT In your Agent communication style with the config `{communication_language}`
- ✅ YOU MUST ALWAYS WRITE all artifact and document content in `{document_output_language}`

## EXECUTION PROTOCOLS:

- 🎯 Show your analysis before taking any action
- ⚠️ Present A/P/C menu after generating journey content
- 💾 ONLY save when user chooses C (Continue)
- 📖 Update output file frontmatter, adding this step name to the end of the list of stepsCompleted
- 🚫 FORBIDDEN to load next step until C is selected

## CONTEXT BOUNDARIES:

- Current document and frontmatter from previous steps are available
- Success criteria and scope already defined
- Input documents from step-01 are available (product briefs with user personas)
- Every human interaction with the system needs a journey

## YOUR TASK:

Create action-oriented user journeys with minimal personas (name + role + goal), identifying all user types needed for comprehensive capability coverage.

## JOURNEY MAPPING SEQUENCE:

### 1. Leverage Existing Users & Identify Additional Types

**Check Input Documents for Existing Personas:**
Analyze product brief, research, and brainstorming documents for user personas already defined.

**If User Personas Exist in Input Documents:**
Guide user to build on existing personas:
- Acknowledge personas found in their product brief
- Extract key persona details and backstories
- Leverage existing insights about their needs
- Prompt to identify additional user types beyond those documented
- Suggest additional user types based on product context (admins, moderators, support, API consumers, internal ops)
- Ask what additional user types should be considered

**If No Personas in Input Documents:**
Start with comprehensive user type discovery:
- Guide exploration of ALL people who interact with the system
- Consider beyond primary users: admins, moderators, support staff, API consumers, internal ops
- Ask what user types should be mapped for this specific product
- Ensure comprehensive coverage of all system interactions

### 2. Create Action-Oriented Journeys

For each user type, create action-oriented journeys with **name + role + goal** only. Persona framework is minimal — coding agents implement observable behaviors, not narrative storytelling.

#### Journey Creation Process:

**Persona fields (minimal):**
- **Name** — identifier only (no demographic markers, no backstory, no personality traits)
- **Role** — how they relate to the system (e.g., "admin", "end-user", "API consumer")
- **Goal** — observable outcome they need from the system

**If Using Existing Persona from Input Documents:**
Extract name + role + goal only; discard any backstory, narrative-storytelling probes, or demographic markers from the source material. If the input persona has no explicit role, derive it from the user's relationship to the system in the brief.

**If Creating New Persona:**
Define name, role, and goal in a single line each. Do NOT prompt the user for personality, situation, obstacle, or solution-narrative — those are implementation-agnostic and belong in FRs downstream.

**Journey prose shape (mandatory form):**

"Actor performs X, system responds Y, outcome Z."

For each journey:
- Describe the triggering action (what the actor does)
- Describe the system's observable response
- Describe the resulting state / outcome
- Flag edge cases and error paths as separate journey entries (not narrative asides)

This form maps 1:1 to FR acceptance-criteria candidates in step 9 (Given/When/Then).

**Why this shape:** Downstream coding agents extract capability requirements from journey prose. Narrative structure (opening, middle, ending arcs) adds noise; action-oriented prose maps directly to testable behaviors.

### 3. Guide Journey Exploration

For each journey, facilitate detailed exploration:
- What happens at each step specifically?
- What could go wrong? What's the recovery path?
- What information do they need to see/hear?
- What is the observable system state at each point?
- Where does this journey succeed or fail?

### 4. Connect Journeys to Requirements

After each journey, explicitly state:
- This journey reveals requirements for specific capability areas
- Help user see how different journeys create different feature sets
- Connect journey needs to concrete capabilities (onboarding, dashboards, notifications, etc.)

### 5. Aim for Comprehensive Coverage

Guide toward complete journey set:

- **Primary user** - happy path (core experience)
- **Primary user** - edge case (different goal, error recovery)
- **Secondary user** (admin, moderator, support, etc.)
- **API consumer** (if applicable)

Ask if additional journeys are needed to cover uncovered user types

### 6. Generate User Journey Content

Prepare the content to append to the document:

#### Content Structure:

When saving to document, append these Level 2 and Level 3 sections:

```markdown
## User Journeys

[All journey narratives based on conversation]

### Journey Requirements Summary

[Summary of capabilities revealed by journeys based on conversation]
```

### 7. Present MENU OPTIONS

Present the user journey content for review, then display menu:
- Show the mapped user journeys (using structure from section 6)
- Highlight how each journey reveals different capabilities
- Ask if they'd like to refine further, get other perspectives, or proceed
- Present menu options naturally as part of conversation

Display: "**Select:** [A] Advanced Elicitation [P] Party Mode [C] Continue to Domain Requirements (Step 5 of 13)"

#### Menu Handling Logic:
- IF A: Invoke the `gm-advanced-elicitation` skill with the current journey content, process the enhanced journey insights that come back, ask user "Accept these improvements to the user journeys? (y/n)", if yes update content with improvements then redisplay menu, if no keep original content then redisplay menu
- IF P: Invoke the `gm-party-mode` skill with the current journeys, process the collaborative journey improvements and additions, ask user "Accept these changes to the user journeys? (y/n)", if yes update content with improvements then redisplay menu, if no keep original content then redisplay menu
- IF C: Append the final content to {outputFile}, update frontmatter by adding this step name to the end of the stepsCompleted array, then read fully and follow: ./step-05-domain.md
- IF Any other: help user respond, then redisplay menu

#### EXECUTION RULES:
- ALWAYS halt and wait for user input after presenting menu
- ONLY proceed to next step when user selects 'C'
- After other menu items execution, return to this menu

## APPEND TO DOCUMENT:

When user selects 'C', append the content directly to the document using the structure from step 6.

## SUCCESS METRICS:

✅ Existing personas from product briefs leveraged when available
✅ All user types identified (not just primary users)
✅ Action-oriented journey prose for each persona (Actor performs X, system responds Y, outcome Z)
✅ Complete action-oriented journey mapping covering all user types
✅ Journey requirements clearly connected to capabilities needed
✅ Minimum 3-4 journeys covering different user types per the Minimum Coverage list
✅ A/P/C menu presented and handled correctly
✅ Content properly appended to document when C selected

## FAILURE MODES:

❌ Ignoring existing personas from product briefs
❌ Only mapping primary user journeys and missing secondary users
❌ Missing critical decision points and failure scenarios
❌ Not connecting journeys to required capabilities
❌ Not having enough journey diversity (admin, support, API, etc.)
❌ Not presenting A/P/C menu after content generation
❌ Appending content without user selecting 'C'

❌ **CRITICAL**: Reading only partial step file - leads to incomplete understanding and poor decisions
❌ **CRITICAL**: Proceeding with 'C' without fully reading and understanding the next step file
❌ **CRITICAL**: Making decisions without complete understanding of step requirements and protocols

## JOURNEY TYPES TO ENSURE:

**Minimum Coverage:**

1. **Primary User - Success Path**: Core experience journey
2. **Primary User - Edge Case**: Error recovery, alternative goals
3. **Admin/Operations User**: Management, configuration, monitoring
4. **Support/Troubleshooting**: Help, investigation, issue resolution
5. **API/Integration** (if applicable): Developer/technical user journey

## NEXT STEP:

After user selects 'C' and content is saved to document, load `./step-05-domain.md`.

Remember: Do NOT proceed to step-05 until user explicitly selects 'C' from the A/P/C menu and content is saved!
