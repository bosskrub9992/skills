# Backend: Orca orchestration

Version-matched command reference is served by the binary itself:
`orca skills get orchestration` (kernel) and
`orca skills get orchestration --reference references/<name>.md` for
`coordinator-loop`, `messaging-and-gates`, `placement-and-remote`,
`recovery-and-cleanup`, `worker-contract`. Read the kernel once per session; this file
maps the orchestrator-mode rules onto it. Use `orca` for the whole session (on Linux
outside an Orca terminal use `orca-ide`; never bare `orca` there).

## Probe (start of mode)

```text
orca status --json
```

Backend = Orca when `ok` is true, `result.runtime.capabilities` lists
`orchestration.worker-launch-preferences.v1`, and `ORCA_TERMINAL_HANDLE` is set (Run
binding and consuming `check` resolve the caller from the Orca terminal). Capability
absent, or `worker-start` rejecting `--model`/`--effort` → Orca too old → escalate.

## Run binding

One long-lived Run per workspace. On start:

```text
orca orchestration run-current --json                   # already bound?
orca orchestration run-use --id <run_id> --json         # id from .claude/orchestrator-mode.md
orca orchestration run-create --objective "<workspace> orchestrator" --json   # first time only
```

Write the Run id under `## Orca run` in `<workspace>/.claude/orchestrator-mode.md` the
first time; `run-list --json` recovers it if the file is lost.

## Task + worker start

Extract the spec from the brief's `## Contract` section (absolute brief path; the awk
stops at the next `## ` heading whatever its name):

```bash
BRIEF=<workspace>/.scratch/orchestrator/briefs/<id>.md
SPEC="$(awk '/^## /{f=($0=="## Contract")} f' "$BRIEF")"
orca orchestration task-create --spec "$SPEC" --task-title "<worker name>" --display-name "<worker name>" --json
```

Append the returned task id to the brief's `backend_ref` list. Use
`--deps '["<task_id>"]'` only for a real ordering dependency (JSON quoting follows the
active shell).

```text
orca orchestration worker-start --task <task_id> --worktree current --agent <agent> \
  --model <full-model-id> --effort <level> --json
```

- `--worktree current` = the orchestrator's workspace root (default). With brief
  `workdir:` set → `--worktree path:<abs>`. Orca must already know the folder. A git
  repo (e.g. a subrepo): `orca repo add --path <abs> --json`. A plain folder:
  `orca project setup-existing-folder --project <id> --host <host-id> --path <abs> --kind folder --json`
  with ids from `orca project list --json` / `orca environment list --json`, then start
  with the returned selector as `id:<full worktree id>`. Register, report that you did,
  then start.
- `--effort` requires `--model`; neither combines with `--terminal`.
- Exit non-zero → do not relaunch. Read `failedStage` / `residualResources`, then
  `orca skills get orchestration --reference references/recovery-and-cleanup.md`.
- Compare `launch.requested` with `launch.effective` in the receipt. Mismatch →
  `worker-stop --dispatch <id>` and escalate.

### Skill visibility (why `workdir` exists)

Claude Code loads `.claude/skills/` and `.claude/agents/` from the start folder up to
the nearest repository root, `CLAUDE.md` from every ancestor, and `.claude/settings.json`
(hooks) only from the start folder. When subrepos have their own `.git`, a worker
started inside `app-backend/` gets that repo's skills and CLAUDE.md plus the
workspace CLAUDE.md, but not the workspace-installed skills or the guard hook. Default
(workspace root) gives the full workspace set. Not available on the subagent backend.

## Supervision loop

Wait in the background so the turn can end while work is in flight (rule 9):

```text
orca orchestration check --wait --types "worker_done,escalation,question" --timeout-ms 540000 --json
```

Run it via the shell tool with `run_in_background`; the tool re-invokes you when it
exits. Empty result or timeout = checkpoint → re-arm. After three consecutive empty
waits:

```text
orca orchestration worker-list --run <run_id> --include-remote --json
```

Act on each row's `projection.attention` / `projection.nextAction` (literal argv).
`nextAction: none` → read `liveness.reason`, keep waiting. Only positive proof of exit
(`exited` liveness, observed process exit, or a transcript ending without `worker_done`)
authorizes `worker-stop` / `worker-abandon` — load `recovery-and-cleanup.md` first.
`unverifiable` is absence, never proof.

A Delivery carries the whole FIFO batch; process every message before `--ack`:

```text
orca orchestration reply --id <message_id> --body "<answer>" --json          # worker ask
orca orchestration send --to dispatch:<dispatch_id> --subject "Follow-up" --body "<one line>" --json
orca orchestration check --ack <delivery_id> --wait --types "worker_done,escalation,question" --timeout-ms 540000 --json
```

Worker `ask` → SKILL.md "Worker questions". A factual ask is answered with `reply`
before the ack. A decision is forwarded to the user, its message id recorded as
`pending_question` in the brief, and that counts as processed: ack, re-arm, and `reply
--id <message_id>` when the user answers (the worker resumes the same question after its
own timeout). Gates (`gate-create`) are for orchestrator-owned DAG decisions only, never
to answer an ask.

### Pointer nudges

Mail that no armed `--wait` filter covers (worker heartbeats, every ~5 min) makes Orca type
`You have N orchestration message(s). Run orca orchestration check --run <run_id>` into the
idle orchestrator terminal. Run that `check`. If every message in the batch is a
`heartbeat`, ack it with `check --ack <delivery_id> --json` (no `--wait`; the background
wait is still armed), and end the turn with no message to the user. Anything else in the
batch → process it as above. Never add `heartbeat` to `--types`: every heartbeat would then
end the background wait, costing a wake plus a re-arm instead of one ack.

## Settlement

Validate each `worker_done` against the expected active Dispatch (task id + dispatch id
match, `--outcome` present). Then, before the ack, exactly one of:

```text
orca orchestration worker-start --task <next_task_id> --terminal <agent_terminal_handle> --worktree <same selector the worker was launched with> --json   # reuse
orca orchestration worker-retain --dispatch <dispatch_id> --json                                                                                        # user asked
orca orchestration worker-release --dispatch <dispatch_id> --json                                                                                       # default
```

Get the terminal handle from `worker-show --dispatch <dispatch_id> --json`. Reuse needs
its own `task-create` first (append the id to `backend_ref`). Archived output stays
readable via `worker-read --dispatch <id> --limit 50 --json`. Do not end the coordinator
turn while `worker-list --run <run_id> --terminal-state reclaimable --json` returns rows.

A valid `worker_done` settles the Task; never follow it with `task-update`.

## Review and fix rounds

Review and fix rounds are ordinary tasks: write `briefs/<id>-review.md` /
`briefs/<id>-fixN.md` per SKILL.md, extract the Contract, `task-create`, `worker-start`
with that class's matrix row. The fix worker leases nothing new — the template's
`## Workspace` sequence finds the slot already held by `<id>`. Never `send` fix
instructions to a settled ship Dispatch; it has idled per the worker contract.

## Landing and teardown

Per SKILL.md "Landing and teardown". Confirm the PR is merged with
`gh pr view <url> --json state -q .state` before any `treehouse return`.

## Shell notes (Windows)

Prefer the bash tool for the `--spec "$(...)"` extraction; a multiline argument with
quotes, `$` and backticks reaches `orca.exe` intact through it. In PowerShell 5.1 pass
JSON arrays with single quotes outside and double quotes inside; never paste POSIX
quoting into cmd.exe. Thai text in specs is fine through bash; avoid round-tripping files
through PowerShell.
