# Config files

Two files, two owners. The skill itself stays workspace-agnostic.

## Global: `~/.config/orchestrator-mode/config.json`

The user's model preferences; travels with the user, not the repo.

```json
{
  "agent": "claude",
  "classes": {
    "ship":        { "model": "claude-opus-5-5",  "effort": "high" },
    "scout":       { "model": "claude-opus-5-5",  "effort": "high" },
    "review-code": { "model": "claude-fable-5-1", "effort": "high" }
  },
  "fallback": {
    "forbidden_models": ["fable", "haiku"]
  }
}
```

- `agent`: the Orca `--agent` id for every worker (`claude`, `codex`, `cursor`, …). A
  class may override with its own `agent` key. Non-Claude agents do not load Claude
  skills or CLAUDE.md, so the brief must carry the pipeline steps itself.
- `classes.<class>.model`: full provider model id (never an alias). `effort`: one of
  `low | medium | high | xhigh | max`; only for models that support it.
- `fallback.forbidden_models`: aliases the subagent backend must never pass. Orca
  workers ignore this list.
- Model short names for worker names: `claude-opus-5-5` → `opus55`,
  `claude-fable-5-1` → `fable51`, `claude-sonnet-5` → `sonnet5`.

Missing file → ask the user for the rows once, show the JSON, write it.

## Workspace: `<workspace>/.claude/orchestrator-mode.md`

Committed with the workspace. Sections are fixed so the skill can find them. The
`## Orca run` section body is the bare Run id and nothing else (the skill writes it on
the first `run-create`).

```markdown
# orchestrator-mode — <workspace name>

## Orca run
run_01ABC...

## Matrix overrides
| class | model | effort |
|---|---|---|
| scout | claude-sonnet-5 | medium |

## Adaptations
- <worktree / subrepo conventions>
- <shared mutable state: dev stack, ports, restart rules>
- <ship deliverable: PR vs local merge; merge autonomy>
- <pipelines that run inside the worker>
- <secrets / boot prerequisites for fresh worktrees>
```

Overrides win over the global matrix for that class. Adaptations win over the generic
rules in SKILL.md where they conflict. Missing file → run with the global matrix only
and say so once.

## Brief frontmatter (per task)

See the template in SKILL.md. `workdir`, `review`, `expected_duration`, `backend_ref`,
`status`, and `pending_question` are per-task and never live in either config file.
