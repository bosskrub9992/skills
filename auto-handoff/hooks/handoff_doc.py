import os
import sys
import tempfile


def state_dir():
    return os.path.join(tempfile.gettempdir(), "auto-handoff")


def doc_path(session_id):
    return os.path.join(state_dir(), f"handoff-{session_id}.md")


def state_path(session_id):
    return os.path.join(state_dir(), f"state-{session_id}.json")


if __name__ == "__main__":
    session_id = (
        sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CLAUDE_CODE_SESSION_ID")
    )
    if not session_id:
        sys.exit("no session id: pass one or set CLAUDE_CODE_SESSION_ID")
    print(doc_path(session_id))
