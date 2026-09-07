"""Process-level tests: real supervisor/git/locks, fake Codex/GitHub/notifications."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/loop-start/scripts/supervisor.py'
FAKES = ROOT / 'tests/fakes'


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='supervisor test ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'checkout'
        self.repo.mkdir()
        self.env = dict(os.environ, FAKE_RUNTIME=str(self.base), PATH=str(FAKES) + os.pathsep + os.environ['PATH'])
        self.scenario({})
        self.git('init', '-b', 'main')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Test')
        subprocess.run(['git', 'init', '--bare', str(self.base / 'origin.git')], check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(self.base / 'origin.git'))
        (self.repo / 'claude-work').mkdir()
        self.config = {'project': 'fixture', 'default_branch': 'main', 'bot_user': 'test-bot',
            'notify': str(FAKES / 'notify'), 'loop_doc': 'LOOP.md', 'status_file': 'STATUS.md',
            'start_blocks': {'codex': {'supervised': 'Iteration', 'supervised_pause': 'Pause'}},
            'codex_supervisor': {'scheduling': 'timer', 'interval_seconds': 1,
                                 'iteration_timeout_seconds': 2, 'notification_timeout_seconds': 1, 'max_iterations': 2}}
        self.write_config()
        (self.repo / '.gitignore').write_text('claude-work/.loop-owner\n')
        (self.repo / 'LOOP.md').write_bytes(b'## Iteration\r\n```text\r\nExact iteration.\r\n```\r\n## Pause\n```\nExact pause.\n```\n')
        (self.repo / 'STATUS.md').write_text('# loop STOPPED (fixture)\n')
        self.commit()
        self.report = self.base / 'report.json'
        self.report.write_text(json.dumps({'client': 'codex', 'mode': 'supervised',
                                          'scheduler_quiescent': True, 'dispatch_reconciled': True}))
        self.owner = self.repo / 'claude-work/.loop-owner'
        self.args = [sys.executable, str(SCRIPT), 'run', '--report', str(self.report), '--codex', str(FAKES / 'codex')]

    def scenario(self, values):
        (self.base / 'scenario.json').write_text(json.dumps(values))

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout.strip()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-m', 'fixture')
        self.git('push', '-u', 'origin', 'main')

    def write_config(self):
        (self.repo / 'claude-work/loop.json').write_text(json.dumps(self.config))

    def run_supervisor(self):
        return subprocess.run(self.args, cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=12)

    def control(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.repo, env=self.env,
                              capture_output=True, text=True, timeout=3)

    def trace(self):
        path = self.base / 'trace.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def background(self):
        process = subprocess.Popen(self.args, cwd=self.repo, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.wait()
        self.addCleanup(cleanup)
        return process

    def wait_phase(self, phase):
        path = self.repo / '.git/looperpowers/state.json'
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if path.exists() and json.loads(path.read_text())['phase'] == phase:
                return json.loads(path.read_text())
            time.sleep(.02)
        self.fail('phase not reached: ' + phase)

    def test_human_wait_stops_without_second_iteration_and_preserves_prompt(self):
        result = self.run_supervisor()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([entry['phase'] for entry in self.trace()], ['iteration', 'pause'])
        self.assertEqual(self.trace()[0]['prompt'], 'Exact iteration.\r\n')
        self.assertIn('workspace-write', self.trace()[0]['args'])
        self.assertFalse(self.owner.exists())
        self.assertFalse(json.loads(self.control('inspect').stdout)['busy'])

    def test_timer_repeats_only_until_iteration_limit(self):
        self.scenario({'decision': 'wait', 'work_in_flight': True})
        result = self.run_supervisor()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([entry['phase'] for entry in self.trace()], ['iteration', 'iteration', 'pause'])

    def test_preflight_blocks_before_notification_or_dispatch(self):
        for failure in ['dirty', 'legacy', 'scheduler', 'policy', 'owner']:
            with self.subTest(failure=failure):
                if failure == 'dirty':
                    (self.repo / 'notes.txt').write_text('untracked')
                elif failure == 'legacy':
                    (self.repo / 'STATUS.md').write_text('# loop PAUSED\n')
                    self.commit()
                elif failure == 'scheduler':
                    self.report.write_text('{}')
                elif failure == 'policy':
                    self.config['codex_supervisor']['scheduling'] = 'events'
                    self.write_config()
                    self.commit()
                else:
                    self.owner.write_text('host=claude\nsession=old\n')
                self.assertNotEqual(self.run_supervisor().returncode, 0)
                self.assertFalse(self.trace())
                self.assertFalse((self.base / 'notifications.jsonl').exists())
                if failure == 'dirty':
                    (self.repo / 'notes.txt').unlink()
                elif failure == 'legacy':
                    (self.repo / 'STATUS.md').write_text('# loop STOPPED\n')
                    self.commit()
                elif failure == 'scheduler':
                    self.report.write_text(json.dumps({'client': 'codex', 'mode': 'supervised', 'scheduler_quiescent': True, 'dispatch_reconciled': True}))
                elif failure == 'policy':
                    self.config['codex_supervisor']['scheduling'] = 'timer'
                    self.write_config()
                    self.commit()

    def test_start_notification_failure_releases_without_invocation(self):
        self.scenario({'notify_failure': 'start'})
        self.assertNotEqual(self.run_supervisor().returncode, 0)
        self.assertFalse(self.owner.exists())
        self.assertFalse(self.trace())

    def test_pause_notification_failure_retains_owner(self):
        self.scenario({'notify_failure': 'pause'})
        self.assertNotEqual(self.run_supervisor().returncode, 0)
        self.assertTrue(self.owner.exists())

    def test_semantic_failure_exit_zero_retains_owner(self):
        self.scenario({'decision': 'failed'})
        self.assertNotEqual(self.run_supervisor().returncode, 0)
        self.assertTrue(self.owner.exists())
        self.assertEqual(len(self.trace()), 1)

    def test_timeout_retains_owner_and_stops_process(self):
        self.scenario({'sleep': 5})
        self.assertNotEqual(self.run_supervisor().returncode, 0)
        self.assertTrue(self.owner.exists())
        self.assertFalse(json.loads(self.control('inspect').stdout)['busy'])

    def test_bad_results_never_schedule_more_work(self):
        for scenario in [{'malformed': True}, {'event_error': True}, {'crash': True},
                         {'decision': 'wait'}, {'replace_owner': True}, {'dirty': True}]:
            with self.subTest(scenario=scenario):
                self.scenario(scenario)
                self.assertNotEqual(self.run_supervisor().returncode, 0)
                self.assertTrue(self.owner.exists())
                self.owner.unlink()
                unexpected = self.repo / 'unexpected.txt'
                if unexpected.exists():
                    unexpected.unlink()

    def test_notification_timeout_kills_descendants_before_release(self):
        self.scenario({'notify_timeout': True})
        self.assertNotEqual(self.run_supervisor().returncode, 0)
        self.assertFalse(self.owner.exists())
        self.assertFalse(self.trace())
        time.sleep(1.2)
        self.assertFalse((self.base / 'survived-notify').exists())

    def test_pause_requires_published_stopped_dashboard(self):
        self.scenario({'bad_pause': True})
        self.assertNotEqual(self.run_supervisor().returncode, 0)
        self.assertTrue(self.owner.exists())

    def test_changed_policy_stops_before_next_iteration(self):
        self.scenario({'policy_change': True, 'decision': 'continue'})
        self.assertNotEqual(self.run_supervisor().returncode, 0)
        self.assertEqual(len(self.trace()), 1)
        self.assertTrue(self.owner.exists())

    def test_stop_during_iteration_is_graceful(self):
        self.scenario({'sleep': 1, 'decision': 'continue'})
        process = self.background()
        state = self.wait_phase('iteration')
        response = self.control('stop', '--token', state['token'])
        self.assertEqual(response.returncode, 0)
        self.assertFalse(json.loads(response.stdout)['stopped'])
        self.assertEqual(process.wait(timeout=5), 0)
        self.assertEqual([entry['phase'] for entry in self.trace()], ['iteration', 'pause'])
        self.assertFalse(self.owner.exists())

    def test_token_checked_stop_and_concurrent_start(self):
        self.scenario({'decision': 'wait', 'work_in_flight': True})
        process = self.background()
        state = self.wait_phase('waiting')
        self.assertTrue(json.loads(self.control('inspect').stdout)['busy'])
        self.assertNotEqual(self.run_supervisor().returncode, 0)
        self.assertNotEqual(self.control('stop', '--token', 'foreign').returncode, 0)
        self.assertEqual(self.control('stop', '--token', state['token']).returncode, 0)
        self.assertEqual(process.wait(timeout=5), 0)
        self.assertFalse(self.owner.exists())
        self.assertEqual([entry['phase'] for entry in self.trace()], ['iteration', 'pause'])

    def test_supervisor_crash_keeps_child_lock_and_owner(self):
        self.scenario({'sleep': 1})
        process = self.background()
        self.wait_phase('iteration')
        deadline = time.monotonic() + 2
        while not self.trace() and time.monotonic() < deadline:
            time.sleep(.02)
        process.kill()
        process.wait()
        self.assertTrue(json.loads(self.control('inspect').stdout)['busy'])
        self.assertTrue(self.owner.exists())
        self.assertNotEqual(self.run_supervisor().returncode, 0)
        time.sleep(1.1)
        self.assertFalse(json.loads(self.control('inspect').stdout)['busy'])
        self.assertTrue(self.owner.exists())


if __name__ == '__main__':
    unittest.main()
