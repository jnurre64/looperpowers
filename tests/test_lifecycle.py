"""Offline executable checks for preflight, resource installation and ownership.

Full skill/tool sequencing is covered separately by lifecycle-scenarios.md.
"""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'skills/loop-start/scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


owner = load('owner')
preflight = load('preflight')


class FakeScheduler:
    def __init__(self, mode='bounded'):
        self.report = dict(client='codex', mode=mode, scheduler_quiescent=True,
                           dispatch_reconciled=True, capabilities=dict(inspect=True, stop=True))
        if mode == 'persistent':
            self.report['capabilities'].update(schedule=True, wake_on_completion=True, fallback=True)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.config = {'start_blocks': {'codex': {'bounded': 'Codex', 'persistent': 'Codex'}}}
        self.doc = '# Policy\n## Codex\n```text\nKeep every gate.\n  Exact spacing.\n```\n## Other\n'
        self.scheduler = FakeScheduler()

    def check(self, **kwargs):
        values = dict(config=self.config, document=self.doc, status='# loop STOPPED (pause)',
                      client='codex', mode='bounded', report=self.scheduler.report)
        values.update(kwargs)
        return preflight.check(**values)

    def test_bounded_start_verbatim(self):
        self.assertEqual(self.check(), 'Keep every gate.\n  Exact spacing.\n')

    def test_existing_status_template(self):
        self.assertTrue(self.check(status=(ROOT / 'templates/STATUS.md').read_text()))
        with self.assertRaises(ValueError):
            self.check(status='# Project\n## Last updated: today — loop PAUSED\n## Awaiting (STOPPED)')

    def test_persistent_start(self):
        self.assertTrue(self.check(mode='persistent', report=FakeScheduler('persistent').report))

    def test_missing_scheduler_no_downgrade(self):
        self.scheduler.report['mode'] = 'persistent'
        with self.assertRaisesRegex(ValueError, 'schedule'):
            self.check(mode='persistent')

    def test_dirty_checkout(self):
        with self.assertRaisesRegex(ValueError, 'dirty checkout'):
            self.check(dirty=True)

    def test_legacy_paused_requires_reconciliation(self):
        with self.assertRaisesRegex(ValueError, 'reconciliation'):
            self.check(status='# loop PAUSED')

    def test_unknown_cross_client_scheduler_blocks(self):
        self.scheduler.report['scheduler_quiescent'] = None
        with self.assertRaisesRegex(ValueError, 'unknown'):
            self.check()

    def test_unreconciled_dispatch_blocks(self):
        self.scheduler.report['dispatch_reconciled'] = False
        with self.assertRaisesRegex(ValueError, 'unreconciled'):
            self.check()

    def test_legacy_block_only_claude_persistent(self):
        doc = '## Starting the loop\n```\n/loop exact\n```\n'
        self.assertEqual(preflight.select_block({}, doc, 'claude', 'persistent'), '/loop exact\n')
        with self.assertRaises(ValueError):
            preflight.select_block({}, doc, 'codex', 'bounded')

    def test_invalid_blocks(self):
        for document in ['## Codex\n## Other\n```\nwrong\n```\n',
                         '## Codex\n```\nunclosed', self.doc + self.doc]:
            with self.subTest(document=document), self.assertRaises(ValueError):
                self.check(document=document)

    def test_crlf_tilde_fence_and_heading_inside(self):
        doc = '## Codex\r\n~~~~text\r\n## Codex\r\n```\r\n~~~~\r\n'
        self.assertEqual(self.check(document=doc), '## Codex\r\n```\r\n')


