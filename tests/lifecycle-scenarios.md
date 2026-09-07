# Lifecycle behavioral walkthrough

Independent evaluation of `loop-start`, `loop-pause`, and the shared runtime contract on
2026-09-07, using skill-creator's forward-testing guidance. The evaluator read these
instructions and selected actions for isolated scenarios without changing the skills.

**These are behavioral walkthroughs, not executable lifecycle runtime integration tests.**
Scheduler inspection, stop, scheduling, dispatch, GitHub, notification, and STATUS publication
were fake actions recorded in temporary fixtures. No live services were contacted and no
actual ten-minute wait occurred. The walkthrough makes the evaluator's decisions inspectable;
it does not prove a client will follow them or an adapter implements the contract.

The real `owner.py` helper was executed to create and release fixture ownership. Fixture
ownership for pause cases was setup state, not a newly started production loop. Assertions
verified absent ownership after missing-scheduler/dirty-start rejection and kickoff-notify
failure, and retained ownership after pause-notify failure and unknown foreign runtime.
The temporary run was `/tmp/looper-lifecycle-forward-weqv67al`, with per-case
`fake-adapter-trace.json` and aggregate `results.json`; the driver was
`/tmp/lifecycle-forward-test.py`. Temporary paths are session-local, not maintained test assets.

| Request and fixture | Expected actions from the skills | Observed evaluator decisions and fixture result |
|---|---|---|
| Start explicitly bounded; clean default branch, STOPPED, valid bounded command, scheduler empty, notify succeeds | Acquire after preflight; notify; invoke unchanged command once; pause and record any dispatched worker; publish, notify, release. No future wakeup. | Selected inspect → acquire → kickoff notify → bounded invocation → one fake worker → stop → worker dashboard → pause notify → release. Real owner file absent afterward. Command selection was a decision, not an executed parser/runtime test. |
| Ordinary pause; owned machinery; one gated/current-head-green PR, one ungated green PR, one gated running PR | Stop/inspect first; merge only gated green; leave remaining PRs; no waits; dashboard, notify, release. | Selected stop/inspect before one fake merge; left ungated and running PRs untouched; published STOPPED and released. Real owner file absent afterward. |
| Pause drain; gated PR still running; wait returns timeout | Stop first; one bounded wait at most 600 seconds; leave PR open on timeout without another polling cycle; publish and release after notification. | Selected one fake 600-second wait returning timeout, no merge or repeated wait, running-CI dashboard, notification, release. Real owner file absent afterward. |
| Pause drain; runtime lacks wait | Stop machinery; report drain unavailable and record in-flight work. | Selected stop/inspect, recorded in-flight work, reported unavailable, retained ownership. No fake wait. Completion/publication behavior is ambiguous; see finding below. |
| Start default persistent in ordinary Codex with no adapter | Stop before ownership/notify/dispatch; offer explicit bounded mode without downgrading. | Selected capability rejection and bounded-mode offer. No owner, notification, dispatch, or scheduling. |
| Start with kickoff notify failure after acquisition | Do not invoke; inspect to verify no tasks; release own token; report locally. | Selected failed notification → empty inspection → token release → local report. Real helper released owner; no fake invocation or dispatch. |
| Pause notification fails after STATUS publication | Keep shutdown in effect and retain ownership; report failed step; recovery retries notification before release. | Selected stopped machinery, published STOPPED, failed pause notification, local retry report. Real owner remains; no success/release action. |
| Start with untracked `notes.txt` | Fail clean-tree preflight with exact file; no acquisition or kickoff. | Selected `commit or remove notes.txt` and stopped. No owner or fake notification/dispatch. |
| Legacy PAUSED, scheduler quiescent, dispatcher exit 0 but `outcome=agent:failed`, no lock and no owner | Reconcile semantic failure as terminal, preserve spin-guard count, record failures/work, publish STOPPED through pause recovery. Do not infer a live worker or merely edit header. | Selected terminal-failure reconciliation and failure-count preservation, full dashboard publication and pause notification; no dispatch or unnecessary wait. Missing ownership was reconciled, with no token release to attempt. |
| Codex start `--force`, owner belongs to Claude session, prior scheduler unknown | Force does not bypass shutdown verification. Keep owner; obtain owning-session/operator-confirmed shutdown before transfer. | Selected read owner → unknown prior runtime → shutdown blocker. No cancellation of local unrelated tasks, no overwrite, no acquire/notify/dispatch. Prior owner remains. |

## Findings for review

1. **Resolved on re-read: pause branch/dirty-tree guard.** The initial walkthrough found
   the branch check after settling/commits. The implementation now checks `default_branch`
   and unrelated dirty changes before settling, keeps ownership on a branch blocker, avoids
   switching over uncommitted work, and stages specific doc files. Reading this revision
   resolves the sequencing concern; this was a behavioral review, not an executed Git test.
2. **Resolved after review: unavailable drain endpoint.** Section 1 and the runtime
   contract say stop machinery, report unavailable, and record in-flight work. They do not
   specify whether to continue a normal no-wait pause through publication/notification/release
   or return while keeping the owner. The evaluator chose conservative retention and made
   no clean-pause claim. The implementation now explicitly completes an ordinary no-wait pause,
   publishing in-flight work, notifying and releasing on success, while reporting drain unavailable.
   This resolution was reviewed as an instruction change; the original trace is preserved above.
3. **Executable coverage is intentionally limited.** This pass did not test scheduler races,
   foreign-runtime shutdown proof, live token validation on callbacks, actual dispatcher
   records, current-head gate checks, publication failures, or extraction/invocation of a
   project block. Adapter integration tests remain necessary before claiming those runtime
   guarantees. There was no observed contradiction in the selected start, notification,
   legacy-outcome, or forced-transfer decisions.

A subsequent concurrency review also tightened missing-owner pause recovery: it now acquires
an atomic recovery token after scheduler reconciliation and before dashboard mutation, then
releases through the usual pause path. The original missing-owner walkthrough above predates
that refinement.
