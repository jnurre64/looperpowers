#!/usr/bin/env python3
"""Validate a proposed native Goal terminal transition from fresh evidence.

This helper classifies state; it does not inspect a Goal, prove evidence, mutate native
state, publish files, notify anyone, or release ownership.
"""
import argparse
import json
from pathlib import Path


TERMINAL_STATES = ('complete', 'blocked')


def _required_bool(observation, key):
    value = observation.get(key)
    if not isinstance(value, bool):
        raise ValueError(f'{key} must be a boolean')
    return value


def decide(observation):
    if not isinstance(observation, dict):
        raise ValueError('terminal observation must be an object')
    proposed = observation.get('proposed_goal_status')
    if proposed not in TERMINAL_STATES:
        raise ValueError('proposed_goal_status must be complete or blocked')

    reached = _required_bool(observation, 'defined_outcome_reached')
    quiescent = _required_bool(observation, 'runtime_quiescent')
    checkpoint_saved = _required_bool(observation, 'checkpoint_saved')
    notified = _required_bool(observation, 'notification_succeeded')
    closed_for_project = _required_bool(observation, 'closed_for_project')

    evidence = observation.get('required_evidence')
    if not isinstance(evidence, list):
        raise ValueError('required_evidence must be a list')
    pending = observation.get('pending')
    if not isinstance(pending, list):
        raise ValueError('pending must be a list')

    evidence_failures = []
    for item in evidence:
        if (not isinstance(item, dict) or not isinstance(item.get('name'), str)
                or not item['name'].strip() or not isinstance(item.get('verified'), bool)):
            raise ValueError('each required_evidence item needs a name and boolean verified')
        if not item['verified']:
            evidence_failures.append(item['name'])

    required_pending = []
    bookkeeping = []
    for item in pending:
        if (not isinstance(item, dict) or not isinstance(item.get('name'), str)
                or not item['name'].strip()
                or not isinstance(item.get('required_by_objective'), bool)):
            raise ValueError(
                'each pending item needs a name and boolean required_by_objective')
        target = required_pending if item['required_by_objective'] else bookkeeping
        target.append(item['name'])

    if reached:
        if proposed != 'complete':
            raise ValueError(
                'the defined outcome is achieved; it is monotonic and cannot become blocked')
        if not evidence:
            raise ValueError('an achieved outcome needs named required_evidence')
        if evidence_failures:
            raise ValueError(
                'defined_outcome_reached contradicts unverified evidence: '
                + ', '.join(evidence_failures))
        if required_pending:
            raise ValueError(
                'defined_outcome_reached contradicts objective-required pending work: '
                + ', '.join(required_pending))
    elif proposed == 'complete':
        raise ValueError('cannot complete before the defined outcome is achieved')
    else:
        if observation.get('genuine_impasse') is not True:
            raise ValueError('blocked requires a genuine impasse')
        if observation.get('blocked_threshold_satisfied') is not True:
            raise ValueError('blocked requires the native repeated-blocker threshold')

    lifecycle_pending = []
    if not quiescent:
        lifecycle_pending.append('runtime quiescence')
    if not checkpoint_saved:
        lifecycle_pending.append('checkpoint persistence')
    if not notified:
        lifecycle_pending.append('required notification')
    if not closed_for_project:
        lifecycle_pending.append('project Goal closure')

    return {
        'goal_status': proposed,
        'outcome_reached': reached,
        'bookkeeping_pending': bookkeeping,
        'lifecycle_pending': lifecycle_pending,
        'release_owner': not lifecycle_pending,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observation', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(decide(json.loads(args.observation.read_text()))))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(1, f'Goal terminal transition blocked: {error}\n')


if __name__ == '__main__':
    main()
