"""Offline Goal routing/ownership tests. No native Goal or network calls."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/loop-start/scripts'
sys.path.insert(0, str(SCRIPTS))
import goal
import owner
import preflight


class GoalDecisions(unittest.TestCase):
    objective = 'Reach the designed playtest checkpoint.\n'

    def observation(self, state='none', **extra):
        return dict(state=state, session='s1', controls=['create', 'resume'],
                    reconciled=True, objective=self.objective.strip(), **extra)

    def record(self):
        return dict(runtime='codex-goal', token='t1', session='s1', goal={
            'objective_sha256': hashlib.sha256(self.objective.strip().encode()).hexdigest()})

    def test_fenced_newline_matches_exact_native_binding_without_reopening_goal(self):
        result = goal.decide(self.objective, self.observation('paused'), self.record())
        self.assertEqual(result['action'], 'resume')
        self.assertEqual(result['objective_sha256'],
                         hashlib.sha256(self.objective.strip().encode()).hexdigest())
        wrong = self.observation('paused')
        wrong['objective'] += ' different work'
        with self.assertRaises(ValueError):
            goal.decide(self.objective, wrong, self.record())

    def test_new_and_repeated_start(self):
        self.assertEqual(goal.decide(self.objective, self.observation())['action'], 'create')
        result = goal.decide(self.objective, self.observation('active'), self.record())
        self.assertEqual(result['action'], 'continue')
        self.assertFalse(result['started'])

    def test_paused_completed_blocked(self):
        for state, action in [('paused', 'resume'), ('complete', 'checkpoint'),
                              ('blocked', 'reconcile')]:
            self.assertEqual(goal.decide(self.objective, self.observation(state),
                                         self.record())['action'], action)

    def test_command_only_handoff_is_not_start(self):
        for state, command in [('none', '/goal ' + self.objective),
                               ('paused', '/goal resume')]:
            observation = self.observation(state, command_ui=True)
            observation['controls'] = []
            result = goal.decide(self.objective, observation,
                                 self.record() if state == 'paused' else None)
            self.assertEqual(result, dict(action='handoff', command=command, started=False))

    def test_missing_capability_or_inspection_never_downgrades(self):
        for change in [dict(controls=[]), dict(state='unknown'), dict(reconciled=False)]:
            observation = self.observation()
            observation.update(change)
            with self.assertRaises(ValueError):
                goal.decide(self.objective, observation)

    def test_foreign_unbound_or_missing_owner_blocks(self):
        records = [None, dict(runtime='claude', token='foreign'),
                   dict(runtime='codex-goal', session='s1', token='partial'),
                   dict(self.record(), session='other')]
        for record in records:
            with self.assertRaises(ValueError):
                goal.decide(self.objective, self.observation('active'), record)
        with self.assertRaises(ValueError):
            goal.decide('different outcome', self.observation('active'), self.record())
        with self.assertRaises(ValueError):
            goal.decide(self.objective, self.observation(), self.record())

    def test_objective_limits_and_runtime_boundary(self):
        for objective in ['', ' ', 'x' * 4001]:
            with self.assertRaises(ValueError):
                goal.decide(objective, self.observation())
        with self.assertRaises(ValueError):
            preflight.resolve_mode({}, 'claude', 'goal')
        with self.assertRaisesRegex(ValueError, 'runtime guide'):
            preflight.check({}, '', '', 'codex', 'goal', {})
        self.assertEqual(preflight.resolve_mode({}, 'codex'), 'goal')
        self.assertEqual(preflight.resolve_mode({}, 'codex', once=True), 'bounded')


class GoalWorkspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.root.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.root / 'tracked').write_text('initial')
        self.git('add', 'tracked')
        self.git('commit', '-qm', 'initial')
        (self.root / 'claude-work').mkdir()
        self.path = self.root / 'claude-work/.loop-owner'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args],
                                       stderr=subprocess.STDOUT)

    def test_bind_rejects_stale_token_and_keeps_partial_failure_owner(self):
        record = owner.acquire(self.path, 'codex', 'goal', 's1', 'codex-goal')
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            owner.bind_goal(self.path, 'old', 'objective', 'active', 's1')
        self.assertEqual(before, self.path.read_bytes())
        with self.assertRaises(ValueError):
            goal.decide('objective', dict(state='none', reconciled=True, session='s1'), record)
        self.assertTrue(self.path.exists())
        record = owner.bind_goal(self.path, record['token'], 'objective', 'paused', 's1')
        with self.assertRaises(FileExistsError):
            owner.acquire(self.path, 'claude', 'persistent', 's2', 'claude')
        for objective, state, session in [('changed', 'active', 's1'),
                                           ('objective', 'invented', 's1'),
                                           ('objective', 'active', 's2')]:
            with self.assertRaises(ValueError):
                owner.bind_goal(self.path, record['token'], objective, state, session)
        self.assertEqual(json.loads(self.path.read_text())['goal']['state'], 'paused')

    def test_explicit_native_whitespace_binding_repair_preserves_semantics(self):
        record = owner.acquire(self.path, 'codex', 'goal', 's1', 'codex-goal')
        owner.bind_goal(self.path, record['token'], 'outcome\n', 'paused', 's1')
        before = self.path.read_bytes()
        for new, old in [('different', 'outcome\n'), ('outcome', 'wrong source'),
                         ('outcome', None), (' outcome ', 'outcome\n')]:
            with self.assertRaises(ValueError):
                owner.bind_goal(self.path, record['token'], new, 'paused', 's1', old)
            self.assertEqual(self.path.read_bytes(), before)
        bound = owner.bind_goal(self.path, record['token'], 'outcome', 'paused', 's1',
                                'outcome\n')
        self.assertEqual(bound['goal']['objective_sha256'],
                         hashlib.sha256(b'outcome').hexdigest())
        self.assertEqual(bound['token'], record['token'])
        self.assertEqual(bound['session'], 's1')

    def test_terminal_handoff_requires_clear_then_new_owner(self):
        old = owner.acquire(self.path, 'codex', 'goal', 's1', 'codex-goal')
        old = owner.bind_goal(self.path, old['token'], 'old outcome', 'complete', 's1')
        observation = dict(state='complete', session='s1', objective='old outcome',
                           reconciled=True, controls=['create'])
        with self.assertRaises(ValueError):
            goal.decide('next outcome', observation, old)
        # Caller has verified quiescence and persisted checkpoint/notification.
        owner.release(self.path, token=old['token'])
        with self.assertRaises(ValueError):
            goal.decide('next outcome', observation)
        # Fresh native inspection after the authorized clear operation.
        observation.update(state='none', objective=None)
        self.assertEqual(goal.decide('next outcome', observation)['action'], 'create')
        new = owner.acquire(self.path, 'codex', 'goal', 's1', 'codex-goal')
        self.assertNotEqual(old['token'], new['token'])
        new = owner.bind_goal(self.path, new['token'], 'next outcome', 'active', 's1')
        with self.assertRaises(ValueError):
            owner.bind_goal(self.path, old['token'], 'old outcome', 'active', 's1')
        self.assertEqual(json.loads(self.path.read_text()), new)

    def test_missing_owner_pause_can_bind_only_after_recovery_acquisition(self):
        with self.assertRaises(FileNotFoundError):
            owner.bind_goal(self.path, 'missing', 'outcome', 'paused', 's1')
        record = owner.acquire(self.path, 'codex', 'goal', 's1', 'codex-goal')
        bound = owner.bind_goal(self.path, record['token'], 'outcome', 'paused', 's1')
        self.assertEqual(bound['goal']['state'], 'paused')
        self.assertTrue(self.path.exists())

    def test_worktree_inspection_failure_blocks_acquisition(self):
        with patch.object(owner.subprocess, 'check_output', side_effect=[
                str(self.root).encode(),
                subprocess.CalledProcessError(1, 'git')]):
            with self.assertRaises(subprocess.CalledProcessError):
                owner.acquire(self.path, 'codex', 'goal', 's1', 'codex-goal')
        self.assertFalse(self.path.exists())

    def test_linked_worktree_acquisition_race_has_one_winner(self):
        linked = Path(self.temp.name) / 'linked'
        self.git('worktree', 'add', '-qb', 'linked', str(linked))
        (linked / 'claude-work').mkdir()
        paths = [self.path, linked / 'claude-work/.loop-owner']
        def claim(path):
            try:
                return owner.acquire(path, 'codex', 'goal', str(path), 'codex-goal')
            except FileExistsError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, paths))
        self.assertEqual(sum(result is not None for result in results), 1)
        winner = next(path for path in paths if path.exists())
        record = json.loads(winner.read_text())
        owner.release(winner, token=record['token'])
        loser = next(path for path in paths if path != winner)
        self.assertIsNotNone(claim(loser))

    def test_goal_cli_preserves_dirty_staged_unpublished_workspace(self):
        self.git('checkout', '-qb', 'unpublished')
        (self.root / 'tracked').write_text('staged')
        self.git('add', 'tracked')
        (self.root / 'tracked').write_text('unstaged')
        (self.root / 'notes').write_text('user notes')
        (self.root / 'LOOP.md').write_text('## Goal\n```text\nReach checkpoint.\n```\n')
        config = dict(loop_doc='LOOP.md', start_blocks={'codex': {'goal': 'Goal'}})
        (self.root / 'claude-work/loop.json').write_text(json.dumps(config))
        observation = Path(self.temp.name) / 'observation.json'
        observation.write_text(json.dumps(dict(state='none', session='s1',
                                              controls=['create'], reconciled=True)))
        snapshot = (self.git('status', '--porcelain'), self.git('diff'),
                    self.git('diff', '--cached'), self.git('rev-parse', 'HEAD'),
                    self.git('branch', '--show-current'))
        result = subprocess.run([sys.executable, str(SCRIPTS / 'goal.py'),
                                 '--observation', str(observation)], cwd=self.root,
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['action'], 'create')
        self.assertEqual(snapshot, (self.git('status', '--porcelain'), self.git('diff'),
                                   self.git('diff', '--cached'), self.git('rev-parse', 'HEAD'),
                                   self.git('branch', '--show-current')))
        self.assertFalse(self.path.exists())
        self.assertEqual((self.root / 'notes').read_text(), 'user notes')


if __name__ == '__main__':
    unittest.main()
