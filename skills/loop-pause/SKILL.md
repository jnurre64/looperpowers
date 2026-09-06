---
name: loop-pause
description: Use when the user asks to pause, stop, halt or wind down the orchestrator loop, or to "get to a clean stopping point" so it can be resumed later, in a project that has claude-work/loop.json.
argument-hint: "[drain]"
user-invocable: true
---

# loop-pause

Reach a clean, clear stopping point and leave the project ready for `/loop-start`. **Order
matters and every step has a check.** The rule: **finish what is cheap, wait for nothing**
(`drain` is the one exception, §2).

## 0. Load the project data

`cat claude-work/loop.json` (missing → stop: "run /loop-setup first"); read `status_file`.

## 1. Stop the machinery FIRST

1. `ScheduleWakeup` with `stop: true`.
2. `TaskList`, then `TaskStop` every monitor this loop armed.

Nothing else happens before this: an iteration firing mid-pause can dispatch or merge under
you.

## 2. Settle what is cheap; wait for nothing

For each open PR whose head branch starts with `agent_branch_prefix`
(`gh pr list --json number,headRefName,title`):

| state | action |
|---|---|
| orchestrator gate passed (your gate comment exists) AND gating CI green | merge (squash); `agent:pr-open` → `agent:done`; board Done (`board` in loop.json); `git pull` |
| gate passed, CI still running | leave open; STATUS records it. `drain`: poll `gh run list --branch <head>` (no sleep loops; Monitor or a bounded background wait), ceiling 10 min per PR, merge on green |
| gate NOT passed | leave open; STATUS records "needs gate". **Pause never gates** — a gate is a judgement read of the diff, not settling, and a rushed gate is worse than none |

Then: close pipeline cleanup PRs matching `cleanup_pr_prefix` with a one-line reason; cancel CI
runs on superseded heads (`gh run cancel`). **Never dispatch anything new.**

## 3. Clean the tree

- Uncommitted changes under docs / `status_file` / DECISIONS → **commit** them to
  `default_branch` (a `docs:` message). Not a stash: a stash is invisible to the next session.
- Anything else uncommitted → ask the user in one line (commit, drop, or leave with a STATUS
  note); never decide silently.
- Delete local copies of merged agent branches: `git branch --merged default_branch | grep
  <agent_branch_prefix>`.
- Check: `git status --porcelain` empty except `claude-work/.loop-owner`; HEAD on
  `default_branch`; `git status -sb` neither ahead nor behind after push.

## 4. Write STATUS — a dashboard, not a checklist

Replace, never append. Required shape:

- Header line: `loop STOPPED (<reason>) <UTC time>` plus one clause of progress.
- **In flight:** one line per open PR / run: number, issue, its state (gate passed / needs gate,
  CI running / green), and what the **standard** iteration does with it. State facts; the
  iteration's rules in `loop_doc` are the instructions. No "on restart do X before Y" lists.
- **Next ready:** the next issue(s) and any constraint (parallel-safe, orchestrator-written
  plan). This is `loop-start`'s entry point.
- **Awaiting <human>:** what a person owes, one line each, where it was posted.
- Keep ≤ 80 lines. Commit straight to `default_branch` (`docs: STATUS — loop paused …`), push.

## 5. Release and announce

1. Remove `claude-work/.loop-owner` (never committed; just delete it).
2. Post through `notify`: `⏸️ <project> loop paused · <progress> · <in flight> · next: <issue>`.
   No ping unless a human owes something.
3. Verify read-only (`gh pr list`, `gh run list --limit 5`, `git status -sb`) that the world
   matches STATUS, then tell the user in three lines: where things stand, what is in flight,
   that `/loop-start` resumes it.

"Just stop now" from the user = steps 1, 4, 5 only; say what was skipped.

## Rationalisations that mean you skipped a step

| thought | reality |
|---|---|
| "I'll close the PRs out first, then stop the loop" | Step 1 is first. A wakeup mid-cleanup double-merges. |
| "CI is nearly done, I'll wait a bit" | Without `drain`, waiting is not part of pause. Record and stop. |
| "CI is green, merging is cheap" (gate not done) | Merge needs gate + green. Cheap ≠ ungated. |
| "stash the docs change and note it" | Commit it. A stash is lost to the next session. |
| "the owner file's semantics are unclear, leave it" | Pause removes it. `loop-start` refuses while it exists. |
| "put the restart steps in STATUS so nothing is missed" | STATUS is a dashboard; `loop-start` + `loop_doc` are the steps. |
