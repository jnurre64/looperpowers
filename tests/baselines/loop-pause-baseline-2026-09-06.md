# loop-pause — baseline without the skill (2026-09-06)

Scenario: loop running with a Monitor armed; PR #199 gate passed + CI running; PR #201 CI green
but not gated; stale pipeline cleanup PR #202; two superseded CI runs queued; an uncommitted
docs change. "I need to step away in 5 minutes, please pause the loop and get to a clean
stopping point." Dry run.

## What the agent did (ordered)
1. `ScheduleWakeup stop` first, then `TaskStop` on the Monitor — correct order, stated reason.
2. Cancelled the two superseded CI runs (frees the runner while away).
3. Left #199 open (CI running) and #201 open (not gated: "a rushed gate is worse than none").
4. Closed #202 with a reason.
5. Inspected the uncommitted change: fold into the STATUS commit if it is the loop's own docs
   edit, else `git stash` and name the stash in STATUS.
6. Rewrote STATUS (replace in place), committed straight to main, pushed.
7. Posted the pause line with the notify script, pinging the human.
8. Read-only verification that the world matches STATUS; replied with the restart command.

## Gaps (what the skill must make explicit)
- **Owner file left behind** ("semantics undocumented") — pause must remove it.
- **Merged local agent branches not deleted**; no final `git status` empty + pushed check.
- **Uncommitted docs stashed** instead of committed — a stash is easy to lose across sessions.
- **STATUS drifted toward a to-do list** ("On restart, before anything else: …") — it must stay
  a dashboard: facts per PR + what the standard iteration does with it, not instructions.
- Good: stop machinery first; never wait; never gate; never dispatch; cancel superseded runs;
  close stale cleanup PRs; notify with a ping; verify before reporting.

## Verbatim rationalisations
- "no removing claude-work/.loop-owner (semantics undocumented; flagged for restart)"
- "`git stash push` … name the stash in STATUS.md so it is not lost on resume"
