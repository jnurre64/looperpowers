# looperpowers — loop-setup, loop-pause, loop-start — design

> Historical design: this records the original Claude-only behavior. For current usage, see
> the [README](../../../README.md), [Codex user guide](../../CODEX.md), and
> [shared runtime contract](../../../skills/loop-start/references/runtime.md). Their client
> selection and verified ownership recovery supersede the original force-transfer rules.

**Date:** 2026-09-06 · **Status:** approved in brainstorm with Jonny (2026-09-06), written for review
**Repo:** `jnurre64/looperpowers` · **Installs into:** `~/.claude/skills/` (symlinks)
**First consumers:** `Frightful-Games/AnomalisticsIdle`, `jnurre64/FingerWizard`

## 1. What this is

Three global Claude Code skills that own the lifecycle of a self-paced orchestrator loop
(the `/loop` that grinds a GitHub backlog through the sandbox-pal pipeline):

| skill | one line |
|---|---|
| `loop-setup` | Give a project the two loop documents and the config the other two skills read. |
| `loop-pause` | Reach a clean, clear stopping point and leave the project ready to resume. |
| `loop-start` | Preflight, then start the loop with the project's exact command. |

The **procedure** is identical across projects; only **data** differs (paths, bot, notify
command, board). So the skills are global and versioned in this repo, and every project-specific
value lives in the project: `claude-work/loop.json` and the "Starting the loop" block of
`docs/LOOP.md`. A project never forks a skill; it edits its data.

Decisions made with Jonny (do not relitigate):
- **Placement:** one skills repo, symlinked into `~/.claude/skills/`, per-project config (§2).
- **Pause semantics:** finish what is cheap, wait for nothing (§3). `drain` is the opt-in that waits.
- **Setup scope:** writes `loop.json`, STATUS.md, and LOOP.md (from a template when absent, the
  "Starting the loop" block only when present). Never the pipeline, workflows, or notify script.

## 2. Repo layout and config

```
looperpowers/
├── README.md                      install + the three commands
├── install.sh                     symlinks skills/* into ~/.claude/skills/ (idempotent)
├── skills/
│   ├── loop-setup/SKILL.md
│   ├── loop-pause/SKILL.md
│   └── loop-start/SKILL.md
├── templates/
│   ├── LOOP.md                    roles, stop cases, one iteration, concurrency, ground rules,
│   │                              "Starting the loop" — with {{placeholders}}
│   └── STATUS.md                  the dashboard + maintenance contract, STOPPED header
├── tests/                         pressure scenarios + baseline transcripts (writing-skills TDD)
└── docs/superpowers/specs/        this file
```

### 2.1 `claude-work/loop.json` (committed in the project)

```json
{
  "project": "Anomalistics Idle",
  "repo": "Frightful-Games/AnomalisticsIdle",
  "default_branch": "main",
  "status_file": "claude-work/STATUS.md",
  "loop_doc": "docs/LOOP.md",
  "notify": "./scripts/notify-discord.sh",
  "mention": "<@181479592735932416>",
  "bot_user": "pennyworth-bot",
  "board": {"org": "Frightful-Games", "number": 1, "done": "Done"},
  "pipeline": "sandbox-pal",
  "agent_branch_prefix": "agent/issue-",
  "cleanup_pr_prefix": "chore: post-merge cleanup"
}
```

Every skill begins: read `loop.json` (refuse with one line naming `loop-setup` if absent), read
`status_file`. Missing optional keys take these defaults: `notify` → print to the user only;
`board` → skip board moves; `mention` → no ping.

### 2.2 The loop command lives in LOOP.md, not in the config

The fenced block under the heading `## Starting the loop` in `loop_doc` is the single source.
`loop-start` extracts it verbatim (first fenced block after that heading) and passes it to
`/loop`. Editing the prompt is a doc edit and a commit, never a skill edit.

### 2.3 Owner file

`loop-start` writes `claude-work/.loop-owner` (`host`, `session`, `started_at`; gitignored via
setup); `loop-pause` removes it. A second `loop-start` refuses while it exists unless passed
`--force`, printing the owner.

## 3. `loop-pause` [drain]

Order matters: the machinery stops before anything else so no iteration fires mid-pause.

1. **Stop the machinery.** `ScheduleWakeup stop`; `TaskStop` every monitor the loop armed
   (`TaskList` to find them). Confirm nothing is scheduled.
