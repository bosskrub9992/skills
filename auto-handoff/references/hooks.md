# Hooks

`npx skills` does not install hooks. Both live in this skill's `hooks/` folder
and go in `settings.json`.

> **Note:** the numbers below are the defaults at the time of writing and can
> change. The constants at the top of each script are the source of truth, so
> read them when a number matters. Some follow upstream limits that can move
> too: the model context windows, and Claude Code's 10,000-character cap on hook
> output, which the 9,000-character inline limit stays under.

- `suggest-handoff.py` (`UserPromptSubmit` and `PostToolUse`, so long
  autonomous turns are covered) reads the last assistant `usage` from the
  transcript and divides it by the model's context window: 200k for Haiku or
  when `CLAUDE_CODE_DISABLE_1M_CONTEXT=1`, otherwise 1M, overridden by
  `AUTO_HANDOFF_CONTEXT_WINDOW` or `CLAUDE_CODE_MAX_CONTEXT_TOKENS`.
  - At the threshold (`AUTO_HANDOFF_THRESHOLD_PCT`, default 30) with no
    document written since the last compact, it sends the handoff reminder,
    then again after every further 10 points.
  - Once the document is written, it asks for a rewrite after every further
    `AUTO_HANDOFF_REFRESH_STEP_PCT` points (default 3) since the last write.
  - It stays silent for subagents' tool calls, which carry the parent's
    session id.
  - A drop in usage, such as after a compact, resets both. Keep the threshold
    below `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` so the document exists before
    auto-compact.
- `attach-handoff.py` (`SessionStart`, matcher `compact`) runs after every
  manual or automatic compact. If this session's document exists, it adds it
  to the new context with its write time: inline up to 9,000 characters, or as
  a pointer to read above that. It attaches after every compact, because the
  next compact summary can drop what the last one attached.

```json
"UserPromptSubmit": [
  {"hooks": [{"type": "command", "command": "python", "args": ["<abs path to>/hooks/suggest-handoff.py"], "timeout": 15}]}
],
"PostToolUse": [
  {"hooks": [{"type": "command", "command": "python", "args": ["<abs path to>/hooks/suggest-handoff.py"], "timeout": 15}]}
],
"SessionStart": [
  {"matcher": "compact", "hooks": [{"type": "command", "command": "python", "args": ["<abs path to>/hooks/attach-handoff.py"], "timeout": 15}]}
]
```
