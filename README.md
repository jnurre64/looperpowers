# looperpowers

Three global Claude Code skills that own the lifecycle of a self-paced orchestrator loop (the
`/loop` that grinds a GitHub backlog through the sandbox-pal pipeline):

| skill | use it when |
|---|---|
| `/loop-setup` | a project needs the loop documents and config the other two read |
| `/loop-pause` | you want the loop stopped at a clean, clear point, ready to resume later |
| `/loop-start` | you want the loop running again, exactly as the project defines it |

The procedure is the same in every project; only data differs. Each project keeps its data in
`claude-work/loop.json` and the "Starting the loop" block of its `docs/LOOP.md`. The skills
never fork per project.

## Install

```bash
git clone https://github.com/jnurre64/looperpowers ~/repos/looperpowers
~/repos/looperpowers/install.sh      # symlinks skills/* into ~/.claude/skills/
```

Re-run `install.sh` after a `git pull`; restart Claude Code sessions to pick up new skills.

## Design

`docs/superpowers/specs/2026-09-06-loop-skills-design.md`. Templates for the two project
documents live in `templates/`; skills are TDD'd per superpowers:writing-skills, with the
baseline transcripts under `tests/`.
