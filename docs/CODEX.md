# Using looperpowers with Codex

Use this guide after [installing the shared skills](../README.md#install). All `$loop-*`
examples are **Codex chat prompts**, not terminal commands. Run terminal commands from the
project root unless indicated otherwise. The repository containing the skills and the project
being orchestrated can be different checkouts.

## Prepare the project

Open Codex in the project to orchestrate. Ensure Git and `gh` are available, and that `gh`
is authenticated as the identity the project's pipeline expects. The project needs its own
working dispatcher, gates and notification path; looperpowers manages their lifecycle.

```text
$loop-setup Configure this project for Codex bounded mode. Discover existing settings and preserve project policy.
```

Setup discovers project guidance from AGENTS.md/CLAUDE.md and non-secret dispatcher settings
from `.sandbox-pal-dispatch/config.defaults.env` and explicit config.env overrides. It asks
for missing data and shows changes to existing config. It does not source config files,
change authentication, configure runners or start a service.

The shared files are:

| File | Purpose |
|---|---|
| `claude-work/loop.json` | Project identity, paths, notification command, selected start headings |
| `docs/LOOP.md` | Project procedure, gates, stop cases and exact client/mode prompts |
| `claude-work/STATUS.md` | Resume dashboard, with configured path overridable in loop.json |
| `claude-work/.loop-owner` | Ignored runtime ownership record used by both clients |

Keep the `claude-work` name when migrating. It is a compatibility path, not an instruction
to run Claude. Setup can suggest a pointer from AGENTS.md to the loop documents, but does
not edit AGENTS.md itself. Review and commit setup before starting.

## One attended iteration

Add the following mapping to the existing config, merging with any existing `start_blocks`:

```json
"start_blocks": {
  "claude": {"persistent": "Starting the loop"},
  "codex": {"bounded": "Starting the loop (Codex bounded)"}
}
```

This is a JSON fragment, not a replacement loop.json. The headings must exist in the
configured loop_doc. The [LOOP template](../templates/LOOP.md) supplies a bounded block;
setup renders it with project values. Existing project gates and policy must also permit
bounded execution. Do not copy an unrendered template into a running project.

```text
$loop-start --mode bounded
```

Preflight checks the clean default branch, remote sync, GitHub identity, notification path,
selected command, dashboard and reconciled ownership/scheduler/worker state. The selected
block is executed verbatim. One iteration can leave asynchronous workers or CI in flight;
the dashboard records them before the orchestrator pauses. No next wakeup is armed.

```text
$loop-pause
```

Pause stops owned orchestration first, settles only already-gated green work and records the
resume point. `$loop-pause drain` requests a bounded completion wait where supported. It does
not authorize a new gate or new dispatch. Repeat the explicitly selected start command to resume.

## Repeated iterations with the supervisor

For a machine-hosted timer loop, explicitly request a supervised setup migration:

```text
$loop-setup Configure Codex supervised mode with an explicit timer policy. Preserve all project gates and the existing Claude and bounded commands.
```

Setup proposes `codex_supervisor` settings and `start_blocks.codex.supervised` /
`supervised_pause` mappings, plus both rendered prompts from
[CODEX-SUPERVISOR.md](../templates/CODEX-SUPERVISOR.md). Review existing requirements for
completion monitors: timer supervision is a policy change if the project requires events.

Then use:

```text
$loop-start --mode supervised
```

This routes Codex to the [supervisor procedure](../skills/loop-start/references/codex-supervisor.md).
A host process manager, authorized credentials and fresh external-runtime/worker reconciliation
are required for unattended operation. The skill does not install a service or turn a chat's
background process into a durable scheduler. The supervisor invokes `codex exec` with explicit
workspace-write sandboxing, exact project prompts and structured results.

For terminal operations, substitute the actual package path:

```bash
python3 /path/to/looperpowers/skills/loop-start/scripts/supervisor.py inspect
python3 /path/to/looperpowers/skills/loop-start/scripts/supervisor.py stop --token <owner-token>
```

A stop request is graceful, not immediate cancellation: the current iteration can finish
before pause runs. `stopped: false` acknowledges the request only. Check for a free lock,
stopped state and released ownership before claiming success. Drain is unavailable for this
runtime; use the ordinary graceful stop. Never settle PRs concurrently from another session.

## Migrate an existing Claude project

1. Pause through the owning Claude session and verify its wakeups/monitors are stopped.
   Codex cannot cancel them by calling tools in its own session.
2. Reconcile open PRs, current-head CI, dispatcher outcomes and locks. Exit code 0 with
   `outcome=agent:failed` is a terminal failure; an absent lock alone does not establish safety.
3. If the dashboard says PAUSED, complete the shared pause/recovery procedure and publish a
   truthful STOPPED dashboard. Do not change only the header.
4. Run `$loop-setup` for the explicitly selected Codex mode, preserving existing config keys
   and Claude blocks. Review any conflicting scheduler policy and commit the migration.
5. Start from a clean, synchronized default branch. Begin with a controlled pilot before
   leaving repeated operation unattended.

Existing config without `start_blocks` selects the legacy Claude/persistent command only.
`$loop-start` without a mode does not mean Codex bounded mode. The supervisor refuses existing
owners rather than offering blind force takeover. Details are in the
[shared runtime contract](../skills/loop-start/references/runtime.md).

## Troubleshooting

| Symptom | What to check |
|---|---|
| Codex cannot find a skill | Run `install.sh codex`, inspect the links under `~/.agents/skills`, keep the package checkout available, and restart Codex if needed. Confirm a custom CODEX_SKILLS_DIR is a discovery location. |
| Missing start block | Verify the selected client/mode mapping and matching heading; use setup for a reviewed migration, not a start-time rewrite. |
| Missing scheduler capabilities | Choose bounded mode explicitly, or configure the runtime required by committed policy. Never pretend a future wakeup is armed. |
| Dirty or unsynchronized checkout | Reconcile pending changes and branch state before starting. Do not discard files to satisfy preflight. |
| GitHub identity mismatch | Check `gh api user -q .login` against bot_user. The authenticated identity and its token need permissions for the project's actual operations. |
| Owner belongs to another client | Pause through that runtime or obtain verified shutdown and explicit recovery. Timestamps are not authority to take over. |
| Supervisor lock free but owner remains | Inspect state/logs and reconcile processes, workers and external scheduling. This may be interrupted execution or a failed pause, not a clean stop. |
| Notification fails | Kickoff failure prevents dispatch. Later failure retains ownership; fix delivery and complete recovery before release. |
| Codex operation is blocked by sandbox/permissions | Report failure and configure an authorized runtime with the required access; the supervisor does not bypass approvals. |

## Native Codex options and scope

For an interactive objective, native `/goal` follows a completion condition. Scheduled tasks
provide future follow-ups where available. Neither is an alias for these lifecycle skills;
use the project's selected runtime and ownership procedure.
[Official long-running work](https://learn.chatgpt.com/docs/long-running-work),
[scheduled tasks](https://learn.chatgpt.com/docs/automations).

For automation, `codex exec` is the documented CLI interface and the SDK supports programmatic
control. The bundled supervisor uses the CLI. Tests use fake executables; they establish
supervisor process behavior, not the correctness of every model decision or live integration.
[Official non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode),
[Codex SDK](https://learn.chatgpt.com/docs/codex-sdk).

The worker engine remains independent: Codex orchestration of the current sandbox-pal shell
dispatcher still starts Claude workers. Changing that engine is outside this package.
