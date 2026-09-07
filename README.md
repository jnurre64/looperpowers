# looperpowers

Three shared lifecycle skills for Claude Code and Codex. They coordinate a GitHub backlog
through your project's existing pipeline, gates, and notification path.

| Task | Codex prompt | Claude Code prompt |
|---|---|---|
| Create or migrate project loop documents | `$loop-setup` | `/loop-setup` |
| Run one attended iteration | `$loop-start --mode bounded` | `/loop-start --mode bounded` |
| Run the Codex timer supervisor | `$loop-start --mode supervised` | Not a Claude runtime |
| Start the existing event-driven loop | Requires a verified compatible adapter | `/loop-start` |
| Pause the selected runtime | `$loop-pause` | `/loop-pause` |

Type skill prompts in the client chat, not your shell. Each mode needs its own committed
project command. The template provides Claude/persistent and Codex/bounded commands;
Claude/bounded requires a project-owned block. Starting without a mode retains the historical
`persistent` default; Codex never silently falls back to bounded mode.

## Install

Run in a terminal:

```bash
git clone https://github.com/jnurre64/looperpowers.git ~/repos/looperpowers
~/repos/looperpowers/install.sh codex   # ~/.agents/skills
# Other choices:
~/repos/looperpowers/install.sh claude  # ~/.claude/skills; also the no-argument default
~/repos/looperpowers/install.sh all     # both clients, same source skills
```

The scripts require Bash, Python 3 and a POSIX environment; supervisor tests run on Linux.
Project operations use Git and `gh`, plus the configured pipeline and notification script.
The supervisor also needs Codex CLI on its host. Native Windows execution is not supported
by the POSIX ownership helper; use an appropriate Linux environment for that runtime.

`CODEX_SKILLS_DIR` and `CLAUDE_SKILLS_DIR` override their respective destinations. Keep this
checkout: installed skills are symlinks, and templates/references resolve through it. Existing
unrelated files or links are preserved. Re-run the installer after pulling updates; restart
the client if the skills do not appear. Codex supports `.agents/skills` discovery and symlinked
skills ([official skill documentation](https://learn.chatgpt.com/docs/build-skills)).

## First run with Codex

Open Codex in the **project you want to orchestrate**, then send:

```text
$loop-setup Configure this project for Codex bounded mode. Preserve existing Claude commands and all project gates.
```

Review the discovered settings and generated documents. Setup creates or updates
`claude-work/loop.json`, `docs/LOOP.md`, the STATUS dashboard and the owner-file ignore rule.
The `claude-work` name is retained for compatibility in both clients. Setup does not install
the worker pipeline, create a notification script, or start the loop.

Once setup is committed and the checkout is clean and ready, send:

```text
$loop-start --mode bounded
```

This runs one attended iteration and records the resume point. It does not arm a future
wakeup. Use `$loop-pause` to pause; `drain` is available only when the selected runtime can
perform a bounded completion wait.

For existing projects, mode configuration, supervised execution and troubleshooting, read
[the Codex user guide](docs/CODEX.md).

## Choose how work continues

| Runtime | What continues the work |
|---|---|
| Bounded skill invocation | The user starts the next iteration |
| Codex exec supervisor | A running host service invokes Codex at the committed interval |
| Claude event-driven loop | Verified loop/scheduler/monitor tools |
| Native Codex `/goal` | Interactive work toward a defined completion condition |
| Native Scheduled tasks | The product's configured scheduled-task facility |

Native `/goal` and Scheduled are separate from our lifecycle commands
([long-running work](https://learn.chatgpt.com/docs/long-running-work),
[scheduled tasks](https://learn.chatgpt.com/docs/automations)). A skill installation or ordinary
chat turn does not establish future liveness. Owner records, exact start blocks, and the
legacy event/fallback contract are project conventions, not a universal Codex standard.

The [supervisor guide](skills/loop-start/references/codex-supervisor.md) covers explicit timer
policy, host process management, structured results and graceful stopping. No service is
installed automatically. Project gates remain binding. Changing the orchestrator to Codex
does not change the worker engine: sandbox-pal's current shell dispatcher still launches
Claude workers.

## Ownership and recovery

All clients share `claude-work/.loop-owner`. `--force` never bypasses verified shutdown of
the prior runtime. A STOPPED/PAUSED dashboard or absent worker locks cannot prove another
client's wakeups are cancelled. Upgrade all clients using a project together; independent
clones require coordination beyond a checkout-local owner file.

See the [shared runtime contract](skills/loop-start/references/runtime.md) for capability
checks, exact command selection, failed notifications, legacy PAUSED migration, and recovery.

## Development and validation

```bash
python3 -m unittest discover -s tests -v
```

Tests use temporary local Git repositories and fake Codex/GitHub/notification executables.
They cover helpers and supervisor process behavior, including timeouts, owner conflicts,
graceful stops and crash retention. They do not contact live services. Validate actual
Codex access, project prompts and service hosting in a controlled pilot before unattended use.

The [original design](docs/superpowers/specs/2026-09-06-loop-skills-design.md) and baseline
transcripts under `tests/baselines/` are historical. Current user guidance and the shared
runtime contract supersede their Claude-only lifecycle and blind force-transfer behavior.
