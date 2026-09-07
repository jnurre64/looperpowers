# {{project}} — project status

**The single source of truth for "where are we and what's next" when a session has to resume
from an interruption.** GitHub (board, milestones, `agent:*` labels) is the live detail; this is
the dashboard.

Maintenance contract (binding):
- The orchestrator updates this file at every event that changes state: a PR merged, a dispatch
  started, a plan bounced, a stop, a gate posted or passed. Commit straight to `{{default_branch}}`
  as `docs: STATUS — <what changed>`; no PR.
- **A dashboard, not a history.** Superseded lines are *replaced*, never appended. Merged PRs and
  closed issues live in git and GitHub; decisions live in `docs/DECISIONS.md`. Target ≤ 80 lines.
- Every "awaiting a human" line names exactly what is awaited and where it was posted.
- The pipeline's post-merge cleanup never edits this file; only the orchestrator does.

---

## Last updated: {{date}} — loop STOPPED (not yet started); restart with the configured client/mode command in `{{loop_doc}}`

## Where we are

Loop: `{{loop_doc}}`. Backlog: <!-- where the issues are filed from, if anywhere -->.

| Milestone | Scope (one line) | Status |
|---|---|---|
| <!-- first milestone --> | <!-- one line --> | Not started |

## Current phase

**Merged:** none yet.

**In flight:** none.

**Next ready:** <!-- the first issue to dispatch, and any constraint (parallel-safe, orchestrator-written plan) -->.

## Awaiting {{human}} (loop STOPPED {{date}})

1. Nothing yet.

## Loop conventions (binding, detail in `{{loop_doc}}`)

- Codex uses `$loop-start`; Claude uses `/loop-start`. Setup saves the runtime choice.
  Optional `--once` runs one iteration. Skill commands are chat prompts.
- One loop owner at a time (`claude-work/.loop-owner`). Status posts via `{{notify}}`; posts that
  need {{human}} use `{{mention}}`; routine lines never ping.
- Dispatch by `repository_dispatch`, never by label (the bot's label events are filtered).
- ≤ 2 issues in flight, disjoint only.
