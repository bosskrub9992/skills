import json
import os
import sys

from handoff_doc import doc_path, state_path

THRESHOLD = float(os.environ.get("AUTO_HANDOFF_THRESHOLD_PCT", "30"))
REFRESH_STEP_PCT = float(os.environ.get("AUTO_HANDOFF_REFRESH_STEP_PCT", "3"))
RENAG_STEP_PCT = 10
COMPACT_DROP_PCT = 5
TAIL_CHUNK = 256 * 1024

WINDOW_OVERRIDE = os.environ.get(
    "AUTO_HANDOFF_CONTEXT_WINDOW"
) or os.environ.get("CLAUDE_CODE_MAX_CONTEXT_TOKENS")
DISABLE_1M = os.environ.get("CLAUDE_CODE_DISABLE_1M_CONTEXT") == "1"
MODELS_WITH_200K = ("haiku",)
WINDOW_1M = 1_000_000
WINDOW_200K = 200_000


def context_window(model):
    if WINDOW_OVERRIDE:
        return int(WINDOW_OVERRIDE)
    model = (model or "").lower()
    if DISABLE_1M or any(sub in model for sub in MODELS_WITH_200K):
        return WINDOW_200K
    return WINDOW_1M


def last_usage_in(lines):
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if e.get("type") != "assistant" or e.get("isApiErrorMessage"):
            continue
        msg = e.get("message") or {}
        usage = msg.get("usage")
        if msg.get("model") == "<synthetic>" or not usage or not total_tokens(usage):
            continue
        return msg.get("model"), usage
    return None


def total_tokens(usage):
    return (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("output_tokens", 0)
    )


def last_assistant_usage(transcript_path):
    try:
        with open(transcript_path, "rb") as f:
            size = f.seek(0, os.SEEK_END)
            chunk = TAIL_CHUNK
            while True:
                start = max(0, size - chunk)
                f.seek(start)
                lines = f.read().splitlines()
                if start > 0:
                    lines = lines[1:]
                found = last_usage_in(lines)
                if found or start == 0:
                    return found or (None, None)
                chunk *= 4
    except OSError:
        return None, None


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def doc_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def reminder(state, pct, doc):
    doc_pct = state.get("doc_pct")
    if doc_pct is not None:
        nagged = state.get("refresh_nag_pct") or doc_pct
        if pct < max(doc_pct, nagged) + REFRESH_STEP_PCT:
            return None
        state["refresh_nag_pct"] = pct
        return (
            f"[auto-handoff hook] This session has used {pct:.0f}% of its "
            f"context. The handoff document at {doc} was last written at "
            f"{doc_pct:.0f}%. Rewrite it now by step 3 of the auto-handoff "
            "skill, at the same path with the current state, then go on with "
            "the work."
        )

    nag_pct = state.get("nag_pct")
    if nag_pct is not None and pct < nag_pct + RENAG_STEP_PCT:
        return None
    state["nag_pct"] = pct
    return (
        f"[auto-handoff hook] This session has used {pct:.0f}% of its context. "
        "Run the auto-handoff skill on all pending work as a hook-started "
        "handoff; the host file it points you to says when. Handoff "
        f"document path: {doc}"
    )


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return

    transcript_path = data.get("transcript_path")
    session_id = data.get("session_id", "unknown")
    event = data.get("hook_event_name", "UserPromptSubmit")
    if not transcript_path or data.get("agent_id"):
        return

    model, usage = last_assistant_usage(transcript_path)
    if not usage:
        return

    pct = total_tokens(usage) * 100.0 / context_window(model)

    spath = state_path(session_id)
    state = load_state(spath)
    last_pct = state.get("last_pct")
    if last_pct is not None and pct < last_pct - COMPACT_DROP_PCT:
        state = {"doc_mtime": state.get("doc_mtime")}
    state["last_pct"] = pct

    doc = doc_path(session_id)
    mtime = doc_mtime(doc)
    if mtime is not None and mtime != state.get("doc_mtime"):
        state["doc_mtime"] = mtime
        state["doc_pct"] = pct
        state.pop("refresh_nag_pct", None)

    message = reminder(state, pct, doc) if pct >= THRESHOLD else None
    save_state(spath, state)
    if not message:
        return

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": message,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
