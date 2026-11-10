import json
import os
import sys
from datetime import datetime

from handoff_doc import doc_path

INLINE_LIMIT = 9000


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    session_id = data.get("session_id")
    if not session_id or data.get("agent_id"):
        return

    path = doc_path(session_id)
    try:
        written = datetime.fromtimestamp(os.path.getmtime(path))
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        body = raw.decode("utf-16", errors="replace")
    else:
        body = raw.decode("utf-8-sig", errors="replace")

    header = (
        "[auto-handoff hook] This conversation was just compacted. The handoff "
        f"document for this session, written {written:%Y-%m-%d %H:%M}, is at "
        f"{path}. It is the record of the work to continue. Where it and the "
        "compact summary disagree, the summary is newer."
    )
    if len(body) <= INLINE_LIMIT:
        context = f"{header}\n\n<handoff-document>\n{body}\n</handoff-document>"
    else:
        context = f"{header} Read that file in full before you continue."

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
