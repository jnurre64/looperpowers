# loop-setup — baseline without the skill (2026-09-06)

Scenario: FingerWizard scratch clone (has docs/LOOP.md, no STATUS, no start block), Anomalistics
as the reference shape. "Set FingerWizard up so the loop can be paused and resumed the same
way … quick please." Dry run.

## What the agent did (ordered)
1. Discovered all nine values read-only (gh repo view, gh project list, CLAUDE.md, scripts/);
   asked nothing; flagged the bot_user ambiguity in one line. Good.
2. Would create loop.json and STATUS.md (seeded from the live gh state + the existing
   hand-off doc), append a "Starting the loop" block to LOOP.md (append only). Good.
3. Would ALSO edit CLAUDE.md, the hand-off doc, and DECISIONS.md, and add a project-specific
   CI rule to the STATUS contract.
4. One docs commit straight to main, pushed only when no main CI run is in progress.

## Gaps (what the skill must fix)
- **Schema drift:** `board` written as a URL string; the other skills read
  `{"org", "number", "done"}`. `notify` without `./` prefix. The skill owns the schema.
- **No `.gitignore` entry** for `claude-work/.loop-owner`.
- **Scope creep:** CLAUDE.md / hand-off / DECISIONS edits are useful suggestions, not setup's
  job. Setup writes exactly: loop.json, STATUS.md (if absent), LOOP.md (template if absent,
  start block if missing), .gitignore line. Everything else is printed as "suggested next".
- **Start block written free-hand** with project-specific clauses inlined. Fine to add clauses,
  but the base must be the template block so every project starts from the same contract.
- Good: discovery table with sources; append-only on an existing LOOP.md; one docs commit.
