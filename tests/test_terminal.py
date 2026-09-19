"""Offline tests for monotonic native Goal terminal decisions."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/loop-start/scripts'
sys.path.insert(0, str(SCRIPTS))
import terminal


def observation(**changes):
    value = {
        'defined_outcome_reached': True,
        'required_evidence': [
            {'name': 'exact-main CI', 'verified': True},
            {'name': 'Jonny-only delivery', 'verified': True},
        ],
        'pending': [
            {'name': 'documentation PR review', 'required_by_objective': False},
        ],
        'runtime_quiescent': True,
        'checkpoint_saved': True,
        'notification_succeeded': True,
        'closed_for_project': True,
        'proposed_goal_status': 'complete',
    }
    value.update(changes)
    return value


class TerminalDecisions(unittest.TestCase):
    def test_achieved_outcome_completes_with_separate_bookkeeping(self):
        result = terminal.decide(observation())
        self.assertEqual('complete', result['goal_status'])
        self.assertEqual(['documentation PR review'], result['bookkeeping_pending'])
        self.assertTrue(result['release_owner'])

    def test_achieved_outcome_cannot_be_downgraded_to_blocked(self):
        with self.assertRaisesRegex(ValueError, 'monotonic'):
            terminal.decide(observation(proposed_goal_status='blocked'))

    def test_claimed_outcome_rejects_missing_gate_or_required_work(self):
        with self.assertRaisesRegex(ValueError, 'unverified evidence'):
            terminal.decide(observation(required_evidence=[
                {'name': 'delivery', 'verified': False},
            ]))
        with self.assertRaisesRegex(ValueError, 'objective-required pending work'):
            terminal.decide(observation(pending=[
                {'name': 'required release', 'required_by_objective': True},
            ]))

    def test_required_lifecycle_failure_keeps_owner_without_downgrading_goal(self):
        result = terminal.decide(observation(notification_succeeded=False))
        self.assertEqual('complete', result['goal_status'])
        self.assertFalse(result['release_owner'])
        self.assertEqual(['required notification'], result['lifecycle_pending'])

    def test_blocked_requires_impasse_and_native_threshold(self):
        base = observation(
            defined_outcome_reached=False,
            required_evidence=[],
            pending=[],
            proposed_goal_status='blocked',
            closed_for_project=False,
        )
        with self.assertRaisesRegex(ValueError, 'genuine impasse'):
            terminal.decide(base)
        base['genuine_impasse'] = True
        with self.assertRaisesRegex(ValueError, 'repeated-blocker threshold'):
            terminal.decide(base)
        base['blocked_threshold_satisfied'] = True
        result = terminal.decide(base)
        self.assertEqual('blocked', result['goal_status'])
        self.assertFalse(result['release_owner'])

    def test_cli_outputs_decision_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'observation.json'
            path.write_text(json.dumps(observation()))
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / 'terminal.py'), '--observation', str(path)],
                text=True, capture_output=True, check=True)
            self.assertEqual('complete', json.loads(result.stdout)['goal_status'])


if __name__ == '__main__':
    unittest.main()
