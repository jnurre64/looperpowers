# The {{project}} Loop

How the backlog gets worked continuously. **Issues are the state**: status lives on the GitHub
issues (`agent:*` labels), the milestones, and the project board. This document is the
procedure; `{{status_file}}` is the dashboard a resuming session reads first.

- Repo: `{{repo}}` (default branch `{{default_branch}}`)
- Board: {{board_url}}
- Pipeline: {{pipeline}} label state machine on the self-hosted runners
- Orchestrator: the selected client/runtime per the lifecycle contract; posts to {{channel}}
  with `{{notify}}`

## Runtime boundary

The project workflow and substantive gates below are shared by both clients. Native Codex
Goal uses the interactive policy and objective added from CODEX-GOAL.md during setup.
Scheduler wakeups, timed reminders and the scheduled clean-main/publication lifecycle below
apply to scheduled runtimes; they are not prerequisites for native Goal. Native Goal preserves
the user workspace, records the same dashboard and uses confirmed native lifecycle controls.

## Roles

| Who | Does |
|---|---|
| Orchestrator (the owning session) | Sweeps, picks the next ready issue, dispatches it, gates plans (substantively — read the touched files), merges green PRs, updates the board, posts status, runs audits and design sessions with {{human}}, handles what the runners cannot. |
| Runners ({{pipeline}}) | Triage → plan → adversarial plan review → implement → post-implementation review → PR, per `agent`-labelled issue. |
| {{human}} | Design sessions, gate verdicts on their own schedule, feel notes anytime. |

## The only stops

The loop stops — posts to {{channel}} with `{{notify}}`, tagging `{{mention}}`, and waits — in
exactly these cases:

1. **Gate.** A milestone's gate issue is the only open work issue and the readiness bar (below)
   is met. The what-to-judge post is a numbered checklist, not prose.
2. **Undesigned work.** The next ready issue is a `design` issue, or a follow-up whose fix means
   new design. Post "needs a design session" with what is known.
3. **Spin guard.** The same issue reaches `agent:failed` or `agent:review-unresolved` **twice**,
   or a plan bounces at the gate twice. One retry is the orchestrator's; the second stop is
   {{human}}'s.
4. **Outside the orchestrator's authority:** service restarts, force-pushes, `rm -rf`, config
   edits outside the repo, secrets.
5. **Human-gated wait with nothing else to do.** When the only remaining action is a human step
   and no dependency-safe work remains: post ONE line naming exactly what is awaited, update
   `{{status_file}}`, then STOP owned scheduling through the verified runtime. **Never schedule polling
   wakeups for a human action** — the stopped loop IS the signal; {{human}} restarts it with
   the configured client/mode start command after acting.

While stopped at a gate, continue with dependency-safe work only (`parallel-safe: yes` issues
whose dependencies are closed), re-posting a one-line reminder every ~3–4 h. When none
remains, the loop parks. Never empty-loop.

**Stops and blocks MUST reach {{channel}}.** The posting path is `{{notify}}`; the session's own
chat bridge is not required. Verify the script **at loop start** by posting the kickoff line.
Posts that need {{human}} use `{{mention}}`; routine status lines never ping.

## One loop iteration

0. **Sweep the unmilestoned.** Issues with no label or no milestone are work, not noise:
   milestone them into the current phase (and into the backlog file, if the project keeps
   one) or close them.
1. **Sync:** current phase = lowest milestone with open issues. Never dispatch phase N+1 while
   phase N has open work issues, except `parallel-safe: yes` issues.
2. **Ready set:** open issues in the current phase whose dependencies are all closed, minus
   `blocked`, gate, `design`, audit issues and anything already carrying an `agent:*` label.
   `design` and audit issues are orchestrator work, never dispatched.
3. **Dispatch** by `repository_dispatch` (label events from the bot are filtered):
   `gh api repos/{{repo}}/dispatches -f event_type=agent-triage -F 'client_payload[issue_number]=N'`
   → the runner triages and posts a plan (`agent:plan-review`). Same with `agent-implement`.
4. **Plan gate:** read the plan against the issue's Scope / Acceptance **and the files it
   touches**, checking the project's architecture rules. Sane → `agent:plan-approved` +
   `agent-implement` dispatch. Off-spec → comment with corrections. A plan that bounces twice
   is rewritten by the orchestrator. The orchestrator writes the plan itself for
   architecture-defining issues and uses the `agent-implement` on-ramp (the plan comment MUST
   begin with `<!-- agent-plan -->`).
5. **Merge gate:** on `agent:pr-open` with green CI → orchestrator gates the diff, merges
   (squash), swaps `agent:pr-open` → `agent:done`, board Done. Red CI or unresolved review →
   investigate; `agent:failed` → retry once with more context, then escalate.
