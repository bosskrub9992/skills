# Backend: Agent-tool subagents (fallback)

Used only when the Orca probe fails at start of mode. Announce the fallback and its
limits once: no effort control, alias-only models, no blocking questions, no `workdir`.

## Spawn

`Agent` tool, one call per worker, all independent spawns in one message:

- `subagent_type`: `general-purpose` for every class (Explore and Plan cannot write the
  report file).
- `model`: the alias nearest the matrix row (`claude-opus-5-5` → `opus`,
  `claude-sonnet-5` → `sonnet`). Never a model in `fallback.forbidden_models`; a row
  naming one (review-code on Fable) is downgraded to `opus` and the downgrade is stated
  in the dispatch line to the user.
- `description`: `<class>-<slug>-<alias>-<effort>` (e.g. `ship-worklist-opus-high`);
  effort is the session's, since the Agent tool cannot set it.
- No `isolation` parameter: the Agent tool's worktree is of the umbrella repo, which is
  useless for nested subrepos. Isolation comes from the brief's treehouse lease exactly
  as on Orca.
- `prompt`: "Read and follow `<workspace>/.scratch/orchestrator/briefs/<id>.md` in
  full; its Workspace and Reporting sections are binding. Write your final report to
  `<workspace>/.scratch/orchestrator/reports/<id>.md` and end with one line
  `RESULT: succeeded|failed|blocked|needs-decision`."

Set brief frontmatter `status: running` on spawn.

## Supervision

- The tool notifies you when a subagent finishes; that notification is the `worker_done`
  event. Read `reports/<id>.md`, not the notification text, as the evidence.
- Staleness: a `running` task whose report file has not changed for longer than the
  brief's `expected_duration` is stale — check whether the agent is still running (task
  list) before escalating.
- Questions: subagents cannot block. The brief instructs them to stop with
  `RESULT: needs-decision` and the question in the report. Record the question under
  `pending_question` in the brief, relay per the "Worker questions" rule, then spawn a
  fresh subagent with the answer appended to the brief (`## Decisions`). The lease is
  found again by holder = task id.
- Steering a running subagent: `SendMessage` to its id with one line; long instructions
  go into the brief.

## Queue and reconcile

Brief frontmatter `status` is the task store: `queued | running | done | failed |
blocked`. Update it on every spawn and completion. Reconcile on restart by globbing
`briefs/*.md` and `treehouse status` per subrepo (lease holder = task id). A `running`
brief with no live agent and no report → stale; verify, then treat as failed and ask
the user before respawning.

## Review and fix rounds

Same as SKILL.md: `briefs/<id>-review.md` spawns a `general-purpose` reviewer on `opus`
(downgraded from the matrix's Fable row; say so); `briefs/<id>-fixN.md` spawns a fresh
ship subagent that finds the existing lease by holder.

## Settlement

There is no terminal to release. After reading the report, mark the brief `done` or
`failed`. Landing and teardown follow SKILL.md "Landing and teardown" — a failed or
unlanded task keeps its lease until the user grants discard authority.