class ModeSelectionTests(unittest.TestCase):
    def test_plain_start_uses_setup_choice_per_client(self):
        config = {'default_modes': {'codex': 'supervised', 'claude': 'persistent'}}
        self.assertEqual(preflight.resolve_mode(config, 'codex'), 'supervised')
        self.assertEqual(preflight.resolve_mode(config, 'claude'), 'persistent')

    def test_once_overrides_without_changing_saved_choice(self):
        config = {'default_modes': {'codex': 'supervised'}}
        self.assertEqual(preflight.resolve_mode(config, 'codex', once=True), 'bounded')
        self.assertEqual(config['default_modes']['codex'], 'supervised')
        self.assertEqual(preflight.resolve_mode(config, 'codex', 'persistent'), 'persistent')

    def test_legacy_claude_preserved_codex_needs_setup(self):
        self.assertEqual(preflight.resolve_mode({}, 'claude'), 'persistent')
        with self.assertRaisesRegex(ValueError, 'loop-setup'):
            preflight.resolve_mode({'start_blocks': {'codex': {'bounded': 'Once'}}}, 'codex')
        self.assertEqual(preflight.resolve_mode({}, 'codex', once=True), 'bounded')

    def test_explicitly_saved_one_off_is_respected(self):
        self.assertEqual(preflight.resolve_mode({'default_modes': {'codex': 'bounded'}}, 'codex'), 'bounded')

    def test_invalid_configuration_and_conflicting_flags_fail(self):
        for config in [{'default_modes': None}, {'default_modes': {'codex': None}},
                       {'default_modes': {'codex': 'typo'}}]:
            with self.subTest(config=config), self.assertRaises(ValueError):
                preflight.resolve_mode(config, 'codex')
        with self.assertRaises(ValueError):
            preflight.resolve_mode({}, 'codex', 'persistent', once=True)
        with self.assertRaises(ValueError):
            preflight.resolve_mode({'default_modes': {'claude': 'supervised'}}, 'claude')

    def test_selected_event_runtime_still_requires_scheduler(self):
        config = {'default_modes': {'codex': 'persistent'},
                  'start_blocks': {'codex': {'persistent': 'Run'}}}
        mode = preflight.resolve_mode(config, 'codex')
        report = FakeScheduler().report
        report['mode'] = mode
        with self.assertRaisesRegex(ValueError, 'schedule'):
            preflight.check(config, '## Run\n```\nrun\n```\n', '# STOPPED', 'codex', mode, report)

    def test_cli_resolves_saved_choice_without_starting_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'claude-work').mkdir()
            config = root / 'claude-work/loop.json'
            config.write_text('{"default_modes":{"codex":"supervised"}}')
            args = ['python3', str(ROOT / 'skills/loop-start/scripts/preflight.py'),
                    '--client', 'codex', '--resolve-mode']
            result = subprocess.run(args, cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'supervised\n')
            self.assertFalse((root / 'claude-work/.loop-owner').exists())
            result = subprocess.run(args + ['--once'], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.stdout, 'bounded\n')


class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / '.loop-owner'

    def claim(self):
        return owner.acquire(self.path, 'codex', 'bounded', 'test', 'fake')

    def test_atomic_competing_clients(self):
        def attempt(_):
            try:
                return self.claim()
            except FileExistsError:
                return None
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_foreign_token_cannot_release(self):
        record = self.claim()
        with self.assertRaises(ValueError):
            owner.release(self.path, token='foreign')
        self.assertTrue(self.path.exists())
        owner.release(self.path, token=record['token'])
        self.assertFalse(self.path.exists())

    def test_legacy_owner_blocks_and_recovery_checks_exact_record(self):
        self.path.write_text('host=claude-host\nsession=old\n')
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        with self.assertRaises(FileExistsError):
            self.claim()
        self.path.write_text('host=changed\n')
        with self.assertRaises(ValueError):
            owner.release(self.path, digest=digest)
        owner.release(self.path, digest=hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertTrue(self.claim()['token'])


class InstallTests(unittest.TestCase):
    def test_both_clients_idempotent_with_resource_resolution_and_conflicts(self):
        with tempfile.TemporaryDirectory(prefix='loop test ') as directory:
            base = Path(directory)
            claude, codex = base / 'claude', base / 'codex'
            env = dict(os.environ, CLAUDE_SKILLS_DIR=str(claude), CODEX_SKILLS_DIR=str(codex))
            codex.mkdir()
            (codex / 'loop-pause').symlink_to(base / 'missing')
            for _ in range(2):
                subprocess.run(['bash', str(ROOT / 'install.sh'), 'all'], env=env,
                               check=True, capture_output=True)
            for dest in [claude, codex]:
                self.assertEqual((dest / 'loop-start').resolve(), ROOT / 'skills/loop-start')
                setup = (dest / 'loop-setup').resolve()
                self.assertTrue((setup / '../../templates/LOOP.md').resolve().is_file())
            self.assertEqual(os.readlink(codex / 'loop-pause'), str(base / 'missing'))

    def test_invalid_client_rejected(self):
        result = subprocess.run(['bash', str(ROOT / 'install.sh'), 'bogus'], capture_output=True)
        self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
