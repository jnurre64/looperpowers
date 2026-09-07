# looperpowers

Three shared lifecycle skills for Claude Code and Codex: `loop-setup` creates project data,
`loop-start` preflights and starts the selected runtime, and `loop-pause` reaches a clear
stopping point. Claude invokes `/loop-start`; Codex invokes `$loop-start`.

```bash
./install.sh          # Claude: ~/.claude/skills (historical default)
./install.sh codex    # Codex: ~/.agents/skills
./install.sh all      # both clients, same source skills
```

`CLAUDE_SKILLS_DIR` and `CODEX_SKILLS_DIR` override the respective destination. Re-run after
pulling; existing unrelated files or symlinks are preserved. Keep the package checkout:
skills resolve shared references, helpers and templates through their real installed path.
Codex supports user `.agents/skills` discovery and symlinked skill folders
([official documentation](https://learn.chatgpt.com/docs/build-skills)).

| Runtime | Support |
|---|---|
| Claude with verified loop/scheduler/monitor tools | Persistent unattended loop |
| Ordinary Codex turn | Explicit `--mode bounded`: one attended iteration; no future wakeup |
| Either client with an external scheduler | Persistent only after the full capability contract passes; no adapter is bundled |

An installed skill is not a scheduler. Scheduled app tasks are a separate facility with
runtime requirements ([official documentation](https://learn.chatgpt.com/docs/automations?surface=app));
their presence alone does not satisfy completion wakeups, ownership and cancellation.
The worker engine is unchanged: sandbox-pal's shell dispatcher still launches Claude workers.

Project data stays in `claude-work/loop.json` and `docs/LOOP.md`. Existing config remains
valid for Claude/persistent. For Codex, explicitly add `start_blocks.codex.bounded` pointing
to `Starting the loop (Codex bounded)` and commit the matching block (see the template).
Review existing project policy for incompatible tool requirements before migrating.
There is no silent runtime downgrade or start-time command translation.

Read the [runtime contract](skills/loop-start/references/runtime.md) for capabilities,
verbatim command selection, notification rollback, PAUSED migration and cross-client
ownership recovery. `--force` never bypasses verified shutdown of the prior runtime. A
STOPPED header or absent worker locks cannot prove another client's wakeups are cancelled.
All clients sharing a project must upgrade together; independent checkouts require a
scheduler providing project-wide exclusion.

Run local tests (Python 3, Bash, no GitHub mutations or notifications):

```bash
python3 -m unittest discover -s tests -v
```

The [original design](docs/superpowers/specs/2026-09-06-loop-skills-design.md) and baseline
transcripts under `tests/baselines/` are historical. The shared runtime contract supersedes
their Claude-only lifecycle and blind force-transfer behavior.
