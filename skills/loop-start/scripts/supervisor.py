#!/usr/bin/env python3
"""Linux/POSIX foreground supervisor for explicitly selected timed Codex iterations."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import owner
import preflight

RUNTIME = 'codex-exec'
SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {'decision': {'type': 'string', 'enum': ['continue', 'wait', 'human', 'stop', 'failed', 'stopped']},
                   'summary': {'type': 'string'}, 'work_in_flight': {'type': 'boolean'}},
    'required': ['decision', 'summary', 'work_in_flight'],
}


def command(args):
    return subprocess.check_output(args, text=True, timeout=30).strip()


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def state_dir():
    return Path(command(['git', 'rev-parse', '--git-common-dir'])).resolve() / 'looperpowers'


def inspect():
    directory = state_dir()
    lock = directory / 'supervisor.lock'
    if not lock.exists():
        return {'busy': False, 'state': None}
    with lock.open('r') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            busy = False
        except BlockingIOError:
            busy = True
        state = directory / 'state.json'
        return {'busy': busy, 'state': json.loads(state.read_text()) if state.exists() else None}


def request_stop(token):
    path = Path('claude-work/.loop-owner')
    with owner.locked(path):
        record = json.loads(path.read_text())
        if record.get('token') != token or record.get('runtime') != RUNTIME:
            raise ValueError('foreign owner; stop through its owning runtime')
        atomic_json(state_dir() / 'stop.json', {'token': token})
    return {'requested': True, 'stopped': False}


class Supervisor:
    def __init__(self, config, report, codex='codex'):
        self.config, self.report, self.codex = config, report, codex
        self.path = Path('claude-work/.loop-owner')
        self.directory = state_dir()
        self.record = None
        self.stop_signal = False
        self.sequence = 0
        self.stop_reason = "stop requested"

    def checkout(self):
        if command(['git', 'branch', '--show-current']) != self.config['default_branch']:
            raise ValueError('checkout default_branch before starting/continuing')
        if command(['git', 'status', '--porcelain']):
            raise ValueError('dirty checkout; reconcile before continuing')
        command(['git', 'fetch', 'origin', self.config['default_branch']])
        if command(['git', 'rev-parse', 'HEAD']) != command(['git', 'rev-parse', 'origin/' + self.config['default_branch']]):
            raise ValueError('checkout must match origin/default_branch')
        if command(['gh', 'api', 'user', '-q', '.login']) != self.config['bot_user']:
            raise ValueError('GitHub identity differs from bot_user')

    def token_check(self):
        if json.loads(self.path.read_text()).get('token') != self.record['token']:
            raise ValueError('owner changed; no further Codex invocations permitted')

    def save(self, phase, **extra):
        atomic_json(self.directory / 'state.json', dict(token=self.record['token'],
                    runtime=RUNTIME, supervisor_pid=os.getpid(), phase=phase,
                    iteration=self.sequence, stop_reason=self.stop_reason, **extra))

    def notify(self, message):
        self.token_check()
        target = self.config.get('notify')
        if target:
            child = subprocess.Popen([str(Path(target).resolve()), message],
                                     start_new_session=True, pass_fds=(self.lock_fd,))
            try:
                child.wait(timeout=self.options['notification_timeout_seconds'])
                if child.returncode:
                    raise ValueError('notification failed')
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        else:
            print(message, flush=True)

    def requested(self):
        request = self.directory / 'stop.json'
        return self.stop_signal or (request.exists() and
                json.loads(request.read_text()).get('token') == self.record['token'])

    def invoke(self, prompt, phase, lock_fd):
        self.token_check()
        if self.policy != (Path('claude-work/loop.json').read_bytes(), Path(self.config['loop_doc']).read_bytes()):
            raise ValueError('project runtime policy changed; reconcile before continuing')
        self.save(phase)
        stem = self.directory / f'{self.record["token"]}-{self.sequence}-{phase}'
        result_path = stem.with_suffix('.result.json')
        schema = self.directory / 'result-schema.json'
        args = [self.codex, 'exec', '--sandbox', 'workspace-write', '--json',
                '--output-schema', str(schema), '-o', str(result_path), '-']
        env = dict(os.environ, LOOPER_OWNER_TOKEN=self.record['token'],
                   LOOPER_PHASE=phase, LOOPER_STOP_REASON=self.stop_reason)
        with stem.with_suffix('.events.jsonl').open('w') as events, stem.with_suffix('.stderr.log').open('w') as errors:
            # The child inherits the lock: if the supervisor crashes, another instance cannot
            # start while that child still holds it. Never identify a process by PID alone.
            child = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=events, stderr=errors,
                                     env=env, start_new_session=True, pass_fds=(lock_fd,))
            try:
                self.save(phase, child_pid=child.pid)
                child.communicate(prompt.encode(), timeout=self.options['iteration_timeout_seconds'])
                if child.returncode:
                    raise ValueError(f'Codex exited {child.returncode}; inspect {stem}')
            finally:
                # Also stop descendants after normal exit. Detached/remote worker engines
                # are reconciled by project policy, never inferred from this process group.
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        self.token_check()
        events = [json.loads(line) for line in stem.with_suffix('.events.jsonl').read_text().splitlines() if line.strip()]
        if any(event.get('type') in ('turn.failed', 'error') for event in events) or not any(event.get('type') == 'turn.completed' for event in events):
            raise ValueError('Codex event stream did not complete successfully')
        result = json.loads(result_path.read_text())
        if (set(result) != set(SCHEMA['required']) or result['decision'] not in SCHEMA['properties']['decision']['enum']
                or not isinstance(result['summary'], str) or type(result['work_in_flight']) is not bool):
            raise ValueError('invalid structured Codex result')
        if result['decision'] == 'failed' or (phase == 'pause') != (result['decision'] == 'stopped'):
            raise ValueError('Codex reported a semantic failure or unexpected lifecycle result')
        if result['decision'] == 'wait' and not result['work_in_flight']:
            raise ValueError('wait without active machine work; refusing idle polling')
        return result

    def validate(self):
        self.policy = (Path('claude-work/loop.json').read_bytes(), Path(self.config['loop_doc']).read_bytes())
        self.options = dict(self.config.get('codex_supervisor', {}))
        if self.options.get('scheduling') != 'timer':
            raise ValueError('commit codex_supervisor.scheduling=timer; event policy is never silently downgraded')
        for key, default in [('interval_seconds', 1200), ('iteration_timeout_seconds', 1800), ('notification_timeout_seconds', 30), ('max_iterations', 100)]:
            value = self.options.get(key, default)
            if type(value) is not int or value < 1:
                raise ValueError(key + ' must be a positive integer')
            self.options[key] = value
        if self.report.get('client') != 'codex' or self.report.get('mode') != 'supervised':
            raise ValueError('fresh codex/supervised reconciliation report required')
        if self.report.get('scheduler_quiescent') is not True or self.report.get('dispatch_reconciled') is not True:
            raise ValueError('prior scheduler/dispatch state must be reconciled before start')
        # This runtime proves its own process lock, timer and stop control. The report is
        # evidence only about external/legacy clients and workers; it cannot enable tools.
        document = Path(self.config['loop_doc']).read_bytes().decode()
        self.prompt = preflight.select_block(self.config, document, 'codex', 'supervised')
        self.pause_prompt = preflight.select_block(self.config, document, 'codex', 'supervised_pause')
        snapshot = dict(self.report, mode='bounded', capabilities={'inspect': True, 'stop': True})
        mapped = dict(self.config, start_blocks={'codex': {'bounded': self.config['start_blocks']['codex']['supervised']}})
        preflight.check(mapped, document, Path(self.config['status_file']).read_text(), 'codex', 'bounded', snapshot)
        self.checkout()
        if self.path.exists():
            raise ValueError('owner exists; explicit verified recovery required, no automatic takeover')
        target = self.config.get('notify')
        if target and not (Path(target).is_file() and os.access(target, os.X_OK)):
            raise ValueError('notify must be an executable file path')
        help_text = command([self.codex, 'exec', '--help'])
        for flag in ['--sandbox', '--json', '--output-schema', '--output-last-message']:
            if flag not in help_text:
                raise ValueError('installed Codex lacks ' + flag)

    def run(self):
        self.directory.mkdir(exist_ok=True)
        with (self.directory / 'supervisor.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd = lock.fileno()
            self.validate()
            self.record = owner.acquire(self.path, 'codex', 'supervised', str(os.getpid()), RUNTIME)
            started = False
            try:
                atomic_json(self.directory / 'result-schema.json', SCHEMA)
                self.save('starting')
                self.notify(f'▶ {self.config["project"]} loop resumed · supervised timer')
                started = True
                for self.sequence in range(1, self.options['max_iterations'] + 1):
                    if self.requested():
                        break
                    self.checkout()
                    result = self.invoke(self.prompt, 'iteration', lock.fileno())
                    self.checkout()
                    if result['decision'] in ('human', 'stop'):
                        self.stop_reason = result['decision'] + ': ' + result['summary']
                        break
                    if self.sequence == self.options['max_iterations']:
                        self.stop_reason = 'iteration limit reached'
                        break
                    self.save('waiting', next_wakeup=time.time() + self.options['interval_seconds'])
                    deadline = time.monotonic() + self.options['interval_seconds']
                    while time.monotonic() < deadline and not self.requested():
                        self.token_check()
                        time.sleep(min(0.2, max(0, deadline - time.monotonic())))
                result = self.invoke(self.pause_prompt, 'pause', lock.fileno())
                self.checkout()
                # Require the actual published dashboard, not just the model's claim.
                status = Path(self.config['status_file']).read_text()
                preflight.require_stopped(status)
                self.notify(f'⏸ {self.config["project"]} loop paused · {result["summary"]}')
                self.save('stopped')
                owner.release(self.path, token=self.record['token'])
            except BaseException as error:
                self.save('recovery-required', error=str(error))
                if started:
                    try:
                        self.notify(f'⛔ {self.config["project"]} loop blocked · recovery required; ownership retained')
                    except (OSError, ValueError, subprocess.SubprocessError):
                        pass  # Original failure is reported locally; never release on notify failure.
                if not started:
                    # No Codex process was started, so kickoff failure can safely release.
                    owner.release(self.path, token=self.record['token'])
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    run = sub.add_parser('run')
    run.add_argument('--report', required=True, type=Path)
    run.add_argument('--codex', default='codex')
    sub.add_parser('inspect')
    stop = sub.add_parser('stop')
    stop.add_argument('--token', required=True)
    args = parser.parse_args()
    try:
        if args.action == 'inspect':
            print(json.dumps(inspect()))
        elif args.action == 'stop':
            print(json.dumps(request_stop(args.token)))
        else:
            runner = Supervisor(json.loads(Path('claude-work/loop.json').read_text()),
                                json.loads(args.report.read_text()), args.codex)
            def stop_signal(signum, frame):
                runner.stop_signal = True
            signal.signal(signal.SIGTERM, stop_signal)
            signal.signal(signal.SIGINT, stop_signal)
            runner.run()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.exit(1, f'Supervisor blocked: {error}\n')


if __name__ == '__main__':
    main()
