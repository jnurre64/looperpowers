<!-- Optional project-owned sections for explicitly selected timer supervision.
     Render placeholders with loop-setup data; append only during a reviewed migration.
     Do not replace or weaken existing project gates. -->

## Starting the loop (Codex supervised)

```text
Run exactly one {{project}} backlog iteration following {{loop_doc}} and {{status_file}}, using gh as {{bot_user}} for {{repo}} on {{default_branch}}. This project explicitly selects the codex-exec timer runtime: the supervisor handles all wakeups, loop ownership and kickoff/pause notifications. Do not invoke loop-start, loop-pause, /goal or any scheduler, change ownership, or detach local work. Before each external mutation, verify claude-work/.loop-owner token matches LOOPER_OWNER_TOKEN; stop with decision failed if it does not. Preserve all plan, merge, playtest and readiness gates, spin guard, dependency rules, concurrency limits and human stop cases in {{loop_doc}}. Inspect dispatcher semantic outcomes, labels, current-head CI and locks before determining active work; process exit 0 does not establish worker success. Perform immediately available work, update and commit/push {{status_file}} as appropriate, and deliver routine status or required human notifications through {{notify}}. Leave the checkout clean on {{default_branch}} and synced with origin. Return a JSON object with decision, summary and work_in_flight. Use continue for more immediately actionable work, wait only for known machine work in flight, human when only a human action remains, stop for a normal project stop case, or failed for an error, unavailable permission/tool, unknown state or failed notification. Do not poll for human input. Never return success if any required gate or lifecycle step was skipped.
```

## Stopping the loop (Codex supervised)

```text
Finalize the {{project}} dashboard under the existing supervisor owner token LOOPER_OWNER_TOKEN; reason is LOOPER_STOP_REASON. Read {{loop_doc}} and {{status_file}}. Do not invoke loop-start, loop-pause, /goal or any scheduler, acquire/release ownership, or dispatch new work. Verify the owner token before each external mutation. Reconcile PRs, current-head CI, dispatcher semantic outcomes and locks. Settle only already-gated green PRs under the project's merge/playtest rules; never perform a new gate or wait for CI. Record workers and PRs still in flight, preserved failure counts, next ready work and human waits. Publish a truthful STOPPED dashboard (or its existing Last updated header) with reason, commit only intended docs and push to {{default_branch}}, leaving a clean synced checkout. The supervisor sends the final pause notification and releases ownership after verifying the result. Return JSON with decision stopped, summary describing the actual resume point, and work_in_flight indicating actual machine work. If publication, reconciliation or any required action fails or is unknown, return decision failed; never claim a clean pause.
```
