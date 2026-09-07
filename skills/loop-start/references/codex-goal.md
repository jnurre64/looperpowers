# Native Codex Goal adapter

Read for resolved `goal` starts or a `codex-goal` owner on pause. This guide replaces the
scheduled/bounded clean-main, scheduler-report and commit/push lifecycle. Shared project
scope, gates, ownership, notifications and dependency rules still apply. Ordinary Codex
start means a native Goal, not a timer, repeated prompts or an arbitrary iteration cap.

## Inspect and prepare

1. Read loop.json, LOOP.md and STATUS. Report In flight, Next ready and Awaiting human.
   Read existing plans, acceptance evidence and failure counts; do not reset on client change.
2. Inspect actual native Goal state in this session using the exposed inspection tool or
   `/goal`. Available tool schemas define capabilities, not a version number or enabled flag.
   Recognize none, active, paused, complete and blocked only from actual runtime evidence.
   Unknown state is a blocker. Do not invent tool names, arguments, pause/resume methods or
   goal IDs. If the runtime supplies an ID, retain it with the session evidence.
3. Inspect ownership in this checkout and all linked worktrees (`git worktree list`), native
   state even if the owner file is missing, prior Claude scheduling/supervisor state and
   dispatched workers. Existing foreign/legacy/unbound ownership blocks ordinary start.
   Reconcile through the prior owning session; timestamps and a STOPPED header prove nothing.
   Known independent workers can remain in flight if recorded and excluded from new writes.
4. Inspect branch, staged/untracked files and unpublished commits to understand actual mutation
   risks. Preserve them. Do not checkout main, stash, reset, clean, push or create a worktree
   merely to start Goal. Isolate work only for a real overlapping writer or project requirement.
   Apply bot identity, current-head review/CI and publication checks when performing actions
   that need them. If project rules demand incompatible publication, reconcile the rule before
   mutation; Goal does not silently waive it or expand sandbox/approval permissions.
5. Extract the exact `start_blocks.codex.goal` fenced objective using `select_block` in
   scripts/preflight.py. It must name a concrete authorized outcome and checkpoint, reference
   the shared project procedure, and fit 1–4000 characters. Review/edit the project block if
   the scope changes; do not replace it with an unrelated or limitless backlog objective.
   No default token/time/iteration budget; pass a budget only if explicitly requested.

The read-only `scripts/goal.py --observation <file>` checks a fresh snapshot outside the
checkout. Example shape (values must come from actual inspection):

```json
{"state":"none","session":"actual-session-id","controls":["create"],
 "command_ui":false,"reconciled":true}
```

For an existing goal include its exact `objective`. `controls` lists only exposed operations
(`create`, `resume`), `command_ui` means verified native UI support, and `reconciled` means
step 3 actually completed. The helper does not discover capabilities, call native tools or
prove shutdown. Its output is a required next action, always `started:false`.

## Start or resume

- **No goal:** after preflight, atomically acquire via `owner.py acquire --client codex
  --mode goal --runtime codex-goal --session <actual-session-id>`. Acquisition checks linked
  worktree owners under a common Git directory lock. Keep the token. Post the configured
  kickoff notification (only where user authorization covers that channel). If it fails,
  do not create; release only after confirming no runtime started.
  Invoke the actual exposed native create operation with the extracted objective unchanged.
  Re-inspect native state; only a matching active goal confirms start. Persist the observed
  state using `owner.py bind-goal --token <token> --session <session> --objective-file <file>
  --state active`. A failed/ambiguous create or bind retains ownership for reconciliation;
  never retry create blindly. The helper is metadata storage, not a runtime control.
- **Matching active goal and owner/session/objective digest:** continue it, never create a
  duplicate. Inspect current state and revalidate the token before each mutation. Native
  objective edits invalidate the digest; reconcile and review the project scope before rebinding.
- **Matching paused goal:** verify the retained token, reconcile workers and shared status,
  call an actually exposed resume operation, then inspect and bind active. If only UI controls
  exist, give `/goal resume`; report pending until runtime confirmation.
- **Matching completed or blocked goal:** preserve checkpoint evidence and inspect what is
  ready. Completed work does not authorize a new objective automatically. Blocked status
  follows actual runtime rules; reconcile the blocker before any supported resume/edit.
  If a new start request authorizes the next known outcome, review its project block, confirm
  the old Goal is quiescent and release its owner after checkpoint persistence/notification.
  Clear the completed native Goal using an exposed control (or verified `/goal clear` handoff),
  then repeat the no-goal procedure. Never silently replace the objective of a bound owner.
