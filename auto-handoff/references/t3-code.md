# T3 Code: compact this thread now

## When

- **User-started**: run steps 1–3 now.
- **Hook-started**: finish the user's current request first, then run
  steps 1–3. The compact ends the work, so it waits for the request to be done.

## Hand off

1. Load the tool with ToolSearch: `select:mcp__t3-code__t3_thread_send`.
2. Call `t3_thread_send` with `threadId` = `T3CODE_THREAD_ID`,
   `mode: "queue"`, `message`:
   `/compact Preserve verbatim: handoff doc at <path>; focus: <focus>`.
   Wait for it to succeed.
3. Call it again with the same `threadId` and mode, `message`:
   `Read the handoff at <path> and continue. Focus: <focus>`.

T3 runs both after this turn ends: the first compacts the thread, the
`attach-handoff.py` hook adds the document to the new context, and the second
starts a turn that continues the work. Report "queued: compact, then kickoff"
and end the turn; any further tool call delays the compact.

## When a step fails

- The tool does not load, or the first send fails: report the error, then read
  `compact-later.md` in this folder and follow its "Hand off" section.
- Only the second send fails: the compact still runs. Give the user the
  kickoff in a code block to paste after the compact finishes.
