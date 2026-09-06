---
name: loop-start
description: Use when the user asks to start, restart or resume the orchestrator loop ("resume the loop", "start the loop", "kick the loop off again") in a project that has claude-work/loop.json, or when a session is picking up a paused loop.
argument-hint: "[--force]"
user-invocable: true
---

# loop-start

Preflight, then start the loop with the project's own command. **A failed preflight stops
before `/loop` with the exact fix; there is no partial start.**

**REQUIRED BACKGROUND:** the project's `docs/LOOP.md` (path from `loop.json`) defines what
an iteration does and when it stops. This skill only decides whether the loop may start.

## 1. Load the project data

```bash
cat claude-work/loop.json            # missing → stop: "run /loop-setup first"
```
Then read `status_file`. Both are required; nothing is inferred.

## 2. Preflight — every line is a hard stop with its fix

| check | command | on failure |
|---|---|---|
| On `default_branch` | `git branch --show-current` | stop: "checkout `<branch>`" |
| Clean tree | `git status --porcelain` is empty except `claude-work/.loop-owner` | stop: "commit or remove: `<files>`" — an untracked file is NOT "nothing actionable"; the loop commits `status_file` straight to the branch and a stray file will ride along or get lost |
| Up to date | `git fetch` then `git status -sb` shows neither ahead nor behind | behind → `git pull --ff-only`; ahead/diverged → stop |
| Identity | `gh api user -q .login` equals `bot_user` | stop: "gh is `<login>`, loop expects `<bot_user>`" |
| Notify path | `notify` file exists and is executable | stop: "notify script missing" (unset `notify` → note "no notify; posts go to the user only" and continue) |
| Start block | `loop_doc` has a `## Starting the loop` heading followed by a fenced block | stop: "no start block; run /loop-setup" |
| STATUS shape | `status_file` header line contains `STOPPED` | not STOPPED → stop: "STATUS says the loop is RUNNING/PAUSED mid-flight; run /loop-pause from the owning session, or edit STATUS if that session is gone" |
| Single owner | `claude-work/.loop-owner` absent | present → stop and print its host, session, started_at: "another session owns the loop; stop it, or re-run with `--force` to take over". **Only `--force` takes over.** A liveness guess ("probably stale", "timestamps say it stopped") never does |

## 3. Situation

Read `status_file` and show the user one paragraph: the header line, what is in flight, what
is next ready, what a human is awaited for. This is the resume point; the loop's first
iteration acts on it.

## 4. Start

1. Write `claude-work/.loop-owner`: `host=<hostname>`, `session=<session id or "unknown">`,
   `started_at=<UTC ISO>`. Never `git add` it.
2. Post the resume line through `notify`: `▶️ <project> loop resumed · <one-line situation>`.
   If the post fails, stop and say so — a loop whose stop posts cannot land is the failure mode
   this check exists for.
3. Extract the fenced block under `## Starting the loop` in `loop_doc` (the first fenced block
   after that heading) and invoke the `loop` skill with that text **verbatim** — never a
   paraphrase, never an edited copy. Editing the command is a doc edit and a commit, not a
   start-time decision.

## Rationalisations that mean STOP

| thought | reality |
|---|---|
| "the untracked file is just a note, nothing actionable" | It is a dirty tree. Clean it or stop. |
| "the owner file is probably stale, the timestamps prove it" | Only `--force` takes over. Say what the file says and stop. |
| "I'll tweak the /loop text slightly for today" | The block is verbatim. Change the doc, commit, then start. |
| "notify is down but the loop can run" | Stops that cannot post are the known failure. Fix notify first. |
