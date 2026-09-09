# looperpowers

Three shared lifecycle skills for Claude Code and Codex: **setup, start, pause**. They
coordinate a GitHub backlog through your project's existing pipeline, gates and notifications.

| Task | Codex | Claude Code |
|---|---|---|
| Configure the project once | `$loop-setup` | `/loop-setup` |
| Start or resume its configured loop | `$loop-start` | `/loop-start` |
| Stop at a clear resume point | `$loop-pause` | `/loop-pause` |

These are chat prompts, not shell commands. Codex uses native Goal; Claude uses its existing
event-driven loop. Both share the same project status, gates and ownership. Start selects the
client backend automatically; pause follows the actual owner. No runtime flags are needed.

## Install

Run in a terminal:

```bash
git clone https://github.com/jnurre64/looperpowers.git ~/repos/looperpowers
~/repos/looperpowers/install.sh codex   # ~/.agents/skills
# Other choices:
~/repos/looperpowers/install.sh claude  # ~/.claude/skills; no-argument default
~/repos/looperpowers/install.sh all     # both clients, same source skills
```

Use a POSIX environment with Bash, Python 3, Git and `gh`; tests run on Linux. The ownership
helper does not support native Windows. The Codex supervisor also needs Codex CLI on its host.
`CODEX_SKILLS_DIR` and `CLAUDE_SKILLS_DIR` override installation destinations. Keep the package
checkout: installation uses symlinks. Re-run after pulling updates; restart the client if the
skills do not appear. [Official Codex skill discovery](https://learn.chatgpt.com/docs/build-skills).

## Everyday use

Open Codex in the **project you want to orchestrate** and run `$loop-setup`. It discovers
existing settings and saves the shared workflow and client commands. Native Goal continues a
scoped outcome in the Codex session; ordinary setup needs no host service or iteration cap.

Once setup is ready, use `$loop-start`. Use
`$loop-pause` when you want to stop, and `$loop-start` again to resume. Claude uses the same
three names with `/` instead of `$`.

The shared configuration remains `claude-work/loop.json`, with the procedure in `docs/LOOP.md`
and resume dashboard in `claude-work/STATUS.md`. Those compatibility paths serve both clients.
Setup does not install the worker pipeline or notification script. Codex orchestration of
the current sandbox-pal shell dispatcher still starts Claude workers.

## Optional controls

- `$loop-start --once`: run one iteration and stop. This is the old `bounded` mode, useful
  for a manual run or pilot. It needs a configured one-iteration block and does not change
  the saved default or schedule a future wakeup.
- `$loop-pause drain`: wait briefly for eligible in-flight CI where the runtime supports it.
- Existing `--mode` overrides and `--force` remain advanced controls. Force never bypasses
  verified shutdown of the previous owner.

Codex Goal continues toward the agreed outcome within the session. Claude wakes on worker/CI
completion with its existing fallback. The optional Codex supervisor uses a host timer;
`--once` stops after one iteration. All preserve the same project gates and stop rules.

When switching clients, pause the previous owner and verify transfer first. A paused native
Goal retains ownership until it cannot resume writes. When a Codex surface lacks a pause tool, the skill uses the native API pause helper
with ownership and readback checks. If that route is unavailable, it requests
`/goal pause`; resume may require `/goal resume`. UI handoffs remain pending until
native state confirms them.
Existing saved timer/bounded defaults remain unchanged until a reviewed setup migration.

See the [Codex guide](docs/CODEX.md) for setup/migration and runtime details, the
[supervisor guide](skills/loop-start/references/codex-supervisor.md) for hosting, and the
[shared contract](skills/loop-start/references/runtime.md) for ownership and recovery.

## Development

```bash
python3 -m unittest discover -s tests -v
```

Tests use local temporary repositories and fake Codex/GitHub/notifications. Validate actual
project prompts and hosting in a controlled pilot before unattended use. The
[original design](docs/superpowers/specs/2026-09-06-loop-skills-design.md) and baseline
transcripts are historical; current guidance supersedes their Claude-only behavior.