- **Foreign goal/session, unknown native state or inconsistent owner:** stop dependent actions
  and explain the precise recovery. Never clear/replace an unrelated goal.

If create is unavailable but native UI exists, show the exact `/goal <objective>` command
using the project block and say start is **pending user action**. Do not acquire a permanent
owner just for showing the command. The objective requires reconciliation and atomic ownership
before any project mutation. When the user runs it, inspect its exact objective/session, repeat
preflight, acquire ownership and bind the observed goal before work. Adoption of a missing-owner
Goal is this explicit recovery step, not an automatic helper decision. If both native tools
and UI are unavailable, report unsupported; do not start a timer or silently run bounded.

## Shared work and checkpoints

Follow the project's standard iteration and gates repeatedly toward the selected outcome.
Block work dependent on missing design/playtest evidence; continue independent, already
specified work within scope. Do not ask for permission after every iteration. Ask when a real
scope/design decision, blocker or human-only acceptance step requires it. Preserve failure
counts and the project spin guard. Goal does not bypass agent review, current-head CI, merge
approval, concurrency limits or any approval requirement for external actions.

At a checkpoint write the same STATUS sections: In flight, Next ready, Awaiting human.
Include runtime (`codex-goal`), actual native state, owner session, branch/unpublished work,
acceptance evidence, exact human ask and where it was posted. Keep status concise; do not
include tokens. Publish only as authorized by project/user policy; otherwise clearly record
local-only status and any pending publication. Never stage unrelated user changes.

When only human work remains, stop project mutations and record the checkpoint. Mark a native
Goal complete only if its defined outcome (possibly reaching that checkpoint) was achieved.
Use blocked only under the exposed tool's own blocking rules; some require a repeated blocker
across three consecutive goal turns. Never misuse complete/blocked as pause. If a genuine
pause control is unavailable, request native `/goal pause` and report pending confirmation.
A Goal is session continuation, not promised future wakeups or an offline service.

## Pause and transfer

1. Inspect native state and actual owner; stop starting new work immediately. Use the exposed
   native pause operation if present. Otherwise give `/goal pause`, then `/goal` to inspect.
   Without confirmation report **pause pending**, retain ownership, and do not claim shutdown.
   `update_goal` with complete/blocked is not pause. `drain` does not create a polling loop;
   use only an available bounded wait when explicitly requested.
2. Confirm the owning Goal is paused/terminal and reconcile any executing work. A native pause
   does not stop foreign timers, Claude wakeups or detached workers. Record those workers;
   unresolved competing writers block transfer. Do not perform a new gate or dispatch on pause.
3. If ownership is missing, first confirm this is the project's exact objective in the
   current session, verify pause/terminal state and reconcile prior runtimes/workers. Acquire
   a recovery owner with `owner.py acquire --client codex --mode goal --runtime codex-goal
   --session <actual-session-id>` before any dashboard mutation. Bind the observed state and
   exact objective. If a linked-worktree owner wins, stop; never publish concurrently. A
   foreign/unrelated native Goal is not adopted or paused by this project skill.
   Save the shared resume point as above, preserving staged/dirty/unpublished work. Do not
   require main or a push merely to pause. Bind the actual observed native state. Notify via
   the configured, authorized channel; delivery/persistence failure retains ownership and is
   reported locally. Never publish STOPPED while shutdown remains unknown.
4. A paused Goal **retains ownership** because native `/goal resume` can revive it. Bare
   loop-start in the same session resumes it. To change clients/session, explicitly transfer:
   first confirm the old goal is cleared/otherwise cannot resume writes and prior runtime is
   quiescent, reconcile workers and status, then token-checked release and fresh acquisition.
   If only UI can clear, provide `/goal clear` after that transfer is authorized and verify.
   Terminal goals may release after confirmed quiescence, saved status and successful required
   notification. Old callbacks must always validate their token before mutation.

Linked worktrees share acquisition exclusion through the owner helper; separate clones or
hosts require a shared external coordinator or one orchestration checkout. Older installations
must be updated before relying on linked-worktree exclusion. Goal IDs/state do not migrate
between clients: the shared project resume point does.

## Sources and validation limits

Native commands and continuation: [developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli),
[Follow goals](https://learn.chatgpt.com/use-cases/follow-goals),
[long-running work](https://learn.chatgpt.com/docs/long-running-work).
The adapter is skill instructions plus deterministic metadata/preflight helpers, not a Python
Goal SDK. Offline tests validate decisions and exclusion; live tool availability, model
compliance and lifecycle behavior need a controlled pilot. Never create a live Goal as a test
without the user's request to run that Goal.
