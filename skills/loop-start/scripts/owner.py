#!/usr/bin/env python3
"""Atomic ownership operations. Scheduler reconciliation is the caller's responsibility."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
import fcntl
from contextlib import contextmanager


def workspace(path):
    """Find the shared Git lock directory and equivalent owner paths in worktrees."""
    def git(*args):
        return subprocess.check_output(['git', '-C', str(path.parent), *args],
                                       stderr=subprocess.DEVNULL).decode()
    try:
        root = Path(git('rev-parse', '--show-toplevel').strip()).resolve()
    except subprocess.CalledProcessError:
        return path.parent, [path]  # Standalone helper/test, outside Git.
    # Once inside Git, failed enumeration must block acquisition, never fall back locally.
    common = Path(git('rev-parse', '--path-format=absolute', '--git-common-dir').strip())
    relative = path.resolve().relative_to(root)
    records = git('worktree', 'list', '--porcelain', '-z').split('\0')
    peers = [Path(r[len('worktree '):]) / relative for r in records
             if r.startswith('worktree ')]
    if not peers:
        raise ValueError('cannot enumerate worktree ownership')
    return common, peers


@contextmanager
def locked(path):
    directory, peers = workspace(path)
    fd = os.open(directory, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield peers
    finally:
        os.close(fd)


def acquire(path, client, mode, session, runtime):
    record = dict(version=1, token=str(uuid.uuid4()), client=client, mode=mode,
                  host=socket.gethostname(), session=session, runtime=runtime,
                  started_at=datetime.now(timezone.utc).isoformat(), handles=[])
    with locked(path) as peers:
        if any(os.path.lexists(peer) for peer in peers):
            raise FileExistsError('an owner exists in this checkout or a linked worktree')
        with path.open('x') as stream:
            json.dump(record, stream)
            stream.flush()
            os.fsync(stream.fileno())
    return record


def release(path, token=None, digest=None):
    with locked(path):
        raw = path.read_bytes()
        if digest is not None:
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError('owner changed; repeat reconciliation')
        elif not token or json.loads(raw).get('token') != token:
            raise ValueError('owner token mismatch')
        path.unlink()


def bind_goal(path, token, objective, state, session):
    """Persist observed native state, never perform or certify a native operation."""
    if state not in ('active', 'paused', 'complete', 'blocked'):
        raise ValueError('unknown native state')
    if not objective.strip() or len(objective) > 4000:
        raise ValueError('goal objective must contain 1–4000 characters')
    with locked(path):
        record = json.loads(path.read_text())
        if record.get('token') != token or record.get('runtime') != 'codex-goal':
            raise ValueError('owner token/runtime mismatch')
        if record.get('session') != session:
            raise ValueError('owner session mismatch')
        digest = hashlib.sha256(objective.encode()).hexdigest()
        if record.get('goal', {}).get('objective_sha256', digest) != digest:
            raise ValueError('goal objective changed; reconcile before rebinding')
        record['goal'] = dict(objective_sha256=digest, state=state,
                              observed_at=datetime.now(timezone.utc).isoformat())
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as out:
                temporary = Path(out.name)
                json.dump(record, out)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, default=Path('claude-work/.loop-owner'))
    sub = parser.add_subparsers(dest='operation', required=True)
    claim = sub.add_parser('acquire')
    claim.add_argument('--client', choices=['claude', 'codex'], required=True)
    claim.add_argument('--mode', choices=['persistent', 'bounded', 'goal'], required=True)
    claim.add_argument('--session', required=True)
    claim.add_argument('--runtime', required=True)
    bind = sub.add_parser('bind-goal', help='record a freshly inspected native state')
    bind.add_argument('--token', required=True)
    bind.add_argument('--objective-file', type=Path, required=True)
    bind.add_argument('--state', choices=['active', 'paused', 'complete', 'blocked'], required=True)
    bind.add_argument('--session', required=True)
    drop = sub.add_parser('release')
    drop.add_argument('--token', required=True)
    recover = sub.add_parser('recover', help='only after authorized, verified shutdown')
    recover.add_argument('--sha256', required=True)
    args = parser.parse_args()
    try:
        if args.operation == 'acquire':
            print(json.dumps(acquire(args.path, args.client, args.mode, args.session, args.runtime)))
        elif args.operation == 'bind-goal':
            print(json.dumps(bind_goal(args.path, args.token, args.objective_file.read_text(),
                                       args.state, args.session)))
        else:
            release(args.path, token=getattr(args, 'token', None),
                    digest=getattr(args, 'sha256', None))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Ownership unchanged or blocked: {error}\n')


if __name__ == '__main__':
    main()
