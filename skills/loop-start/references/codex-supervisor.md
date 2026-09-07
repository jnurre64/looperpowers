# Codex exec supervisor

This is looperpowers' timed runtime, built on the documented `codex exec` interface. It is
not a built-in Codex loop command. Read this when setup saved supervised operation or the user explicitly overrides to it.
Normal commands remain `$loop-setup`, `$loop-start`, and `$loop-pause`.
It runs on Linux/POSIX with Python 3, Git, gh and Codex CLI; it is not a Windows service.

## Choose the runtime

- For one interactive objective with completion criteria, native `/goal` is appropriate.
  It is distinct from future scheduled wakeups. [Official long-running work guidance](https://learn.chatgpt.com/docs/long-running-work).
- Native scheduled tasks can return to a chat or start independent runs. Local tasks need
  the machine and app running. The CLI has no Scheduled management interface.
  [Official scheduled-task guidance](https://learn.chatgpt.com/docs/automations).
- For a shell-driven backlog controller, this supervisor serializes `codex exec` processes
  and interprets schema-constrained results. The CLI supports JSONL events, output schemas,
  explicit sandboxes and session resumption. We use fresh threads and committed project
  state each iteration; no ambiguous `resume --last` selection.
  [Official non-interactive guidance](https://learn.chatgpt.com/docs/non-interactive-mode).

Completion events and a 20–30 minute fallback are the existing project's event policy,
not general Codex requirements. This timer runtime cannot satisfy that event policy.
Explicitly review and commit a timer policy before selecting it; preserve every plan,
merge/playtest gate, spin guard, dependency/concurrency rule and human stop condition.
Native scheduled tasks require their own verified integration; they are not controlled here.

## Project configuration

Setup saves this choice once in loop.json (preserve existing keys, defaults and start blocks):

```json
"default_modes": {"claude":"persistent", "codex":"supervised"},
"start_blocks": {
  "claude": {"persistent": "Starting the loop"},
  "codex": {
    "supervised": "Starting the loop (Codex supervised)",
    "supervised_pause": "Stopping the loop (Codex supervised)"
  }
},
"codex_supervisor": {
  "scheduling": "timer",
  "interval_seconds": 1200,
  "iteration_timeout_seconds": 1800,
  "notification_timeout_seconds": 30,
  "max_iterations": 100
}
```

The named blocks must be committed in loop_doc. Use `templates/CODEX-SUPERVISOR.md` as a
starting point and review it against project policy. Both prompts are passed byte-for-byte
as stdin to `codex exec`; lifecycle context is supplied separately in `LOOPER_OWNER_TOKEN`,
`LOOPER_PHASE` and `LOOPER_STOP_REASON`. The supervisor owns acquisition, start/stop
notifications, timing and release. Its children must not call loop-start/loop-pause,
start a goal/scheduler, alter ownership, or leave local background processes behind.

A result has exactly `decision`, `summary`, and `work_in_flight`. Iterations return
`continue`, `wait`, `human`, `stop`, or `failed`; pause returns `stopped` or `failed`.
`wait` requires actual machine work in flight. Both continue and wait use the committed
interval. Human/stop results go straight to pause without another timer. Max iterations
also triggers pause. A zero exit code is insufficient: failed events, malformed output,
semantic failures or missing turn completion stop execution and retain ownership.

## Start, inspect and stop

Before starting, reconcile external schedulers and dispatches as required by runtime.md.
Save a fresh report outside the checkout:

```json
{"client":"codex","mode":"supervised","scheduler_quiescent":true,"dispatch_reconciled":true}
```

These two booleans summarize verified external evidence, not an automatic discovery of
other clients. Do not assert them if prior Claude/app scheduling is unknown. The supervisor
probes its own CLI flags, process lock, clean default branch, origin sync, GitHub identity,
notification executable, selected blocks and STOPPED dashboard before acquisition/notify.
It refuses an existing owner, including stale/legacy owners; there is no force-start switch.

From the project root, with the installed package path resolved:

```bash
python3 /path/to/looperpowers/skills/loop-start/scripts/supervisor.py run --report /outside/checkout/reconciliation.json
python3 /path/to/looperpowers/skills/loop-start/scripts/supervisor.py inspect
python3 /path/to/looperpowers/skills/loop-start/scripts/supervisor.py stop --token <owner-token>
```

`run` is a foreground service, not a shell daemon. For unattended operation launch it with
a process manager on the host that has the checkout and authorized credentials. Do not
claim a background tool invocation will survive the chat. A systemd service, for example,
should set WorkingDirectory to the project root, ExecStart to the command above,
Restart=no, KillMode=control-group, and a TimeoutStopSec covering the current iteration plus
pause (each can take iteration_timeout_seconds) and notification/git checks. Provision
service configuration and credentials separately; setup never installs services or reads
secrets. Start with narrow sandbox permissions; this runner sets workspace-write and never
bypasses approvals, rules or hook trust. Unsupported/blocked tool access must produce failure,
not repeated privileged attempts.

Stop is **graceful**: the current iteration can continue until its timeout, then the pause
block runs. A stop request returns `stopped: false`; it is not shutdown confirmation. Inspect
until the lock is free and phase is stopped, then verify owner release and dashboard. `drain`
is not implemented here; report it unavailable and use this ordinary graceful stop. Do not
run another session's PR settling while the supervisor or its child still holds the lock.
SIGTERM/SIGINT requests the same graceful stop. Forced termination or timeout is a recovery
condition, not clean pause.

## Failure and recovery boundaries

The runtime stores a lock, atomically replaced state, and per-invocation JSONL/stderr/results
under the Git common directory's `looperpowers/` folder. Linked worktrees share its lock;
independent clones do not. Use one designated controller checkout/host for each project.
Never remove the lock file: unlinking a locked inode defeats process exclusion. Logs can
contain project content; archive them after a verified stop, preserving incident evidence.

The supervisor checks its owner token before every invocation and lifecycle notification,
refuses runtime policy changes mid-run, and kills invocation process groups on timeout or
completion. The child inherits the service lock, helping prevent overlap after a supervisor
crash. `busy` only indicates that a process holds the lock; it does not prove the supervisor
is healthy. A free lock does not prove remote/detached workers or another runtime are stopped.
Owner records remain blockers after interruption. No PID-based takeover or automatic expiry.

Kickoff notification failure releases only the just-acquired token before any Codex launch.
Later failure (including pause notification failure) retains it and attempts one blocked
notification; if that also fails, the original error remains in local state/logs. Read state/logs, confirm the
service and children are stopped, and reconcile workers/external schedulers. Then use the
shared explicit recovery procedure: publish the reconciled STOPPED dashboard and deliver the
pause notification before token-checked release. Never restart by deleting state files.

This supervisor enforces process sequencing and lifecycle decisions. It does not mediate
every GitHub mutation made inside Codex: per-action token checks, substantive gates and
semantic worker reconciliation remain instructions in the committed project prompt. The
JSON result is an agent report, not independent proof of PR/worker state. Production use
still requires validating the selected Codex version, sandbox access, notify path, and
project prompts in a controlled pilot. Offline tests exercise real processes, git, locks,
timers and cleanup with fake executables; they do not call a model or live services.
