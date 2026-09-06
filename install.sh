#!/usr/bin/env bash
# Symlink every skill in skills/ into ~/.claude/skills/ (idempotent). Re-run after a git pull.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dest="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
mkdir -p "$dest"
for skill in "$here"/skills/*/; do
  name="$(basename "$skill")"
  target="$dest/$name"
  if [ -L "$target" ] && [ "$(readlink -f "$target")" = "$(readlink -f "$skill")" ]; then
    echo "ok       $name"
  elif [ -e "$target" ]; then
    echo "SKIP     $name — $target exists and is not this symlink; remove it to install" >&2
  else
    ln -s "${skill%/}" "$target"
    echo "linked   $name -> $target"
  fi
done
echo "Restart Claude Code sessions to pick up new skills."
