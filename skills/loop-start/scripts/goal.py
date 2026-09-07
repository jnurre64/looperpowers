#!/usr/bin/env python3
"""Read-only Goal routing from fresh native inspection; this is not a Goal API.

The caller supplies observed state and available controls, never guessed capabilities.
Output is the next required action, not evidence that the action succeeded.
"""
import argparse
import hashlib
import json
from pathlib import Path
from preflight import select_block


def decide(objective, observation, owner=None):
    if not objective.strip() or len(objective) > 4000:
        raise ValueError('goal objective must contain 1–4000 characters')
    if observation.get('reconciled') is not True:
        raise ValueError('prior runtimes and workers must be reconciled')
    state = observation.get('state')
    if state not in ('none', 'active', 'paused', 'complete', 'blocked'):
        raise ValueError('native Goal state unavailable or unknown')
    controls = observation.get('controls', [])
    if not isinstance(controls, list):
        raise ValueError('controls must list actually available native operations')
    digest = hashlib.sha256(objective.encode()).hexdigest()
    if owner:
        if (owner.get('runtime') != 'codex-goal' or not owner.get('token')
                or not observation.get('session')
                or owner.get('session') != observation['session']):
            raise ValueError('foreign or legacy owner; verified transfer required')
        if owner.get('goal', {}).get('objective_sha256') != digest:
            raise ValueError('unbound or different goal owner; reconcile partial start')
    if state != 'none' and observation.get('objective') != objective:
        raise ValueError('another native goal exists; do not replace it')
    if state != 'none' and not owner:
        raise ValueError('native goal without ownership; reconcile before adoption')
    if state == 'none' and owner:
        raise ValueError('owner without native goal; reconcile before release')
    action = {'none': 'create', 'active': 'continue', 'paused': 'resume',
              'complete': 'checkpoint', 'blocked': 'reconcile'}[state]
    if action in ('create', 'resume') and action not in controls:
        if observation.get('command_ui') is True:
            command = '/goal ' + objective if action == 'create' else '/goal resume'
            return dict(action='handoff', command=command, started=False)
        raise ValueError('native control unavailable; no timer or bounded fallback')
    return dict(action=action, objective_sha256=digest, started=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('claude-work/loop.json'))
    parser.add_argument('--observation', type=Path, required=True)
    parser.add_argument('--owner', type=Path, default=Path('claude-work/.loop-owner'))
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        with Path(config['loop_doc']).open(newline='') as stream:
            objective = select_block(config, stream.read(), 'codex', 'goal')
        owner = json.loads(args.owner.read_text()) if args.owner.exists() else None
        print(json.dumps(decide(objective, json.loads(args.observation.read_text()), owner)))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'Goal preflight blocked: {error}\n')


if __name__ == '__main__':
    main()
