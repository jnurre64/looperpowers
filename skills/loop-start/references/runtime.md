# Shared lifecycle runtime contract

Read this before setup, start, pause, recovery, or transfer. Resolve this file from the
real installed SKILL.md path, following symlinks; sibling skills use
`../loop-start/references/runtime.md`. The package root is two directories above a skill
folder. Never infer resources from a client's home directory.

## Clients and modes

| Client/runtime | Persistent unattended | Explicit bounded iteration |
|---|---|---|
| Claude Code with loop, ScheduleWakeup, Monitor, TaskList, TaskStop | Supported after capability preflight | Requires a committed bounded block |
| Codex ordinary CLI/app turn | Unavailable without a verified scheduler adapter | Supported with `--mode bounded` and a committed bounded block |
| Either client with an external scheduler | Only if it satisfies every capability below | Supported with a bounded block |

A normal turn, background shell process, sleep, or in-turn wait does not establish that the
client will wake later. This package supplies instructions and ownership helpers, not a
durable scheduler. App automations are not automatically a compatible adapter. The
orchestrator client does not change the worker engine: the current sandbox-pal shell
dispatcher still launches Claude workers.

Default mode is `persistent`. Never silently downgrade. If required capabilities are missing,
stop before owner creation, kickoff notification, scheduling, or dispatch. Offer bounded
mode, but require explicit user selection and the corresponding project command first.

## Capability preflight (read-only)

Bind these operations to actual available tools or an installed adapter, identifying its
runtime, host, session, and scope. A config declaration is not proof of availability.

| Operation | Required behavior |
|---|---|
| inspect | Enumerate project wakeups, monitors, executing iterations and their owner tokens; distinguish empty from unknown/unreachable. Inspect prior clients too, or obtain verified shutdown from their owning session. |
| stop | Cancel only this owner's wakeups/monitors, prevent queued iterations starting, and confirm executing iterations quiesced. Worker dispatches may remain, but must be recorded. |
| schedule | Persistent: schedule a future iteration that survives the current turn, returning an inspectable handle. |
| wake_on_completion | Persistent: wake on agent label transitions and PR CI completion, returning owned monitor handles. |
| fallback | Persistent: a long (20–30 min per project policy) fallback while dispatches run, cancellable and inspectable. |
| wait | Drain only: completion notification or one bounded wait, at most 10 min per PR. No sleep/poll loop; unsupported drain stops machinery, reports drain unavailable, then completes an ordinary no-wait pause. |

Claude mapping: invoke the `loop` skill with the selected text; ScheduleWakeup supplies
schedule/fallback/stop, Monitor supplies completion wakeups, TaskList/TaskStop inspect and stop
recorded monitors. Verify actual session scope; these tools do not cancel a different
session's tasks. Codex mapping: bounded text executes in the current turn; persistent text
requires an explicitly configured available adapter satisfying this table. Do not invent
Codex equivalents for Claude tool names.

The preflight helper consumes a fresh inspection snapshot, saved outside the checkout:

```json
{"client":"codex","mode":"bounded","capabilities":{"inspect":true,"stop":true},
 "scheduler_quiescent":true,"dispatch_reconciled":true}
```

Persistent reports also require `schedule`, `wake_on_completion`, and `fallback` set to true
under `capabilities`. Record only verified operations. `scheduler_quiescent` means prior
orphaned/owned scheduling has been reconciled and cannot run; `dispatch_reconciled` permits
known active workers recorded for the next iteration, but not unknown state. Never fabricate
a passing snapshot. Keep the actual inspection evidence in the session/recovery record.

In bounded mode there are no new wakeups or monitors: inspect/stop still require reconciliation
of earlier owners. Run one iteration, perform only immediately available work, record workers
still in flight, and pause before ending the turn. Do not wait for CI unless drain is selected.
If the only remaining action is human input, post once, write STATUS, cancel owned scheduling,
and stop. Never schedule idle polling for a human, in either mode.

## Project commands and compatibility

Keep all existing loop.json keys and paths. Without `start_blocks`, the first fenced block
under `## Starting the loop` is the legacy **claude/persistent** command only. Never execute
it in Codex or remove its scheduling clauses at start time.

Optional additive configuration selects exact level-two headings in the same loop_doc:

