#!/usr/bin/env python3
"""Validate a read-only runtime inspection and extract the selected command verbatim.

The report must come from current tool inspection, not static project configuration.
This helper does not implement a scheduler or replace identity/git/notification checks.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


def select_block(config, document, client, mode):
    mapping = config.get('start_blocks')
    if mapping is None:
        heading = 'Starting the loop' if (client, mode) == ('claude', 'persistent') else None
    else:
        heading = mapping.get(client, {}).get(mode)
    if not heading:
        raise ValueError('no committed start block for selected client/mode')
    # Parse headings only outside fences; preserve the original block bytes/newlines.
    sections = []
    active = False
    fence = None
    captured = None
    commands = []
    for line in document.splitlines(keepends=True):
        if fence:
            if re.fullmatch(r' {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}[ \t]*(?:\r?\n)?', line):
                fence = None
                if captured is not None:
                    commands.append(''.join(captured))
                    captured = None
            elif captured is not None:
                captured.append(line)
            continue
        opener = re.match(r' {0,3}(`{3,}|~{3,})[^\r\n]*', line)
        if opener:
            fence = opener[1]
            captured = [] if active else None
            continue
        header = re.match(r'^(#{1,2})[ \t]+(.+?)\s*$', line)
        if header:
            if active:
                sections.append(commands)
            active = header[1] == '##' and header[2] == heading
            commands = []
    if active:
        if captured is not None:
            raise ValueError('unclosed start block')
        sections.append(commands)
    if len(sections) != 1 or not sections[0] or not sections[0][0].strip():
        raise ValueError('missing, duplicate heading or empty start block')
    return sections[0][0]


def require_stopped(status):
    headers = [line for line in status.splitlines() if re.match(r'^## Last updated:', line)]
    if len(headers) > 1:
        raise ValueError('ambiguous dashboard state')
    header = headers[0] if headers else next((line for line in status.splitlines() if line.strip()), '')
    if not re.search(r'\bSTOPPED\b', header) or re.search(r'\b(RUNNING|PAUSED)\b', header):
        raise ValueError('dashboard requires pause/reconciliation; do not edit only the header')


def check(config, document, status, client, mode, report, dirty=False):
    if dirty:
        raise ValueError('dirty checkout; commit or remove pending files')
    require_stopped(status)
    if report.get('client') != client or report.get('mode') != mode:
        raise ValueError('runtime report does not match selected client/mode')
    capabilities = report.get('capabilities', {})
    required = ['inspect', 'stop']
    if mode == 'persistent':
        required += ['schedule', 'wake_on_completion', 'fallback']
    missing = [name for name in required if capabilities.get(name) is not True]
    if missing:
        raise ValueError('missing runtime capabilities: ' + ', '.join(missing))
    if report.get('scheduler_quiescent') is not True or report.get('dispatch_reconciled') is not True:
        raise ValueError('scheduler/dispatch state unknown or unreconciled')
    return select_block(config, document, client, mode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', choices=['claude', 'codex'], required=True)
    parser.add_argument('--mode', choices=['persistent', 'bounded'], default='persistent')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    try:
        config = json.loads(Path('claude-work/loop.json').read_text())
        dirty = subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
        # Files are opened without universal newline conversion for verbatim output.
        with Path(config['loop_doc']).open(newline='') as stream:
            document = stream.read()
        command = check(config, document, Path(config['status_file']).read_text(),
                        args.client, args.mode, json.loads(args.report.read_text()), bool(dirty))
        sys.stdout.write(command)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Preflight blocked: {error}\n')


if __name__ == '__main__':
    main()