2. **Settle what is cheap; wait for nothing.** For each open PR whose head branch starts with
   `agent_branch_prefix`:
   - gating CI green and the orchestrator gate already passed → merge (squash), label
     `agent:pr-open` → `agent:done`, board Done, pull;
   - gate passed, CI still running → leave open, record in STATUS;
   - gate not yet passed → leave open, record "needs gate" in STATUS (pause never gates: a
     gate is judgement work, not settling).
   Cleanup PRs matching `cleanup_pr_prefix` → close with a reason. CI runs on superseded heads
   → cancel. **With `drain`:** for "CI still running" PRs, wait (poll with `gh run list`, no
   sleep loops, 10 min ceiling per PR), then merge when green.
   Never dispatch anything new.
3. **Clean the tree.** Commit pending docs to `default_branch`; delete local copies of merged
   agent branches; `git status` must be empty and HEAD on `default_branch`, pushed.
4. **Write STATUS** (replace, never append): header `STOPPED (<reason>) <UTC time>`; **In
   flight** lists each open PR / run and what the first iteration will do with it; **Next
   ready** names the next issue(s) and any constraint (parallel-safe, orchestrator-written
   plan); **Awaiting <human>** lists what a person owes. No manual checklist — `loop-start` is
   the checklist. Commit straight to `default_branch`.
5. **Remove the owner file. Post the pause line** through `notify` (⏸️ project · progress ·
   what is in flight · next). Report to the user in three lines: where things stand, what is
   in flight, how to resume.

The user's instruction wins over the order when they say so ("just stop now" = step 1 + 4 + 5).

## 4. `loop-start` [--force]

1. **Preflight** (every check prints its fix on failure; any failure stops before `/loop`):
   `loop.json` present; on `default_branch`, clean tree, up to date with origin; `gh api user`
   is `bot_user` (or the configured human when the pipeline filters bot labels — say which);
   `notify` exists and is executable; the "Starting the loop" block exists; no owner file (or
   `--force`).
2. **Situation.** Read STATUS and show one paragraph: header, in flight, next ready, awaiting.
3. **Start.** Write the owner file; invoke `/loop` with the fenced block verbatim; post the
   resume line (▶️). The loop's first iteration handles whatever pause left in flight.

## 5. `loop-setup`

Idempotent; safe to re-run; asks one question at a time and only for what it cannot discover.

1. **Discover:** repo + default branch from `git remote` / `gh repo view`; bot user, runner
   labels from `.sandbox-pal-dispatch/config.env` when present; notify script by name under
   `scripts/`; org project by `gh project list --owner <org>`; mention from an existing LOOP.md
   or STATUS.md if any. Each discovered value is offered as the default.
2. **Write `claude-work/loop.json`.** Existing keys are never overwritten silently: show the
   diff, ask.
3. **LOOP.md.** Absent → render `templates/LOOP.md` with the values. Present → append the
   "Starting the loop" block only if no such heading exists; never edit other sections.
4. **STATUS.md.** Absent → render `templates/STATUS.md` (maintenance contract, STOPPED header,
   empty tables to fill). Present → untouched.
5. **`.gitignore`:** add `claude-work/.loop-owner`.
6. **Commit** to `default_branch` (`docs: loop setup — loop.json, LOOP.md, STATUS.md`), print
   "next: /loop-start".

## 6. Templates

`templates/LOOP.md` is this repo's `docs/LOOP.md` shape generalised: roles, the stop cases
(device gate, undesigned work, spin guard, infra down, human step), one iteration (sweep,
sync, ready set, dispatch, plan gate, merge gate, status, phase boundary), readiness bar,
concurrency, liveness, **Starting the loop** (the fenced `/loop` prompt with placeholders),
ground rules. Placeholders: `{{project}}`, `{{repo}}`, `{{status_file}}`, `{{bot_user}}`,
`{{notify}}`, `{{mention}}`, `{{channel}}`, `{{human}}`.

`templates/STATUS.md`: the dashboard used in AnomalisticsIdle (maintenance contract, "Last
updated" header, milestone table, current-phase block with Merged / In flight / Next ready,
Awaiting <human>, loop conventions), ≤ 80 lines, replace-never-append.

## 7. Testing (writing-skills TDD)

Each skill is a discipline skill (the failure mode is skipping a step under "just stop / just
start" pressure), so each gets a pressure scenario run **without** the skill first, in a
scratch clone of AnomalisticsIdle with a fake `gh` where needed, the observed omissions
recorded verbatim under `tests/`, then the skill written against them and re-run until it
complies. Expected baseline failures to look for: pausing without stopping the wakeup first;
writing a manual checklist into STATUS instead of a dashboard; starting without checking the
tree or the owner file; setup overwriting an existing LOOP.md.

`loop-setup` is additionally run for real against a scratch copy of FingerWizard (has LOOP.md,
lacks STATUS and the start block) to prove the template path.

## 8. Out of scope

Porting the pipeline (`sandbox-pal`), the notify script, CI workflows; multi-owner loops;
anything that changes how an iteration works (that is `docs/LOOP.md`'s job in each project).
