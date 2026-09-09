# Using looperpowers with Codex

Use **`$loop-setup` → `$loop-start` → `$loop-pause`** in Codex chat. Claude uses the same
names with `/`. [Install the shared skills](../README.md#install) in each client.

## Setup once

`$loop-setup` discovers the project's settings, procedure, gates and notification path.
New setups route Codex to native Goal and Claude to the existing event-driven loop. There
is no runtime menu for ordinary use. Setup asks only for missing project decisions, including
the outcome and human checkpoint if the existing plan does not establish them.

Both clients use the same files:

| File | Purpose |
|---|---|
| `claude-work/loop.json` | Shared settings and client command headings |
| `docs/LOOP.md` | Project procedure, gates, outcomes and client commands |
| `claude-work/STATUS.md` | Shared progress, in-flight work, next ready work and human asks |
| `claude-work/.loop-owner` | Ignored current runtime/session ownership |

Paths can be configured; existing compatibility paths remain valid. Setup preserves unknown
keys and existing Claude commands. It does not start a Goal, install a service, or change
credentials. Native Goal setup/start does not require clean main, a push, a new worktree or an
arbitrary iteration budget. Existing project rules still govern the actions performed.

## Start, pause and switch clients

`$loop-start` reads the common resume point and inspects actual native state and ownership.
It creates a scoped Goal or resumes the matching Goal, then continues toward the agreed
outcome. Missing design/playtest evidence blocks dependent work; independent designed work
within scope can continue. All existing plan, review, current-head CI, merge and playtest gates
remain in force. Goal does not grant additional permissions.

`$loop-pause` stops new work, uses the owning runtime's controls and saves the same dashboard.
It preserves dirty/staged files, unpublished commits and the current branch. Publication
follows project policy and user authorization; local-only status is disclosed.

Some Codex environments expose creation/inspection tools but no native pause/resume tool.
For pause, the skill first uses its ownership-checked native API helper and verifies
readback; it does not require a model-facing pause tool. If the installed API is
unavailable or unconfirmed, it gives `/goal pause`. Resume still uses an exposed
control or `/goal resume`. A UI handoff reports pending
until native state confirms the transition. If only command UI is available for creation,
it supplies `/goal <project objective>`. It never claims a Goal started just from preparing
a command, or treats complete/blocked as a substitute for pause.

A paused Goal retains ownership because it can resume natively. To switch to Claude or another
session, verify the old runtime can no longer write, reconcile workers and release its token
before the next client starts. The skill guides that transfer; deleting the owner file is not
recovery. Native Goal controls do not stop Claude wakeups, a host supervisor or detached workers.
Linked worktrees share acquisition exclusion; separate clones/hosts need an external coordinator
or one orchestration checkout. Update both clients before relying on this protection.

## Continuation and optional controls

| Runtime | How work continues |
|---|---|
| Codex Goal (ordinary) | Works toward a scoped outcome within the native session |
| Claude event loop (ordinary) | Wakes on completion events, with the project's fallback timer |
| Codex supervisor (optional) | A configured host process invokes Codex on a timer |
| `--once` (optional) | One iteration, then saves the resume point and stops |

Goal is not an offline service or a guarantee of future scheduled wakeups. When only human
work remains, record the exact ask and use supported native checkpoint/stop controls.
`$loop-start --once` requires its own project block and keeps the saved default unchanged.
`$loop-pause drain` uses a supported bounded wait only; the supervisor does not support drain.

## Migration and advanced configuration

Existing explicitly saved timer or bounded choices remain intact. Run `$loop-setup` to review
migration to Goal. Missing Codex defaults select Goal, but a missing Goal project block still
requires setup. Legacy Claude projects keep their existing command and persistent behavior.
New configuration includes this additive fragment:

```json
"default_modes": {"claude": "persistent", "codex": "goal"},
"start_blocks": {
  "claude": {"persistent": "Starting the loop"},
  "codex": {"goal": "Starting the loop (Codex Goal)"}
}
```

Render the [Goal template](../templates/CODEX-GOAL.md) into the project procedure with a
concrete outcome and checkpoint. Keep the exact objective within 4,000 characters and put
long policy in referenced project files. Review any existing scheduler-specific publication
rules when adding the interactive policy; do not weaken substantive gates.

Advanced `--mode goal|persistent|bounded|supervised` overrides still need corresponding
capabilities and project blocks. `--once` and `--mode` are mutually exclusive. `--force`
requires verified shutdown/transfer; it never means blind takeover. Timer hosting requires
explicit setup and project timer policy; see the [supervisor guide](../skills/loop-start/references/codex-supervisor.md).

## Troubleshooting and verification

| Symptom | Next step |
|---|---|
| Skills missing | Re-run install.sh codex, check symlinks and restart the client if needed |
| Goal block missing | Run setup to add the reviewed project objective |
| Native controls unavailable | Inspect actual tool/UI support; no silent timer or bounded fallback |
| Pause/resume pending | Use the supplied native command and confirm via `/goal` |
| Foreign or inconsistent owner | Reconcile in the owning session; preserve the record |
| Permissions or publication blocked | Resolve the actual operation; Goal does not alter authorization |
| Notification failed | Report locally and retain ownership where recovery is unresolved |

See the [native adapter contract](../skills/loop-start/references/codex-goal.md) and
[shared ownership contract](../skills/loop-start/references/runtime.md).
Official references: [Follow goals](https://learn.chatgpt.com/use-cases/follow-goals),
[developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli), and
[long-running work](https://learn.chatgpt.com/docs/long-running-work).

Offline tests exercise routing, ownership and supervisor processes with local fakes. They do
not establish real native lifecycle behavior or model adherence to project gates; those need
a controlled pilot. The orchestrator backend is independent of the worker engine: the current
sandbox-pal shell dispatcher still launches Claude workers.

## Native self-pause validation (September 9, 2026)

Codex CLI0.153.4 exposes native `thread/goal/get` and status-only
`thread/goal/set` even when the model tool surface has no pause operation. The
control-only stdio helper read an existing owned Goal, verified its identity and
confirmed an idempotent paused-state request against the real native API. An
independent model-facing Goal read also reported paused. No live Goal was created,
resumed or turned active for this check; active→paused behavior is covered by the
fake-peer and actual-stdio regression tests, not claimed as a live transition.

The live check caught a legacy owner binding made from a trailing-newline source
while native Codex stored trimmed text. Explicit hash-checked whitespace repair
fixed the metadata without replacing the Goal, changing usage/budget or releasing
ownership. Bare-start routing now compares the native-normalized objective.

All61offline lifecycle/owner/supervisor/native tests pass; both modified skills
pass structural validation. Installed symlinks use this same source. These checks
do not certify all Codex versions or stop foreign workers. On an unsupported or
unconfirmed native API, retain ownership and use the documented UI handoff.
