"""Native pause invariants against a fake RPC peer; no Goals or services started."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/loop-start/scripts'
sys.path.insert(0, str(SCRIPTS))
import native_goal


class Peer:
    def __init__(self, state='active'):
        self.goal = dict(threadId='session', objective='Deliver the approved work.',
                         status=state, createdAt=10, updatedAt=20, tokensUsed=123,
                         timeUsedSeconds=45, tokenBudget=1000)
        self.calls = []
        self.fail_set = False
        self.ignore_set = False
        self.revert_read = False
        self.reset_usage = False
        self.changed_budget = False

    def call(self, method, params):
        self.calls.append((method, copy.deepcopy(params)))
        if method == 'thread/goal/set':
            if self.fail_set:
                raise native_goal.NativeError('rejected')
            if not self.ignore_set:
                self.goal['status'] = params['status']
            if self.reset_usage:
                self.goal['tokensUsed'] = 0
            if self.changed_budget:
                self.goal['tokenBudget'] = None
        if method == 'thread/goal/get' and len(self.calls) > 2 and self.revert_read:
            self.goal['status'] = 'active'
        return {'goal': copy.deepcopy(self.goal)}


class NativePause(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / '.loop-owner'
        self.peer = Peer()
        self.record = dict(token='token', session='session', client='codex', mode='goal',
                           runtime='codex-goal', goal={'state': 'active',
                           'objective_sha256': hashlib.sha256(
                               self.peer.goal['objective'].encode()).hexdigest()})
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.record))

    def run_control(self, operation='pause', **kw):
        return native_goal.control(self.path, kw.get('token', 'token'),
                                   kw.get('session', 'session'), operation, self.peer,
                                   kw.get('current_session', 'session'))

    def test_pause_only_changes_status_and_preserves_owner(self):
        before = self.path.read_bytes()
        result = self.run_control()
        self.assertEqual(result['state'], 'paused')
        self.assertTrue(result['changed'])
        self.assertFalse(result['workers_reconciled'])
        self.assertEqual(self.peer.calls, [
            ('thread/goal/get', {'threadId': 'session'}),
            ('thread/goal/set', {'threadId': 'session', 'status': 'paused'}),
            ('thread/goal/get', {'threadId': 'session'})])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.peer.goal['tokensUsed'], 123)
        self.assertEqual(self.peer.goal['tokenBudget'], 1000)

    def test_inspection_never_writes_and_paused_is_idempotent(self):
        for operation, state in [('inspect', 'active'), ('pause', 'paused'),
                                  ('pause', 'complete'), ('pause', 'blocked')]:
            with self.subTest(operation=operation, state=state):
                self.peer = Peer(state)
                result = self.run_control(operation)
                self.assertEqual(result['state'], state)
                self.assertFalse(result['changed'])
                self.assertTrue(all(m == 'thread/goal/get' for m, _ in self.peer.calls))

    def test_limited_goals_can_be_paused_without_budget_change(self):
        for state in ['budgetLimited', 'usageLimited']:
            self.peer = Peer(state)
            result = self.run_control()
            self.assertEqual(result['state'], 'paused')
            self.assertEqual(self.peer.goal['tokenBudget'], 1000)

    def test_foreign_owner_or_session_cannot_mutate(self):
        for kwargs in [{'token': 'stale'}, {'session': 'other'},
                       {'current_session': 'other'}]:
            with self.subTest(kwargs=kwargs):
                self.peer.calls.clear()
                with self.assertRaises(native_goal.NativeError):
                    self.run_control(**kwargs)
                self.assertEqual(self.peer.calls, [])
        self.record['runtime'] = 'claude'
        self.save()
        with self.assertRaises(native_goal.NativeError):
            self.run_control()
        self.assertEqual(self.peer.calls, [])

    def test_missing_owner_does_not_adopt_goal(self):
        self.path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_control()
        self.assertFalse(self.path.exists())
        self.assertEqual(self.peer.calls, [])

    def test_wrong_objective_thread_unknown_state_or_missing_goal_never_sets(self):
        for change in [{'objective': 'another task'}, {'threadId': 'foreign'},
                       {'status': 'unknown'}]:
            self.peer = Peer()
            self.peer.goal.update(change)
            with self.assertRaises(native_goal.NativeError):
                self.run_control()
            self.assertFalse(any(m == 'thread/goal/set' for m, _ in self.peer.calls))
        with self.assertRaises(native_goal.NativeError):
            native_goal.validate_goal(None, self.record)

    def test_rejected_unconfirmed_or_history_reset_retains_owner(self):
        before = self.path.read_bytes()
        for flag in ['fail_set', 'ignore_set', 'revert_read', 'reset_usage', 'changed_budget']:
            with self.subTest(flag=flag):
                self.peer = Peer()
                setattr(self.peer, flag, True)
                with self.assertRaises(native_goal.NativeError):
                    self.run_control()
                self.assertEqual(self.path.read_bytes(), before)
                self.assertLessEqual(sum(m == 'thread/goal/set' for m, _ in self.peer.calls), 1)

    def test_owner_changed_after_read_refuses_set(self):
        call = self.peer.call
        def change_owner(method, params):
            result = call(method, params)
            self.record['token'] = 'replacement'
            self.save()
            return result
        with patch.object(self.peer, 'call', side_effect=change_owner):
            with self.assertRaises(native_goal.NativeError):
                self.run_control()
        self.assertEqual([m for m, _ in self.peer.calls], ['thread/goal/get'])

    def test_stdio_protocol_pause_and_cleanup_without_starting_a_real_goal(self):
        executable = self.path.parent / 'fake-codex'
        program = """#!/usr/bin/env python3
import json,sys
g = GOAL
for line in sys.stdin:
    msg = json.loads(line)
    if 'id' not in msg:
        continue
    method = msg['method']
    assert method in ['initialize', 'thread/goal/get', 'thread/goal/set']
    if method == 'thread/goal/set':
        assert msg['params'] == {'threadId':'session','status':'paused'}
        g['status'] = 'paused'
    result = {} if method == 'initialize' else {'goal':g}
    print(json.dumps({'method':'thread/goal/updated','params':{}}), flush=True)
    print(json.dumps({'id':msg['id'],'result':result}), flush=True)
""".replace('GOAL', repr(self.peer.goal))
        executable.write_text(program)
        executable.chmod(0o700)
        rpc = native_goal.AppServer(str(executable), timeout=2)
        try:
            result = native_goal.control(self.path, 'token', 'session', 'pause', rpc)
            self.assertEqual(result['state'], 'paused')
            self.assertTrue(result['changed'])
        finally:
            rpc.close()
        self.assertIsNotNone(rpc.process.poll())
        self.assertTrue(self.path.exists())

    def test_competing_linked_owner_refuses_rpc(self):
        peer_path = self.path.parent / 'linked-owner'
        peer_path.write_text('{}')
        from contextlib import contextmanager
        @contextmanager
        def fake_lock(path):
            yield [self.path, peer_path]
        with patch.object(native_goal.owner, 'locked', fake_lock):
            with self.assertRaises(native_goal.NativeError):
                self.run_control()
        self.assertEqual(self.peer.calls, [])


if __name__ == '__main__':
    unittest.main()