6. **Status:** update `{{status_file}}` (replace, never append), post one compact line with
   `{{notify}}`.
7. **Phase boundary:** when only the gate issue remains, meet the readiness bar, post the
   what-to-judge summary on the gate issue, and continue into the next phase (gates run
   open). Feel notes become issues in the current phase and outrank the spec.

## Readiness bar (a gate only opens on a testable build)

<!-- PROJECT-OWNED: list what "testable" means here (tests green, captures reviewed, deploy
     path, anything known-but-unfixed a tester would hit blocks the gate). -->

## Concurrency

Default **1 issue in flight**; 2 only when clearly disjoint (`parallel-safe: yes`, different
directories). The self-hosted runner may be this machine: never run heavy local jobs while CI
is running (`gh run list --limit 3` first).

## Liveness

A `killed` or `failed` task notification about a wait or a dispatch is **unverified until
checked** (`gh run view <id>`, `gh issue view <n> --json labels`, `git log origin/<branch>`).
Read dispatcher semantic `outcome` even if exit code is 0: `agent:failed` is failure.
Reconcile locks and runner state before calling work active. Never report work lost on a
notification alone; use the verified runtime completion wait, not sleep loops.

## Starting the loop

Preferred: Claude `/loop-start` or Codex `$loop-start`; setup saves the runtime choice. Start always runs
capability and ownership preflight. The legacy block below is Claude/persistent only. Codex
defaults to native Goal and requires its reviewed `start_blocks` mapping in loop.json;
never rewrite the legacy block at start time. All client blocks inherit every gate and stop
rule in this document, including project playtest requirements.
By hand, in the orchestrator session, after reading `{{status_file}}`:

```
/loop Run one {{project}} loop iteration per {{loop_doc}} for the current phase (entry: {{status_file}} "Next ready"; gh as {{bot_user}}; repo {{repo}} on {{default_branch}}). Self-pace: arm a persistent Monitor on agent:* label transitions and one per PR CI run; wake on those; long fallback (20–30 min) while a dispatch runs. Each iteration: sweep orphans, gate plans against the touched files, commit any .github/workflows or .claude edits the pipeline left for a human onto the agent branch, merge green PRs (merge {{default_branch}} in first if the branch predates a merge), mark agent:done + board Done, dispatch the next ready issues (≤2 in flight, disjoint), update {{status_file}}, post one status line with {{notify}}. Stop the loop (ScheduleWakeup stop) only on a {{loop_doc}} stop case, after posting it; on stop case 5 post what is awaited and stop — never schedule idle wakeups for a human step.
```

In the verified Claude runtime, `/loop` without an interval is self-paced: the session schedules its own next wake-up and
**stops itself** on a stop case. Claude pauses with `/loop-pause` and resumes with `/loop-start`.
Codex uses `$loop-pause` and `$loop-start` with the saved setup choice.
Optional `$loop-start --once` runs one iteration without changing that choice. Supervised mode requires its own committed timer policy and
iteration/pause sections; it never executes the legacy Claude block.

## Starting the loop (Codex bounded)

Select this through `start_blocks.codex.bounded` for `--once` (or an explicitly saved one-off default).

```text
Run exactly one attended {{project}} loop iteration per {{loop_doc}} for the current phase (entry: {{status_file}} "Next ready"; gh as {{bot_user}}; repo {{repo}} on {{default_branch}}). Preserve all plan, merge and playtest gates, readiness bars, spin guard, concurrency, dependency rules and notification checks in {{loop_doc}}. Perform immediately available work only; never wait or schedule another iteration. Inspect dispatcher semantic outcomes and locks before dispatching. When only a human action remains, post once naming what is awaited and stop without polling. At the end, use loop-pause to stop owned machinery, record PRs and workers still in flight in {{status_file}}, publish status, notify with {{notify}}, and release verified ownership. State that no future wakeup is armed.
```

## Ground rules

- Definition of done per issue = its Acceptance section + tests green in CI, never weakened.
- Feel notes outrank spec.
- The orchestrator records nontrivial design and infra calls in `docs/DECISIONS.md`.
- `{{status_file}}` is the resume point: updated at every state change and kept a dashboard
  (≤ 80 lines, replace never append). Scheduled/bounded runtimes commit it straight to
  `{{default_branch}}`. Native Goal follows the interactive publication policy: preserve the
  current workspace and disclose local-only status until publication is authorized.
- Agent branches are cut from `{{default_branch}}` at dispatch time; one that predates a merge
  gets `{{default_branch}}` merged in (keep both DECISIONS entries, `git rm --cached` any
  force-added review ledger). Never force-push an agent branch.

<!-- PROJECT-OWNED: add the project's own rules below (toolchain versions, test flags, backlog
     file conventions). -->
