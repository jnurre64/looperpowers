"""readiness.py is the ONE definition of "ready to loop-start".

Pins the 2026-09-09 failure class: a handoff claimed "ready to restart" from a hand-written
checklist that never looked at the owner file, and a paused record left by a closed runtime
blocked the next start.  These checks run against a real temporary git checkout.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'skills/loop-start/scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


readiness = load('readiness')
owner = load('owner')

DOC = '# Loop\n## Starting the loop\n```\n/loop run one iteration\n```\n## Ground rules\n'
STATUS = '# Project\n## Last updated: today — loop STOPPED (pause)\n'


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'repo'
        self.remote = Path(self.tmp.name) / 'remote.git'
        subprocess.run(['git', 'init', '-q', '--bare', str(self.remote)], check=True)
        subprocess.run(['git', 'init', '-q', '-b', 'main', str(self.root)], check=True)
        self.git('config', 'user.email', 't@example.com')
        self.git('config', 'user.name', 'test')
        (self.root / 'claude-work').mkdir()
        (self.root / 'docs').mkdir()
        (self.root / 'claude-work/loop.json').write_text(json.dumps({
            'project': 'T', 'default_branch': 'main', 'status_file': 'claude-work/STATUS.md',
            'loop_doc': 'docs/LOOP.md', 'notify': None, 'bot_user': 'test-bot',
            'default_modes': {'claude': 'persistent'},
            'start_blocks': {'claude': {'persistent': 'Starting the loop'}}}))
        (self.root / '.gitignore').write_text('claude-work/.loop-owner\n')
        (self.root / 'docs/LOOP.md').write_text(DOC)
        (self.root / 'claude-work/STATUS.md').write_text(STATUS)
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'init')
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('push', '-q', '-u', 'origin', 'main')
        self.env = dict(os.environ, PATH=str(ROOT / 'tests/fakes') + os.pathsep + os.environ['PATH'])

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.root), *args], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def run_checks(self, **kwargs):
        os.environ['PATH'] = self.env['PATH']
        return list(readiness.run_checks(self.root, 'claude', fetch=False, **kwargs))

    def first_failure(self, **kwargs):
        with self.assertRaises(readiness.Failure) as caught:
            self.run_checks(**kwargs)
        return caught.exception

    def test_clean_checkout_passes_every_check_in_order(self):
        checks = [check for _, check, _ in self.run_checks()]
        self.assertEqual(checks, ['branch', 'tree', 'sync', 'identity', 'notify', 'block', 'status', 'owner'])
        self.assertTrue(readiness.pass_line(self.root).startswith('PASS loop-preflight '))

    def test_foreign_owner_record_is_a_hard_stop_with_the_release_fix(self):
        """The 2026-09-09 class: a paused record left by a closed runtime blocks the start."""
        owner.acquire(self.root / 'claude-work/.loop-owner', 'codex', 'goal', 'other-session', 'codex-goal')
        failure = self.first_failure()
        self.assertEqual(failure.check, 'owner')
        self.assertIn('client=codex session=other-session', failure.problem)
        self.assertIn('release', failure.fix)
        self.assertIn('never ask to shut the other client down', failure.fix)
        # Even the same client is foreign when the session differs.
        self.assertEqual(self.first_failure(session='another').check, 'owner')

    def test_own_owner_record_is_accepted(self):
        owner.acquire(self.root / 'claude-work/.loop-owner', 'claude', 'persistent', 'me', 'claude-code-loop')
        checks = dict((check, detail) for _, check, detail in self.run_checks(session='me'))
        self.assertIn('held by this session', checks['owner'])

    def test_untracked_file_is_a_dirty_tree_not_nothing_actionable(self):
        (self.root / 'note.txt').write_text('just a note\n')
        failure = self.first_failure()
        self.assertEqual(failure.check, 'tree')
        self.assertIn('note.txt', failure.fix)

    def test_ready_claim_without_stopped_header_fails(self):
        (self.root / 'claude-work/STATUS.md').write_text('# Project\n## Last updated: loop PAUSED, ready\n')
        self.git('commit', '-q', '-am', 'paused')
        self.git('push', '-q')
        self.assertEqual(self.first_failure().check, 'status')

    def test_ahead_of_origin_fails_sync(self):
        (self.root / 'docs/LOOP.md').write_text(DOC + '\nmore\n')
        self.git('commit', '-q', '-am', 'local only')
        self.assertEqual(self.first_failure().check, 'sync')

    def test_wrong_identity_fails(self):
        cfg = json.loads((self.root / 'claude-work/loop.json').read_text())
        cfg['bot_user'] = 'someone-else'
        (self.root / 'claude-work/loop.json').write_text(json.dumps(cfg))
        self.git('commit', '-q', '-am', 'identity')
        self.git('push', '-q')
        failure = self.first_failure()
        self.assertEqual(failure.check, 'identity')
        self.assertIn('test-bot', failure.problem)

    def test_cli_prints_pass_line_and_exit_codes(self):
        result = subprocess.run(
            ['python3', str(ROOT / 'skills/loop-start/scripts/readiness.py'), '--client', 'claude',
             '--no-fetch', '--root', str(self.root)], capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.strip().splitlines()[-1].startswith('PASS loop-preflight '))
        owner.acquire(self.root / 'claude-work/.loop-owner', 'codex', 'goal', 'other', 'codex-goal')
        result = subprocess.run(
            ['python3', str(ROOT / 'skills/loop-start/scripts/readiness.py'), '--client', 'claude',
             '--no-fetch', '--root', str(self.root)], capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, 1)
        self.assertIn('FAIL [owner]', result.stdout)


if __name__ == '__main__':
    unittest.main()
