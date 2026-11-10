# Claude Code CLI, Claude desktop: attach at the next compact

These hosts give the agent no way to compact its own conversation, so the
document waits for the next auto-compact, or a `/compact` the user types. The
`attach-handoff.py` hook then adds it to the new context.

## When

- **User-started**: run steps 1–3 now.
- **Hook-started**: run steps 1–3 now, even mid-task, then carry on.
  Auto-compact can land before the user's request is done, and the document
  must exist by then.

## Hand off

Do not compact. Report the document path, then go on with the work.

Keep the document current until the compact:

- Each time the hook asks you to rewrite it, run step 3 again and overwrite it
  at the same path with the state as of now, then carry on.
- Rewrite it yourself too after a milestone the next context must know about,
  such as a commit, a finished task or a changed decision.