```json
"start_blocks": {
  "claude": {"persistent": "Starting the loop"},
  "codex": {"bounded": "Starting the loop (Codex bounded)"}
}
```

Select by the actual client and explicitly selected mode. Extract the first complete fenced
block within that heading, before the next heading of level two or higher. Missing, duplicate,
or unclosed blocks fail preflight. Pass the contents verbatim to the supported runtime;
never paraphrase, strip tool names, or translate on the fly. Adding an alternative is a
reviewable, committed project doc/config edit. Each alternative must refer to the same
iteration and stop policy and preserve plan/merge/playtest gates, spin guard, notifications,
concurrency and dependency rules. A runtime cannot weaken these rules. Contradictory project
policy needs a doc change before start, even when a bounded block is present.

## Ownership and recovery

The shared path remains `claude-work/.loop-owner`, ignored by git. New records contain
`version`, `token` (random unique generation), `client`, `mode`, `host`, `session`,
`started_at`, `runtime`, and owned scheduler/monitor handles. Never use an unknown session
as authority to cancel tasks. Legacy host/session/started_at records remain blockers.

Use the bundled `scripts/owner.py` for atomic acquire and token-checked release; do not
truncate/overwrite the file. All clients must use these updated skills. The local owner file
coordinates one shared checkout, not separate clones or hosts: a scheduler adapter must
provide project-wide exclusion, or all orchestration must use a single shared checkout.

Before every iteration and external mutation, verify the owner token still matches. All
callbacks must carry and validate the token; a stale callback exits without dispatch/merge.
Persist returned handles before proceeding. Failure to record a handle requires immediate
stop and reconciliation; retain the owner if shutdown cannot be verified.

`--force` authorizes transfer, not blind overwrite. First have the prior owning runtime stop
and confirm no queued/running iterations or monitors can mutate the project. Reconcile PRs,
CI, dispatch locks and outcomes; then release the old token and atomically acquire a new one.
If another starter wins acquisition, stop. Do not delete a legacy or malformed record until
explicit transfer authorization and verified shutdown; archive its contents in the recovery
record and use the helper's exact-file digest recovery. Unknown scheduler state blocks
transfer even when timestamps look old or locks are absent. A Codex pause cannot claim to
stop another Claude session. Ask that session to pause, or obtain operator-confirmed shutdown
of that runtime; do not send another person a message without authorization.

Missing owner: inspect scheduler state before acquisition. If any unowned/orphan task exists,
stop and reconcile it through its owning runtime; absence of the file is not proof of safety.
A pause/recovery with no owner must atomically acquire a recovery token after verified
scheduler reconciliation and before settling/publishing; losing acquisition stops that pause.
This prevents a concurrent start from racing dashboard cleanup. Release the recovery token
only after normal pause publication and notification succeed.

Interrupted acquisition, shutdown, or status publication: leave the record as a blocker until
recovery establishes quiescence. Never auto-expire ownership.

Start order: all preflight and reconciliation → atomic acquire → kickoff notify → invoke
verbatim command. Notify failure: no dispatch/scheduling; verify no tasks exist, release only
this token, report failure locally. If invocation partially fails, stop/inspect first; retain
the owner on uncertainty. Pause order: stop/inspect → settle → publish STATUS → pause notify
→ token-checked release. If status commit/push or pause notification fails, retain ownership,
report the failed step locally, and retry that step on recovery before release. An unset
notify retains the historical user-only behavior; an explicitly configured failing notify
never silently falls back to local output.

## Reconciliation and legacy PAUSED

Neither STOPPED nor PAUSED proves quiescence. Inspect scheduler state, open PRs and current
head CI, dispatch locks, runner state, and terminal dispatcher records. Read semantic `outcome`
(e.g. `agent:failed`) even when process exit code is 0. Failed workers with no locks are
terminal failures, not active workers. Conflicting evidence or missing outcome stays unknown;
do not duplicate dispatch. Preserve failure counts for the spin guard.

For a legacy PAUSED dashboard, run pause/recovery reconciliation. Once scheduling is verified
stopped, record open PRs, live workers, failures and the next standard actions, normalize the
header to STOPPED, commit/push, and complete notification/release. Active workers can be
recorded under STOPPED: the header describes the orchestrator. Never normalize by merely
editing the header, and never start directly from PAUSED. Clean pause still merges only an
already-gated PR whose current head has green required CI; it never performs a new gate.
