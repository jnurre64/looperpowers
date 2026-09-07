# Issue #2: native Goal lifecycle implementation plan

Status: approved and implemented locally. Offline validation covers the helpers and existing
supervisor; live native Goal behavior remains a controlled pilot. No live Goal was created.

Issue: [Support native Codex Goal mode](https://github.com/jnurre64/looperpowers/issues/2).

## Intended experience

Keep exactly three everyday skills: setup, start, pause. For a new Codex setup whose intent
is “keep working until playtesting/design input needs me,” recommend native Goal when the
current client supports it. Save that decision once. Bare start creates/resumes the matching
goal and works across steps; bare pause follows its actual native lifecycle. No timer,
service, automatic checkout migration or arbitrary iteration budget for this use case.

Keep existing saved choices unchanged until the user selects a setup migration. Preserve
Claude's event-driven loop, the timer supervisor and `--once` as explicit alternatives.
Changing the orchestrator runtime does not change the worker engine or project policy.

## Evidence and limitations

Official guidance recommends Goal for sustained work with an outcome, constraints and
verification. It retains existing permissions, and concurrent work should avoid conflicting
writers. It does not establish scheduled execution after the session is unavailable.
[Long-running work](https://learn.chatgpt.com/docs/long-running-work).

A goal should have a coherent, verifiable scope rather than an unbounded list of unrelated
backlog work. Use a project phase/checkpoint and its readiness criteria as the objective.
[Follow a goal](https://learn.chatgpt.com/use-cases/follow-goals).

The documented client controls include `/goal <objective>`, `/goal`, `/goal pause`,
`/goal resume` and `/goal clear`. CLI objective text is limited to 4,000 characters; larger
policy belongs in referenced files. [Developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli).

Read-only local inspection: codex-cli 0.153.4 reports goals stable/enabled. This conversation
exposes create/get/update goal tools, but update supports completion/blocking, not pause or
resume. Tool availability and supported transitions must be checked per session; CLI feature
availability alone does not prove that the assistant can execute every control. Respect the
actual tool's authorization and transition rules, including any conditions for marking blocked.

## 1. Separate common policy from runtime requirements

Make the skill entry points thin routers around one shared project contract:

1. Load project/config and resolve the saved runtime.
2. Inspect actual runtime state, ownership and proposed workspace mutations.
3. Prepare the project outcome and its constraints.
4. Start/resume/pause through the selected runtime's supported operations.
5. Record actual state and the resume point with the project's publication policy.

Common invariants: acceptance and plan/review/merge/playtest gates, dependency safety,
spin guard, accurate dispatcher outcomes, notification policy, preservation of existing work,
permission boundaries and no concurrent conflicting writers.

Runtime-specific concerns: scheduler handles and callbacks; native goal controls; iteration
limits; clean-default-branch requirements caused by a particular publication/dispatcher path.
Do not route Goal through the current scheduler-capability report or supervisor preflight.
Do not weaken those requirements for existing timer/Claude users as a side effect.

Use a small capability-aware reference/helper boundary, not a new plugin system or a second
loop engine. Native tools remain native tool calls from the skill; Python helpers cannot
pretend to create/pause a goal by writing a JSON file.

## 2. Add compatible saved selection

Extend the existing resolver with the Codex-only `goal` value:

```json
"default_modes": {"claude": "persistent", "codex": "goal"},
"start_blocks": {
  "claude": {"persistent": "Starting the loop"},
  "codex": {"goal": "Working toward the next checkpoint (Codex Goal)"}
}
```

This is an additive fragment. Preserve other default/mapping keys and retain `--once` as a
single-iteration override. New setup prefers Goal for sustained interactive work, not for a
request to run later while the session is gone. Existing supervised/bounded defaults are not
silently migrated. Unsupported Goal never silently falls back to either alternative.

Setup prepares the goal section in project LOOP.md, including the outcome scope, readiness
evidence, meaningful stopping conditions and references to project policy. Existing Claude
start blocks remain verbatim. Do not rewrite old scheduling clauses into goal text at start.

The submitted objective is short, project-authored and traceable: use the selected goal
section and explicitly allowed context fields (e.g. current phase/checkpoint). Record the
exact submitted text or digest with the runtime binding. Do not paraphrase away gates.
If the scope cannot be derived from project context, ask one substantive setup question.

## 3. Implement honest native lifecycle semantics

| Observed state/capability | Start/pause behavior |
|---|---|
| No goal; create available | Prepare/check first, reserve ownership, create, verify returned native state, bind ownership to the confirmed goal/session |
| Matching active goal | Continue it; do not create a second goal or request another “continue” |
| Matching paused goal | Reconcile current work; resume with an actual supported control and verify |
| Completed checkpoint goal | Preserve its outcome/evidence; create the next scoped objective when start is requested and the next target is known |
| Unrelated active/paused goal | Explain conflict; do not replace or clear it |
| Goal UI exists, needed tool absent | Provide the exact client command and prepared objective; report pending user control, not started/paused/resumed |
| No supported Goal facility or unknown state | Explain the missing capability and stop dependent actions; offer alternatives only as explicit choices |
| Requested pause | Stop active native work through a supported control; confirm before claiming paused/releasing ownership |

Keep native state separate from project state. For example, native goal may be completed
because its playtest-ready outcome is achieved while the project is awaiting playtesting.
Mark complete only when that actual scoped objective is achieved; never use complete/blocked
as a substitute for an unavailable pause operation. Unresolved work and unexpected blockers
remain visible. Do not manufacture runtime transitions merely to satisfy an abstract interface.

If a tool call fails before creation is confirmed, release a reservation only after proving
that no goal was started. Ambiguous creation/pause/notification failures retain a recovery
record. For command-only hand-offs, do not reserve a permanent owner before the user acts:
the prepared objective must recheck ownership before mutations, and binding follows confirmed
native start. This avoids blocking a project indefinitely with a command nobody ran.

## 4. Make ownership and checkout checks fit interactive work

Keep shared legacy owner detection so Goal cannot take over an existing Claude/supervisor
loop. Extend records to bind runtime, client/session, native goal identity when exposed,
workspace and objective fingerprint. When no goal ID exists, use the verified session plus
objective identity; do not invent an ID. Match both owner and native state for reentrant start.

Retain ownership during a paused goal by default: the same native goal can later resume.
An explicit handoff must establish the previous goal cannot write before releasing/transferring.
Project prompts revalidate ownership before further mutations, including manual native resume.
Unknown owner/runtime state blocks conflicting work, not unrelated read-only inspection.

Existing worktrees use the Git common directory lock and enumerate all local owner files,
but all legacy owner paths and the supervisor lock must be reconciled too. Separate clones
remain a coordination limitation. Do not create a new worktree merely to get Goal started.
Use isolation only when actual writes would conflict or project policy requires it; preserve
uncommitted files, staged state and unpublished commits. No reset/stash/auto-commit/push as a
precondition to native Goal creation.

Classify checks by the intended action: reading/planning, editing, dispatching, merging,
publishing. Require GitHub identity/access when those actions need it. Project-specific
main-branch and publication rules still apply to the actions they govern. If an existing
LOOP.md mandates a rule incompatible with desired interactive operation, propose a narrow
project-policy migration; do not override it silently or weaken substantive acceptance gates.
Setup's own unconditional main-branch commit instruction must also become conditional on
project policy for Goal setup, preserving user changes during configuration.

## 5. Continue useful work; publish a truthful resume point

Goal carries the existing substantive workflow across steps. Routine gates stay with their
assigned project actor: do not turn every plan/merge review into a human permission question,
and do not assume Goal grants permission to mutate GitHub or use a different worker engine.
A blocked dependent issue remains blocked while independent, designed work can continue
within the objective's scope. Do not expand into unrelated phases just to keep the goal busy.

When only human input remains, record exactly what is needed, preserve gate evidence and
failure counts, deliver the configured notification, then use a supported native transition.
If a user control is required, say so and retain an honest pending state. Never poll a human
or create a timer to simulate native continuation. No budget/iteration limit unless requested
or required by the native runtime itself.

For active machine work, use available session completion/wait facilities according to the
project, while continuing independent work. A missing event-wakeup tool is not a reason to
install a timer. If the current runtime cannot wait/continue safely, record the limitation.
Native pause affects this goal only; detached workers and other clients' timers remain separate.

STATUS records native state (including unknown/pending), project checkpoint, in-flight work,
awaited input and workspace preservation/publication status. Update an existing dashboard
without overwriting unrelated content. Do not require publication to main solely to pause a
native goal. Required project notifications/publication failures must be reported, and must
not erase evidence or become a false claim of clean handoff.

## 6. Implementation sequence and validation

1. Resolver/config tests: add goal selection, saved choice, explicit override, --once,
   unsupported-client rejection, and unchanged Claude/supervisor defaults.
2. Separate common checks from runtime-specific preflight; add native lifecycle decision
   helpers with a fake capability/state adapter (no fake “all capabilities true” report).
3. Add `references/codex-goal.md`, a project goal template, and setup/start/pause routing.
   Include partial-capability handoffs and distinct runtime/project state reporting.
4. Extend atomic ownership binding/update helpers and preservation tests for dirty/staged/
   unpublished work, current branch, worktree collisions and notification/runtime failures.
5. Update README/Codex guide to recommend Goal for the ordinary sustained-session use case,
   with timer/bounded kept as explicit alternatives. Keep the three-command interface.
6. Run existing tests plus scenario tests with fake goal controls/dispatcher/notifications.
   Independently exercise the skill workflow in temporary projects. A live pilot is a separate
   controlled validation step, not implied by offline tests or by this planning request.

Required scenarios: new goal, repeated start, matching paused resume, unrelated goal conflict,
completed checkpoint/new scope, missing create/inspect/pause/resume, failed/ambiguous native
calls, paused/manual-resume ownership, foreign Claude/supervisor owner, dirty/staged/unpublished
preservation, failed notifications/publication, blocked dependency with independent ready work,
plan/review/merge/playtest gates, semantic agent:failed at exit 0, human-only wait, permissions
stop and optional --once. Assert operation traces and file preservation, not just prose strings.

## Accepted workflow

The user approved the same three commands and shared status across clients: native Goal for
Codex, existing loop for Claude. Use the issue's default checkpoint policy: continue independent
already-designed work within scope while dependent work awaits human evidence. A project's
explicit immediate-stop checkpoint still governs its objective.

The implementation is a skill adapter with read-only decision and ownership helpers, not a
native Goal API emulator. Native calls and confirmation remain in the owning Codex session.
Offline tests cannot establish model adherence to gates or real native pause behavior.
