---
name: loop-start
description: Use when the user asks to start, restart or resume the orchestrator loop ("resume the loop", "start the loop", "kick the loop off again") in a project that has claude-work/loop.json, or when a session is picking up a paused loop.
---

# loop-start

Usage: `loop-start [--force] [--mode persistent|bounded|supervised]`.

Preflight, then start the loop with the project's own command. **A failed preflight stops
before `/loop` with the exact fix; there is no partial start.**

**REQUIRED BACKGROUND:** the project's `docs/LOOP.md` (path from `loop.json`) defines what
an iteration does and when it stops. This skill only decides whether the loop may start.

Read [the shared runtime contract](references/runtime.md) first. It defines client/mode
selection, scheduler preflight, verbatim command selection and recovery. Resolve helpers
from this installed skill folder, following symlinks.

## 1. Load the project data

```bash
cat claude-work/loop.json            # missing → stop: "run /loop-setup first"
```
Then read `status_file`. Both are required; nothing is inferred.

For explicitly selected `supervised` mode, read [the Codex supervisor guide](references/codex-supervisor.md).
Use its run/inspect/stop workflow instead of steps 2–4 below: the executable performs its own
preflight, acquisition and lifecycle notifications. Do not pre-acquire an owner or wrap its
iteration in another loop. Review project timer policy and fresh external-runtime/worker
reconciliation first; then launch via the user's selected host process manager. A chat's
background process is not verified durable hosting. Never install/start a service merely
because this skill was installed.

## 2. Preflight — every line is a hard stop with its fix

| check | command | on failure |
|---|---|---|
| On `default_branch` | `git branch --show-current` | stop: "checkout `<branch>`" |
| Clean tree | `git status --porcelain` is empty except `claude-work/.loop-owner` | stop: "commit or remove: `<files>`" — an untracked file is NOT "nothing actionable"; the loop commits `status_file` straight to the branch and a stray file will ride along or get lost |
| Up to date | `git fetch` then `git status -sb` shows neither ahead nor behind | behind → `git pull --ff-only`; ahead/diverged → stop |
| Identity | `gh api user -q .login` equals `bot_user` | stop: "gh is `<login>`, loop expects `<bot_user>`" |
| Notify path | `notify` file exists and is executable | stop: "notify script missing" (unset `notify` → note "no notify; posts go to the user only" and continue) |
| Runtime | Verify the selected client/mode capabilities and reconcile scheduler/dispatch state per the runtime contract | missing or unknown → stop before ownership or notification; bounded mode requires explicit selection |
| Start block | Select the client/mode heading per the runtime contract; validate its complete fenced block and all project gates | stop: "no start block; run /loop-setup" |
| STATUS shape | `status_file` header line contains `STOPPED` | not STOPPED → pause/reconcile first; PAUSED is legacy, not proof of an active worker. Never fix only the header |
| Single owner | Inspect owner AND scheduler state | existing/legacy/unknown state → stop; `--force` requires verified prior-runtime shutdown and reconciliation before token-checked release and atomic acquisition |

After read-only capability inspection, write a temporary JSON report outside the checkout
using the schema in the runtime contract. Run
`python3 <skill-dir>/scripts/preflight.py --client <client> --mode <mode> --report <temp-report>`.
It validates the snapshot and emits the selected block verbatim. Preserve that output without
shell command substitution (which strips trailing newlines). This supplements every check
above; it does not perform identity checks or certify an adapter from its own declarations.

## 3. Situation

Read `status_file` and show the user one paragraph: the header line, what is in flight, what
is next ready, what a human is awaited for. This is the resume point; the loop's first
iteration acts on it.

## 4. Start

1. After every preflight passes, acquire ownership with
   `python3 <skill-dir>/scripts/owner.py acquire --client <client> --mode <mode> --session <id> --runtime <runtime>`.
   Keep its token; never git add the owner. Acquisition failure stops the start.
2. Post through `notify`: `▶️ <project> loop resumed · <mode> · <one-line situation>`.
   If it fails, do not schedule or dispatch. Follow verified shutdown and token-checked
   release in the runtime contract; report the failure locally.
3. Invoke the selected project block **verbatim** through the verified runtime. Legacy
   blocks invoke Claude's `loop` skill only. A changed command requires a project doc edit
   and commit, never a start-time rewrite. Record owned task handles and validate the token
   before every iteration or external mutation.
4. Bounded mode performs one iteration, then follows `loop-pause` to publish the dashboard,
   notify and release ownership. Say explicitly that no future wakeup is armed. Any partial
   start failure requires stop/inspect; retain ownership if shutdown is uncertain.

## Rationalisations that mean STOP

| thought | reality |
|---|---|
| "the untracked file is just a note, nothing actionable" | It is a dirty tree. Clean it or stop. |
| "the owner file is probably stale, the timestamps prove it" | `--force` still requires verified shutdown of the old runtime. Say what the file says and stop. |
| "I'll tweak the /loop text slightly for today" | The block is verbatim. Change the doc, commit, then start. |
| "notify is down but the loop can run" | Stops that cannot post are the known failure. Fix notify first. |
