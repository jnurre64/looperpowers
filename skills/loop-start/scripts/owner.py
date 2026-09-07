#!/usr/bin/env python3
"""Atomic ownership operations. Scheduler reconciliation is the caller's responsibility."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import uuid
from datetime import datetime, timezone
import fcntl
from contextlib import contextmanager


@contextmanager
def locked(path):
    # Lock the directory, not the owner inode (which is replaced on reacquisition).
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def acquire(path, client, mode, session, runtime):
    record = dict(version=1, token=str(uuid.uuid4()), client=client, mode=mode,
                  host=socket.gethostname(), session=session, runtime=runtime,
                  started_at=datetime.now(timezone.utc).isoformat(), handles=[])
    with locked(path):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, default=Path('claude-work/.loop-owner'))
    sub = parser.add_subparsers(dest='operation', required=True)
    claim = sub.add_parser('acquire')
    claim.add_argument('--client', choices=['claude', 'codex'], required=True)
    claim.add_argument('--mode', choices=['persistent', 'bounded'], required=True)
    claim.add_argument('--session', required=True)
    claim.add_argument('--runtime', required=True)
    drop = sub.add_parser('release')
    drop.add_argument('--token', required=True)
    recover = sub.add_parser('recover', help='only after authorized, verified shutdown')
    recover.add_argument('--sha256', required=True)
    args = parser.parse_args()
    try:
        if args.operation == 'acquire':
            print(json.dumps(acquire(args.path, args.client, args.mode, args.session, args.runtime)))
        else:
            release(args.path, token=getattr(args, 'token', None),
                    digest=getattr(args, 'sha256', None))
    except (OSError, ValueError) as error:
        parser.exit(1, f'Ownership unchanged or blocked: {error}\n')


if __name__ == '__main__':
    main()
