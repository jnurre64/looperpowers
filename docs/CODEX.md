# Using looperpowers with Codex

The daily workflow is **`$loop-setup` → `$loop-start` → `$loop-pause`**. Setup is normally
needed only once per project/client, or when changing how the loop runs. Type these in Codex
chat, not the terminal. [Install the shared skills first](../README.md#install).

## Setup once

Open Codex in the project you want to orchestrate, then send:

```text
$loop-setup
```

Setup discovers the repo, bot identity, existing project rules, notification path and dispatcher
settings. It reads AGENTS.md/CLAUDE.md and non-secret config.defaults.env/config.env assignments
without sourcing files. It preserves existing keys, Claude commands and project gates.

Setup establishes continued operation where available, explains any required host service,
and saves the choice. If something cannot be discovered, it asks during setup. It does not
make you choose a runtime every time you start. Missing hosting remains an explicit prerequisite;
a one-off run is saved as the default only if that is what you ask for.

| File | Purpose |
|---|---|
| `claude-work/loop.json` | Settings, the saved choice per client and exact command headings |
| `docs/LOOP.md` | Project procedure, gates, stop cases and client commands |
| `claude-work/STATUS.md` | Resume dashboard (path can be overridden in config) |
| `claude-work/.loop-owner` | Ignored ownership record shared by both clients |

Keep these compatibility paths when migrating. Review and commit setup before starting.
Setup does not install a dispatcher, notification script or service, change credentials, or
start the loop. It may suggest an AGENTS.md pointer but does not edit that file.

## Start and pause

```text
$loop-start
```

Start loads the saved configuration, checks the clean default branch, remote sync, identity,
notification path and reconciled ownership, then starts the configured loop. It briefly tells
you whether that loop continues automatically or runs just once. Missing runtime capabilities
cause a clear stop; they never silently change how the loop runs.

```text
$loop-pause
```

Pause uses the current owner's runtime. It stops orchestration, settles only already-gated
green work, and publishes the resume point. It never dispatches new work or performs a new
gate. The Codex supervisor stops gracefully: the current iteration can finish before pause
runs. A stop request is not proof of completed shutdown. Use `$loop-start` again to resume.

## What did “bounded” mean?

An iteration reads the backlog, reconciles existing work, performs eligible actions, and
updates status. It may dispatch a worker whose work continues after that iteration ends.

| Behavior | What happens after an iteration? |
|---|---|
| Existing event-driven loop (`persistent`) | Waits for worker/CI completion events, with a fallback timer while machine work runs, then iterates again |
| Codex timer loop (`supervised`) | The running host supervisor waits the configured interval, then invokes Codex again |
| One-off run (`bounded`, now exposed as `--once`) | Publishes the resume point and stops; the user must start the next iteration |

The distinction is continuation, not which gates apply. All preserve project plan, merge,
playtest, dependency, concurrency, spin-guard and human-stop rules. When only a human action
remains, a continuing loop parks rather than polling indefinitely.

For one iteration without changing your saved default:

```text
$loop-start --once
```

Setup must have added a one-iteration command first; the [LOOP template](../templates/LOOP.md)
provides one for Codex. `--once` never strips scheduler instructions from a continuous prompt.
`$loop-pause drain` requests a bounded CI wait where supported; the Codex supervisor does not
support drain and uses its ordinary graceful stop instead.

## Existing projects

Run `$loop-setup` once to save your Codex choice. Until then, existing explicit `--mode`
commands continue to work; bare Codex start asks for setup rather than guessing from blocks.
Legacy Claude projects keep their existing persistent default without migration.

Before changing clients, pause through the owning session and verify its scheduler is stopped.
Codex cannot cancel another Claude session's wakeups using local tools. Reconcile PRs, CI,
dispatcher outcomes and locks. Exit 0 with `outcome=agent:failed` is a failure; absent locks or
a PAUSED header alone do not prove safety. Complete pause/recovery before normalizing legacy
PAUSED dashboards to STOPPED. Never take over by deleting an owner record.

## Advanced configuration

Setup manages these settings; ordinary start and pause do not need flags. For example, after
choosing a Codex timer loop and keeping the existing Claude event loop, merge this fragment
into the existing loop.json (do not replace the file):

```json
"default_modes": {"claude": "persistent", "codex": "supervised"},
"start_blocks": {
  "claude": {"persistent": "Starting the loop"},
  "codex": {
    "supervised": "Starting the loop (Codex supervised)",
    "supervised_pause": "Stopping the loop (Codex supervised)",
    "bounded": "Starting the loop (Codex bounded)"
  }
}
```

Each heading must contain its rendered project command in loop_doc. Supervised operation
also requires committed timer policy and `codex_supervisor` settings; see the
[supervisor guide](../skills/loop-start/references/codex-supervisor.md) and
[template](../templates/CODEX-SUPERVISOR.md). It requires an authorized host process manager;
a chat background process does not establish future liveness. Do not substitute a timer
when project policy requires completion events without reviewing that policy change.

`--mode persistent|bounded|supervised` overrides the saved choice for one invocation;
`--once` is the clearer alias for `--mode bounded`. Do not combine them. Overrides still need
the correct committed block and capabilities. Pause always follows the active owner, even
when start used an override. `--force` retains all verified-transfer requirements.

## Troubleshooting

| Symptom | Next step |
|---|---|
| Skills not found | Re-run `install.sh codex`; verify the symlinks and package checkout; restart Codex if needed |
| No saved Codex runtime | Run `$loop-setup` once to save the intended behavior |
| Missing block or scheduler | Fix the selected setup/prerequisite; optionally request `--once` if its block exists |
| Dirty or unsynchronized tree | Reconcile pending changes and branch state; do not discard files to satisfy preflight |
| Identity/permission mismatch | Check gh identity against bot_user and permissions for the required operations |
| Foreign owner or stale runtime state | Follow [verified recovery](../skills/loop-start/references/runtime.md); do not infer safety from timestamps |
| Notification failed | Fix delivery and complete recovery; later failures retain ownership |

## Native Codex options

Native `/goal` works toward a defined outcome, and Scheduled provides future follow-ups where
available. They are separate facilities, not aliases for these three skills. The bundled
supervisor uses the documented `codex exec` interface. Project ownership and event/fallback
rules are looperpowers conventions, not a universal Codex standard.
[Long-running work](https://learn.chatgpt.com/docs/long-running-work),
[scheduled tasks](https://learn.chatgpt.com/docs/automations),
[non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode).

Offline tests establish helper and supervisor process behavior with fake executables. Live
model decisions and integrations still need a controlled pilot. The worker engine remains
independent: the current sandbox-pal shell dispatcher still starts Claude workers.
