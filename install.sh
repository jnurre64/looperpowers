#!/usr/bin/env bash
# Install the same skills for either client; preserve the historical default.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
client="${1:-claude}"
if [[ $# -gt 1 || ! "$client" =~ ^(claude|codex|all)$ ]]; then
  echo "Usage: $0 [claude|codex|all]" >&2
  exit 2
fi
install_client() {
  local dest="$1" skill name target
  mkdir -p "$dest"
  for skill in "$here"/skills/*/; do
    name="$(basename "$skill")"
    target="$dest/$name"
    if [ -L "$target" ] && [ "$(readlink -f "$target")" = "$(readlink -f "$skill")" ]; then
      echo "ok       $target"
    elif [ -e "$target" ] || [ -L "$target" ]; then
      echo "SKIP     $target exists and is not this symlink; remove it to install" >&2
    else
      ln -s "${skill%/}" "$target"
      echo "linked   $target"
    fi
  done
}
if [[ "$client" == claude || "$client" == all ]]; then
  install_client "${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
fi
if [[ "$client" == codex || "$client" == all ]]; then
  install_client "${CODEX_SKILLS_DIR:-$HOME/.agents/skills}"
fi
echo "Restart the client if the skills do not appear. Installation does not provide scheduling."
