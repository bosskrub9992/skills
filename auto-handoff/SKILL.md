---
name: auto-handoff
description: >-
  Write a handoff document with the global /handoff skill so the work survives
  compaction — in T3 Code compact onto it right away, in Claude Code CLI and
  Claude desktop a hook attaches it at the next auto-compact. Use
  when the user says "/auto-handoff", "handoff and compact", "context is
  getting long", or in Thai "ส่งต่องาน", "handoff แล้ว compact", and when the
  auto-handoff hook reminder appears. For a handoff document alone, use
  /handoff.
---

# Auto Handoff

Write a handoff document to this session's fixed path. After the conversation
is compacted, a hook puts the document into the new context. T3 Code compacts
right away; every other host waits for auto-compact.

Relative paths below start from the folder that holds this SKILL.md; the hook
reminder names it. If a file is not there, report that instead of skipping the
handoff.

## 0. Pick the host

Check `T3CODE_THREAD_ID`, then read only the file for this host. It says when
to run steps 1–3 and how to hand off after them.

| `T3CODE_THREAD_ID` | Host | File |
|---|---|---|
| set | T3 Code | `references/t3-code.md` |
| unset | Claude Code CLI, Claude desktop | `references/compact-later.md` |

The handoff is **hook-started** when the `[auto-handoff hook]` reminder is in
context and the user did not ask; its focus is all pending work. Otherwise it
is **user-started**.

## 1. Pick the focus

The focus is the user's arguments. With no arguments it is "all pending work
from this session". Settle it without asking.

## 2. Get the document path

The `attach-handoff.py` hook finds the document by session id, so it must live
at `<OS temp>/auto-handoff/handoff-<session_id>.md`. The hook reminder names
this path. Without a reminder, get it from `python hooks/handoff_doc.py` in
this skill's folder; it reads `CLAUDE_CODE_SESSION_ID`.

## 3. Write the handoff document

Read `~/.agents/skills/handoff/SKILL.md` and follow it. It is set to
`disable-model-invocation`, so read the file rather than calling it through the
Skill tool. Tailor the document to the focus and save it to the path from
step 2, overwriting any earlier version. The path is already in the OS temp
directory, as that skill asks.

If that file is missing, write the document yourself: goal, current state,
done, pending, decisions and why, gotchas, next steps, and a **Suggested
skills** section. Reference other artifacts by path instead of copying them,
and redact secrets.

The next context starts from this document and the compact summary, so it must
stand alone.

## 4. Hand off through the host

Follow the host file from step 0.

## Hooks

Installing or changing the hooks, or a question about how they decide:
`references/hooks.md`. Handing off does not need it.
