import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "suggest-handoff.py"
SKILL_MD = HOOK.parent.parent / "SKILL.md"
WINDOW = 1000
SESSION = "s1"


class SuggestHandoffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.transcript = Path(self.tmp.name) / "transcript.jsonl"
        self.doc = Path(self.tmp.name) / "auto-handoff" / f"handoff-{SESSION}.md"
        self.env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("AUTO_HANDOFF_", "CLAUDE_CODE_"))
        }
        self.env.update(
            {
                "TMP": self.tmp.name,
                "TEMP": self.tmp.name,
                "TMPDIR": self.tmp.name,
                "AUTO_HANDOFF_CONTEXT_WINDOW": str(WINDOW),
            }
        )

    def write_doc(self, mtime):
        self.doc.parent.mkdir(exist_ok=True)
        self.doc.write_text("# Handoff", encoding="utf-8")
        os.utime(self.doc, (mtime, mtime))

    def run_hook(
        self,
        pct,
        threshold=None,
        event="UserPromptSubmit",
        padding=1,
        trailing=(),
        agent_id=None,
    ):
        usage = {"input_tokens": pct * WINDOW // 100, "output_tokens": 0}
        lines = (
            [
                {"type": "assistant", "message": {"model": "m", "usage": {"input_tokens": 1}}},
                {"type": "assistant", "message": {"model": "m", "usage": usage}},
            ]
            + [{"type": "user", "message": {"content": "x" * 1000}}] * padding
            + list(trailing)
        )
        self.transcript.write_text(
            "".join(json.dumps(l) + "\n" for l in lines), encoding="utf-8"
        )
        env = dict(self.env)
        if threshold is not None:
            env["AUTO_HANDOFF_THRESHOLD_PCT"] = str(threshold)
        payload = {
            "transcript_path": str(self.transcript),
            "session_id": SESSION,
            "hook_event_name": event,
        }
        if agent_id:
            payload["agent_id"] = agent_id
        stdin = json.dumps(payload)
        out = subprocess.run(
            [sys.executable, str(HOOK)],
            input=stdin,
            capture_output=True,
            text=True,
            env=env,
            check=True,
        ).stdout.strip()
        if not out:
            return None
        hso = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], event)
        return hso["additionalContext"]

    def test_silent_below_default_threshold(self):
        self.assertIsNone(self.run_hook(29))

    def test_fires_at_default_threshold(self):
        msg = self.run_hook(30)
        self.assertIn("[auto-handoff hook]", msg)
        self.assertIn("30%", msg)
        self.assertIn("hook-started", msg)
        self.assertIn(str(self.doc), msg)
        self.assertIn(str(SKILL_MD), msg)

    def test_refresh_reminder_names_the_skill_file(self):
        self.run_hook(30)
        self.write_doc(1000)
        self.run_hook(31)
        self.assertIn(str(SKILL_MD), self.run_hook(34))

    def test_silent_for_subagent_tool_calls(self):
        self.assertIsNone(self.run_hook(30, event="PostToolUse", agent_id="a1"))
        self.assertIn("hook-started", self.run_hook(30, event="PostToolUse"))

    def test_skips_synthetic_and_api_error_entries(self):
        zero = {"input_tokens": 0, "output_tokens": 0}
        trailing = [
            {"type": "assistant", "message": {"model": "<synthetic>", "usage": zero}},
            {
                "type": "assistant",
                "isApiErrorMessage": True,
                "message": {"model": "m", "usage": {"input_tokens": 5}},
            },
            {"type": "assistant", "message": {"model": "m", "usage": zero}},
        ]
        self.assertIsNotNone(self.run_hook(30))
        self.write_doc(1000)
        self.assertIsNone(self.run_hook(31, trailing=trailing))
        self.assertIn("Rewrite it", self.run_hook(34, trailing=trailing))

    def test_failed_state_write_leaves_no_temp_file(self):
        state = self.doc.parent / f"state-{SESSION}.json"
        state.mkdir(parents=True)
        self.assertIsNotNone(self.run_hook(30))
        self.assertEqual(list(self.doc.parent.glob("*.tmp")), [])

    def test_finds_usage_beyond_the_first_tail_chunk(self):
        self.assertIn("30%", self.run_hook(30, padding=600))

    def test_fires_on_post_tool_use(self):
        self.assertIn("hook-started", self.run_hook(30, event="PostToolUse"))

    def test_threshold_env_override(self):
        self.assertIsNone(self.run_hook(30, threshold=50))
        self.assertIsNotNone(self.run_hook(50, threshold=50))

    def test_renags_only_after_ten_more_points(self):
        self.assertIsNotNone(self.run_hook(30))
        self.assertIsNone(self.run_hook(35))
        self.assertIsNone(self.run_hook(39))
        self.assertIsNotNone(self.run_hook(40))

    def test_usage_drop_resets_after_compact(self):
        self.assertIsNotNone(self.run_hook(38))
        self.assertIsNone(self.run_hook(5))
        self.assertIsNotNone(self.run_hook(30))

    def test_asks_to_refresh_doc_every_three_points(self):
        self.assertIn("hook-started", self.run_hook(30))
        self.write_doc(1000)
        self.assertIsNone(self.run_hook(31, event="PostToolUse"))
        self.assertIsNone(self.run_hook(33, event="PostToolUse"))
        msg = self.run_hook(34, event="PostToolUse")
        self.assertIn("Rewrite it", msg)
        self.assertIn("31%", msg)
        self.assertIsNone(self.run_hook(36))
        self.assertIn("Rewrite it", self.run_hook(37))
        self.write_doc(2000)
        self.assertIsNone(self.run_hook(38))
        self.assertIsNone(self.run_hook(40))
        self.assertIn("38%", self.run_hook(41))

    def test_old_doc_does_not_count_after_compact(self):
        self.assertIsNotNone(self.run_hook(30))
        self.write_doc(1000)
        self.assertIsNone(self.run_hook(31))
        self.assertIsNone(self.run_hook(5))
        self.assertIn("hook-started", self.run_hook(30))


if __name__ == "__main__":
    unittest.main()
