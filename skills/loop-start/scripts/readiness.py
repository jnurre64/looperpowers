#!/usr/bin/env python3
"""The ONE definition of "ready to loop-start".

Runs every hard-stop check the loop-start skill lists — branch, clean tree, up to date,
identity, notify path, start block, STATUS header, OWNER FILE — in that order, and prints
either a single ``PASS loop-preflight <sha> <utc>`` line or the first failing check with
its fix.  Both loop-start AND loop-pause run it: a STATUS header may claim "ready to
restart" only next to this script's PASS line.  A hand-written checklist is not readiness.

Why this exists (2026-09-09): a handoff declared a project "ready to restart" from a
checklist that never looked at the owner file; a paused record left by a closed runtime
blocked the next start.  Nothing may claim readiness without running this.

Usage: readiness.py --client <claude|codex> [--session <id>] [--mode <mode>] [--no-fetch]
  --session: an existing owner record is accepted only when it belongs to this
             client AND session (the starting/pausing session's own claim).  Without it
             any owner record is a hard stop — never assume a record is stale.
Exit 0 = PASS, 1 = a check failed, 2 = usage / missing config.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preflight  # noqa: E402  (select_block / resolve_mode)

OWNER = 'claude-work/.loop-owner'


class Failure(Exception):
    def __init__(self, check, problem, fix):
        super().__init__(problem)
        self.check, self.problem, self.fix = check, problem, fix


def git(*args, cwd=None):
    return subprocess.check_output(['git', *args], text=True, cwd=cwd).strip()


def run_checks(root, client, session=None, mode=None, fetch=True, gh='gh'):
    """Yield ('ok', check, detail) per passing check; raise Failure on the first failure."""
    root = Path(root)
    config_path = root / 'claude-work/loop.json'
    if not config_path.is_file():
        raise Failure('config', 'claude-work/loop.json missing', 'run /loop-setup first')
    config = json.loads(config_path.read_text())
    branch = config.get('default_branch', 'main')
    status_file = config.get('status_file', 'claude-work/STATUS.md')
    loop_doc = config.get('loop_doc', 'docs/LOOP.md')
    notify = config.get('notify')
    bot_user = config.get('bot_user')

    current = git('branch', '--show-current', cwd=root)
    if current != branch:
        raise Failure('branch', f"on '{current}'", f'git checkout {branch}')
    yield 'ok', 'branch', current

    dirty = [line for line in git('status', '--porcelain', cwd=root).splitlines()
             if not line.endswith(OWNER)]
    if dirty:
        files = ' '.join(line.split(None, 1)[1] for line in dirty)
        raise Failure('tree', 'uncommitted changes',
                      f'commit or remove: {files} (an untracked file is NOT "nothing actionable")')
    yield 'ok', 'tree', 'clean'

    if fetch:
        try:
            git('fetch', '-q', 'origin', cwd=root)
        except subprocess.CalledProcessError:
            raise Failure('fetch', 'git fetch failed', 'check network / origin')
    sb = git('status', '-sb', cwd=root).splitlines()[0]
    if 'behind' in sb:
        raise Failure('sync', sb, 'git pull --ff-only')
    if 'ahead' in sb:
        raise Failure('sync', sb, 'push or reconcile local commits first')
    yield 'ok', 'sync', sb

    if bot_user:
        try:
            login = subprocess.check_output([gh, 'api', 'user', '-q', '.login'], text=True,
                                            cwd=root, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            login = ''
        if login != bot_user:
            raise Failure('identity', f"gh is '{login or 'unauthenticated'}'",
                          f'loop expects {bot_user}')
        yield 'ok', 'identity', login
    else:
        yield 'ok', 'identity', '(no bot_user configured)'

    if notify:
        if not os.access(root / notify, os.X_OK):
            raise Failure('notify', f'{notify} missing or not executable', 'restore the notify script')
        yield 'ok', 'notify', notify
    else:
        yield 'ok', 'notify', '(unset — posts go to the user only)'

    try:
        selected = mode or preflight.resolve_mode(config, client)
        with (root / loop_doc).open(newline='') as stream:
            preflight.select_block(config, stream.read(), client, selected)
    except (ValueError, OSError) as error:
        raise Failure('block', f'no complete start block for {client}/{mode or "saved mode"}: {error}',
                      'run /loop-setup')
    yield 'ok', 'block', f'{client}/{selected} in {loop_doc}'

    try:
        status = (root / status_file).read_text()
        preflight.require_stopped(status)
    except (ValueError, OSError) as error:
        raise Failure('status', f'STATUS header is not STOPPED: {error}',
                      'pause/reconcile first (never edit only the header)')
    yield 'ok', 'status', 'STOPPED'

    owner_path = root / OWNER
    if owner_path.exists():
        try:
            record = json.loads(owner_path.read_text())
        except ValueError:
            record = {}
        o_client, o_session = record.get('client'), record.get('session')
        o_state = (record.get('goal') or {}).get('state', '-')
        if session and o_client == client and o_session == session:
            yield 'ok', 'owner', f'held by this session ({o_client})'
        else:
            raise Failure(
                'owner',
                f'record held by client={o_client} session={o_session} runtime={record.get("runtime")} state={o_state}',
                'that runtime must release it (owner.py release --token …), or transfer with '
                '/loop-start --force after verified shutdown of THAT runtime for THIS project. '
                'A record left by a runtime the project docs say is closed is a stale RECORD: '
                'release it once the user confirms — never ask to shut the other client down '
                '(it may run another project side by side). Never assume a record is stale.')
    else:
        yield 'ok', 'owner', 'no record (inspect scheduler state before acquiring)'


def pass_line(root):
    sha = git('rev-parse', '--short', 'HEAD', cwd=root)
    return f"PASS loop-preflight {sha} {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--client', choices=['claude', 'codex'], required=True)
    parser.add_argument('--session')
    parser.add_argument('--mode', choices=preflight.MODES)
    parser.add_argument('--no-fetch', action='store_true')
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    try:
        root = git('rev-parse', '--show-toplevel', cwd=args.root)
    except subprocess.CalledProcessError:
        parser.exit(2, 'FAIL: not in a git checkout\n')
    try:
        for _, check, detail in run_checks(root, args.client, args.session, args.mode, not args.no_fetch):
            print(f'ok   [{check}] {detail}')
    except Failure as failure:
        print(f'FAIL [{failure.check}]: {failure.problem}')
        print(f'  fix: {failure.fix}')
        sys.exit(2 if failure.check == 'config' else 1)
    print(pass_line(root))


if __name__ == '__main__':
    main()
