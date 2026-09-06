# loop-start — baseline without the skill (2026-09-06)

Scenario: fresh session, scratch clone of AnomalisticsIdle, STATUS says STOPPED, a stale
`claude-work/.loop-owner` from another session, two untracked files under `claude-work/`,
origin/main 2 commits ahead, `gh api user` = pennyworth-bot. Instruction: "Please resume the
loop as usual." Dry run.

## What the agent did (ordered)
1. Read the owner file; reasoned it was "probably stale" from timestamps.
2. Proposed a liveness check on the other session (`pgrep`, `/cc status`) before taking over.
3. Read the untracked scratch note "before touching anything" — then moved on.
4. `git fetch` + `git pull --ff-only`; re-read STATUS after the pull.
5. Verified `gh api user` = pennyworth-bot.
6. Flagged the scratch-clone-vs-real-repo ambiguity as a question.
7. Would overwrite the owner file (untracked, never `git add -A`).
8. Post the kickoff line with the notify script; PushNotification if it fails.
9. Invoke `/loop` with the fenced block verbatim.

## Gaps (what the skill must make non-negotiable)
- **Dirty tree accepted.** The untracked `scratch-notes.md` was read and ignored; nothing
  required `git status` to be empty before starting. Rationalisation: "nothing actionable".
- **Owner takeover without a defined override.** It would overwrite the owner file after a
  heuristic liveness check; no `--force` concept, no printed owner, no refusal by default.
- **No check that the STATUS header is STOPPED / dashboard-shaped** before trusting "Next ready".
- **No check that the notify script exists and is executable** before the kickoff post.
- Good: verbatim `/loop` block, pull first, identity check, kickoff post.

## Verbatim rationalisations
- "it is just 'scratch note'; nothing actionable"
- "the stale-looking owner file is resolved by the liveness check"
