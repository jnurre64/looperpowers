---
name: loop-pause
description: Use when the user asks to pause, stop, halt or wind down the orchestrator loop, or to "get to a clean stopping point" so it can be resumed later, in a project that has claude-work/loop.json.
---

# loop-pause

Usage: `loop-pause [drain]`.

Reach a clean, clear stopping point and leave the project ready for `/loop-start`. **Order
matters and every step has a check.** The rule: **finish what is cheap, wait for nothing**
(`drain` is the one exception, §2).

Read [the shared runtime contract](../loop-start/references/runtime.md) first, including
cross-client shutdown, legacy PAUSED reconciliation and failed-notification recovery.

## 0. Load the project data

`cat claude-work/loop.json` (missing → stop: "run /loop-setup first"); read `status_file`.

Inspect the actual owner before choosing a runtime; do not route pause from saved defaults.
For a `codex-goal` owner (or a native Goal with missing ownership), follow
[the native Goal pause procedure](../loop-start/references/codex-goal.md) instead of all
remaining sections below. That procedure includes native API self-pause when the model
lacks a pause tool; try it before requesting a manual UI command. Unknown/foreign
ownership requires reconciliation first.

For an owner whose runtime is `codex-exec`, read
[the supervisor guide](../loop-start/references/codex-supervisor.md). Request stop using its
exact token; the running supervisor owns settling, publication, notification and release.
Do not concurrently run steps 2–5 here. A stop request is graceful and not proof of shutdown:
report stopping until inspect shows no lock holder, stopped state and released ownership.
If interrupted/failed, reconcile and use explicit recovery; never infer success from a free
lock. `drain` is unavailable in this runtime; say so and request the ordinary graceful stop.

## 1. Stop the machinery FIRST

1. Identify the owner token, client, runtime and recorded handles. Inspect scheduler state
   even if the owner is missing. A foreign/legacy owner requires the contract's explicit
   transfer/recovery; do not call local tools and claim another session is stopped.
2. Use the verified runtime's stop operation for owned wakeups and monitors, then inspect
   to confirm no queued or executing iteration can mutate the project. For Claude this uses
   ScheduleWakeup stop and TaskList/TaskStop in the owning session. Codex bounded mode has
   no new scheduled tasks, but still checks for older scheduling.
3. If shutdown is unknown, retain ownership and report the blocker. Do not settle or publish
   STOPPED. Reconcile PRs, CI, dispatch locks and semantic outcomes; exit 0 with agent:failed
   is a failed worker. Verified terminal failures without locks are not active workers.

Nothing settles before shutdown is verified. For `drain`, verify the bounded wait capability;
if absent, report drain unavailable and complete the ordinary no-wait pause below (publish
in-flight work, notify, release on success). Do not claim the workers were drained.

## 2. Settle what is cheap; wait for nothing

If ownership is missing, after verified scheduler reconciliation atomically acquire a
recovery owner using the owner helper before any settling or dashboard mutation. If acquisition
loses to another session, stop. Legacy ownership requires the contract's authorized recovery.

Before settling or committing, verify HEAD is on `default_branch`. If not, keep the
scheduler stopped and ownership retained; report the branch blocker without switching over
uncommitted work. Inspect the dirty tree now: docs may be settled in step 3; unrelated changes
need the user's decision before git mutations. Stage only the specific intended doc files.

For each open PR whose head branch starts with `agent_branch_prefix`
(`gh pr list --json number,headRefName,title`):

| state | action |
|---|---|
| orchestrator gate passed (your gate comment exists) AND gating CI green | merge (squash); `agent:pr-open` → `agent:done`; board Done (`board` in loop.json); `git pull` |
| gate passed, CI still running | leave open; STATUS records it. `drain`: use the verified completion/bounded wait (10 min ceiling per PR), then re-read current-head CI and gate; merge only on green. Timeout/failure leaves it open; no repeated polling |
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
  plan), with the source and remaining scope of any user-approved next action. This is
  `loop-start`'s entry point; the user must not have to repeat that approval in a new prompt.
- **Awaiting <human>:** what a person owes, one line each, where it was posted.
- Keep ≤ 80 lines. Commit straight to `default_branch` (`docs: STATUS — loop paused …`), push.

**Readiness is a script result, not a checklist.** After the STATUS commit is pushed, run
`python3 <resolved-loop-start-dir>/scripts/readiness.py --client <client> --session <your session>`
(your own owner record is still held, so pass your session). If it prints
`PASS loop-preflight <sha> <utc>`, put that line in the header next to the STOPPED clause in
one more `docs: STATUS — preflight PASS` commit and push. If it fails, the header states the
failing check and its fix and does NOT say "ready"; a later `loop-start` reports the failure
as "the handoff overstated readiness" if it finds a ready claim without a PASS line. Never
write "ready to restart" from a hand-written list — the 2026-09-09 restart stalled on exactly
that: a checklist that never looked at the owner file while a paused record from a closed
runtime sat on it.

## 5. Release and announce

1. Post through `notify`: `⏸️ <project> loop paused · <progress> · <in flight> · next: <issue>`.
   No ping unless a human owes something. Notification or STATUS commit/push failure retains
   ownership; report locally and retry the failed step before releasing. Never claim success.
2. Verify read-only that PRs, runs, dispatch outcomes and scheduler state match STATUS.
3. Release only your token with
   `python3 <resolved-loop-start-dir>/scripts/owner.py release --token <token>`.
   Legacy/missing ownership follows recovery in the shared contract.
4. Tell the user where things stand, what is in flight, and that `loop-start` resumes it.

"Just stop now" from the user = steps 1, 4, 5 only; say what was skipped.

## Rationalisations that mean you skipped a step

| thought | reality |
|---|---|
| "I'll close the PRs out first, then stop the loop" | Step 1 is first. A wakeup mid-cleanup double-merges. |
| "CI is nearly done, I'll wait a bit" | Without `drain`, waiting is not part of pause. Record and stop. |
| "CI is green, merging is cheap" (gate not done) | Merge needs gate + green. Cheap ≠ ungated. |
| "stash the docs change and note it" | Commit it. A stash is lost to the next session. |
| "the owner file's semantics are unclear, leave it" | Release only after verified shutdown, published STATUS and notification; retain it on uncertainty. |
| "put the restart steps in STATUS so nothing is missed" | STATUS is a dashboard; `loop-start` + `loop_doc` are the steps. |
| "the checklist is ticked, so the header can say ready" | Ready is `readiness.py` printing PASS after the STATUS push. A ticked list proved nothing on 2026-09-09. |
| "the runtime is closed in the docs, the owner file can stay" | Closing a runtime for a project releases its owner record. A `paused` record from a closed runtime is the next start's blocker. |
