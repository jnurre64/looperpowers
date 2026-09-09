#!/usr/bin/env python3
"""Inspect or pause the owned native Codex Goal through its documented app-server API.

No thread start/resume, turn execution, database editing, service or owner release.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import subprocess
import time

import owner


class NativeError(RuntimeError):
    pass


class AppServer:
    """A short-lived control-only stdio connection to the installed Codex binary."""
    def __init__(self, binary='codex', timeout=15):
        self.timeout = timeout
        self.sequence = 0
        self.buffer = b''
        self.process = subprocess.Popen(
            [binary, 'app-server', '--stdio'], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        try:
            self.call('initialize', {
                'clientInfo': {'name': 'looperpowers_goal_control', 'version': '1'},
                'capabilities': {'experimentalApi': True}})
            self.send({'method': 'initialized', 'params': {}})
        except Exception:
            self.close()
            raise

    def send(self, message):
        self.process.stdin.write(json.dumps(message).encode() + b'\n')
        self.process.stdin.flush()

    def call(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        self.send({'id': request_id, 'method': method, 'params': params})
        deadline = time.monotonic() + self.timeout
        while True:
            while b'\n' not in self.buffer:
                left = deadline - time.monotonic()
                if left <= 0 or not self.selector.select(left):
                    raise NativeError('native request timed out; inspect before retrying')
                chunk = os.read(self.process.stdout.fileno(), 65536)
                if not chunk:
                    raise NativeError('native server disconnected; inspect before retrying')
                self.buffer += chunk
                if len(self.buffer) > 4 * 1024 * 1024:
                    raise NativeError('native response exceeded control-message limit')
            line, self.buffer = self.buffer.split(b'\n', 1)
            message = json.loads(line)
            if message.get('id') == request_id:
                if 'error' in message:
                    # Do not print arbitrary native error bodies or unrelated notifications.
                    raise NativeError('native RPC rejected: ' + method)
                if 'result' not in message:
                    raise NativeError('native RPC omitted its result')
                return message['result']
            if time.monotonic() >= deadline:
                raise NativeError('native request timed out; inspect before retrying')

    def close(self):
        self.selector.close()
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.terminate()  # Only this helper's control process.
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self.process.stdout.close()


def validate_owner(path, token, session):
    record = json.loads(path.read_text())
    if (not token or record.get('token') != token
            or record.get('client') != 'codex' or record.get('mode') != 'goal'
            or record.get('runtime') != 'codex-goal'
            or record.get('session') != session):
        raise NativeError('owner token, client, runtime or session mismatch')
    if not record.get('goal', {}).get('objective_sha256'):
        raise NativeError('native owner is unbound; reconcile first')
    return record


def validate_goal(goal, record):
    if not isinstance(goal, dict) or goal.get('threadId') != record['session']:
        raise NativeError('native Goal missing or session mismatch')
    objective = goal.get('objective')
    if (not isinstance(objective, str)
            or hashlib.sha256(objective.encode()).hexdigest()
            != record['goal']['objective_sha256']):
        raise NativeError('native objective differs from bound owner')
    if goal.get('status') not in {
            'active', 'paused', 'complete', 'blocked', 'budgetLimited', 'usageLimited'}:
        raise NativeError('native Goal state is unknown')
    return goal


def preserved(before, after):
    for field in ('threadId', 'objective', 'createdAt', 'tokenBudget'):
        if before.get(field) != after.get(field):
            raise NativeError('native pause changed Goal identity or budget')
    for field in ('tokensUsed', 'timeUsedSeconds'):
        if not isinstance(after.get(field), int) or after[field] < before.get(field, 0):
            raise NativeError('native usage history was not preserved')


def control(path, token, session, operation, rpc, current_session=None):
    if current_session and current_session != session:
        raise NativeError('current Codex session differs from requested owner')
    # Serialize with linked-worktree acquire/release for the entire read/set/read.
    # The helper never writes or releases ownership metadata.
    with owner.locked(path) as peers:
        record = validate_owner(path, token, session)
        if any(p.resolve() != path.resolve() and os.path.lexists(p) for p in peers):
            raise NativeError('competing linked-worktree owner; reconcile first')
        before = validate_goal(rpc.call('thread/goal/get', {'threadId': session}).get('goal'),
                               record)
        state = before['status']
        changed = False
        if operation == 'pause' and state in {'active', 'budgetLimited', 'usageLimited'}:
            validate_owner(path, token, session)
            result = rpc.call('thread/goal/set', {'threadId': session, 'status': 'paused'})
            after = validate_goal(result.get('goal'), record)
            preserved(before, after)
            if after['status'] != 'paused':
                raise NativeError('native pause response is not paused')
            changed = True
        # A separate native read is mandatory, including for already-paused Goals.
        after = validate_goal(rpc.call('thread/goal/get', {'threadId': session}).get('goal'),
                              record)
        validate_owner(path, token, session)
        preserved(before, after)
        if operation == 'pause' and (changed or state == 'paused') and after['status'] != 'paused':
            raise NativeError('native pause not confirmed; retain ownership')
        return dict(state=after['status'], session=session, changed=changed,
                    objective_sha256=record['goal']['objective_sha256'],
                    native_confirmation=True, ownership_retained=True,
                    workers_reconciled=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['inspect', 'pause'])
    parser.add_argument('--owner', type=Path, default=Path('claude-work/.loop-owner'))
    parser.add_argument('--session', required=True)
    parser.add_argument('--token', required=True)
    parser.add_argument('--codex-bin', default='codex')
    args = parser.parse_args()
    rpc = None
    try:
        # Refuse wrong ownership/session before even launching the control process.
        current_session = os.environ.get('CODEX_THREAD_ID')
        if current_session and current_session != args.session:
            raise NativeError('current Codex session differs from requested owner')
        validate_owner(args.owner, args.token, args.session)
        rpc = AppServer(args.codex_bin)
        print(json.dumps(control(args.owner, args.token, args.session,
                                 args.operation, rpc, current_session)))
    except (OSError, ValueError, KeyError, TypeError, NativeError) as error:
        parser.exit(1, 'Native Goal control unconfirmed; retain ownership. '
                    + str(error) + '\n')
    finally:
        if rpc is not None:
            rpc.close()


if __name__ == '__main__':
    main()
