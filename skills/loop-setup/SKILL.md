---
name: loop-setup
description: Use when a project needs the orchestrator-loop documents and config (claude-work/loop.json, the STATUS dashboard, the "Starting the loop" block in docs/LOOP.md), or when /loop-start or /loop-pause report that loop.json is missing.
---

# loop-setup

Give a project exactly the files `loop-pause` and `loop-start` read. Idempotent; safe to re-run.
**Writes four things and nothing else:** `claude-work/loop.json`, `claude-work/STATUS.md` (if
absent), `docs/LOOP.md` (template if absent, else missing start sections or an explicitly selected client-block migration), one `.gitignore` line. Other edits you think the project needs (CLAUDE.md pointer,
old hand-off notes, DECISIONS) are **printed as suggestions**, never made.

Read [the shared runtime contract](../loop-start/references/runtime.md). Resolve this loaded
SKILL.md to its real path (follow installation symlinks); templates are at `../../templates/`
relative to its skill folder. Never assume a Claude home path. If the package resources are
missing, stop with a reinstall instruction.

## 1. Discover, then ask only for what is missing

Read-only. Offer each discovered value as the default; ask one question at a time for the rest.

| key | discover from |
|---|---|
| `project` | AGENTS.md or CLAUDE.md title / `gh repo view --json name` |
| `repo`, `default_branch` | `gh repo view --json nameWithOwner,defaultBranchRef` |
| `status_file` | `claude-work/STATUS.md` (convention) |
| `loop_doc` | `docs/LOOP.md` if it exists |
| `notify` | a `scripts/notify-*.sh`; written with its `./` prefix; absent → ask, allow empty |
| `mention` | an existing `<@digits>` in LOOP.md / STATUS.md; else ask (may be empty) |
| `bot_user` | `AGENT_BOT_USER` in `.sandbox-pal-dispatch/config.defaults.env` and any explicit `config.env` override (read assignments, never source files or print secrets), else `gh api user -q .login`; say which identity runs `gh` in the loop |
| `board` | `gh project list --owner <org> --format json` → pick by name; **object** `{"org","number","done":"Done"}`, or `null` |
| `pipeline` | `sandbox-pal` if `.sandbox-pal-dispatch/` exists |
| `agent_branch_prefix`, `cleanup_pr_prefix` | defaults `agent/issue-`, `chore: post-merge cleanup` |

## 2. `claude-work/loop.json` — the schema is this skill's, not the project's

```json
{
  "project": "…", "repo": "owner/name", "default_branch": "main",
  "status_file": "claude-work/STATUS.md", "loop_doc": "docs/LOOP.md",
  "notify": "./scripts/notify-discord.sh", "mention": "<@…>", "bot_user": "…",
  "board": {"org": "…", "number": 1, "done": "Done"},
  "pipeline": "sandbox-pal",
  "agent_branch_prefix": "agent/issue-", "cleanup_pr_prefix": "chore: post-merge cleanup"
}
```

Optional `start_blocks` maps client/mode to exact headings in loop_doc, as specified in the
runtime contract. Preserve unknown keys and all legacy paths. Ask which runtime/mode the
project needs; setup does not prove scheduler availability. For Codex bounded mode, propose
a separate committed heading and verbatim one-iteration command that preserves every project
gate. Never translate or replace an existing Claude block. Existing project policy that
requires Claude tools needs an explicit reviewed doc migration before Codex start.

For explicitly selected supervised mode, read
[the supervisor guide](../loop-start/references/codex-supervisor.md), propose additive
`codex_supervisor`/`start_blocks` config and the two sections from
`templates/CODEX-SUPERVISOR.md`. Review timer-policy compatibility before committing. Do not
install services, change authentication or launch the loop as part of setup. Explain that
host process management is separate and a controlled pilot is still needed.

Existing file: never overwrite a key silently — show the diff per key and ask. Validate with
`jq .` before committing.

## 3. `docs/LOOP.md`

- Absent → render `templates/LOOP.md`, substituting `{{project}} {{repo}} {{default_branch}}
  {{status_file}} {{loop_doc}} {{notify}} {{mention}} {{bot_user}} {{channel}} {{human}}
  {{board_url}} {{pipeline}}`. Leave the `PROJECT-OWNED` comments for the project to fill.
- Present → if no `## Starting the loop` heading, append the template's "Starting the loop"
  section (heading, the fenced `/loop` block, the two closing sentences) before `## Ground
  rules` if that heading exists, else at the end. **Never edit other sections.** Adding a client
  block to an existing document requires an explicitly selected setup migration, with its diff
  shown before changing the existing config. Project-specific
  clauses may be added inside the fenced block after the template text, each one a sentence.

## 4. `claude-work/STATUS.md`

Absent → render `templates/STATUS.md` (`{{date}}` = UTC now). Present → untouched, even if it
looks stale; say so.

## 5. `.gitignore`, commit, hand-off

- Append `claude-work/.loop-owner` to `.gitignore` if missing.
- One commit on `default_branch`: `docs: loop setup — loop.json, STATUS.md, LOOP.md start block`.
  Push only if the tree was clean before you started and no CI run on `default_branch` is in
  progress; otherwise leave it committed and say so.
- Print: what was written, the suggestions you did not make, and `next: /loop-start`.

## Rationalisations that mean you left the four-file scope

| thought | reality |
|---|---|
| "CLAUDE.md should point at STATUS too" | Suggest it. Setup writes four things. |
| "the old hand-off doc will compete with the dashboard" | Suggest a one-line banner. Don't edit it. |
| "the board is easier as a URL" | The other skills read `{org, number, done}`. Schema is fixed. |
| "the start block reads better rewritten for this project" | Template block first, project clauses appended. Same contract everywhere. |
