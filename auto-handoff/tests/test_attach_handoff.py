import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
HOOK = HOOKS / "attach-handoff.py"
SESSION = "s1"


class AttachHandoffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = dict(os.environ)
        self.env.update(
            {"TMP": self.tmp.name, "TEMP": self.tmp.name, "TMPDIR": self.tmp.name}
        )
        self.doc = Path(self.tmp.name) / "auto-handoff" / f"handoff-{SESSION}.md"

    def write_doc(self, body, mtime):
        self.doc.parent.mkdir(exist_ok=True)
        self.doc.write_text(body, encoding="utf-8")
        os.utime(self.doc, (mtime, mtime))

    def run_hook(self, agent_id=None):
        payload = {"session_id": SESSION, "source": "compact"}
        if agent_id:
            payload["agent_id"] = agent_id
        out = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=self.env,
            check=True,
        ).stdout.strip()
        if not out:
            return None
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]

    def test_doc_path_matches_helper(self):
        out = subprocess.run(
            [sys.executable, str(HOOKS / "handoff_doc.py"), SESSION],
            capture_output=True,
            text=True,
            env=self.env,
            check=True,
        ).stdout.strip()
        self.assertEqual(Path(out), self.doc)

    def test_silent_without_doc(self):
        self.assertIsNone(self.run_hook())

    def test_inlines_small_doc(self):
        self.write_doc("# Handoff\nnext: ship it", 1000)
        msg = self.run_hook()
        self.assertIn(str(self.doc), msg)
        self.assertIn("next: ship it", msg)

    def test_silent_for_subagent(self):
        self.write_doc("v1", 1000)
        self.assertIsNone(self.run_hook(agent_id="a1"))

    def test_decodes_utf16_and_bom_utf8_docs(self):
        self.doc.parent.mkdir(exist_ok=True)
        for encoding in ("utf-16", "utf-8-sig"):
            self.doc.write_text("# Handoff ส่งต่องาน", encoding=encoding)
            msg = self.run_hook()
            self.assertIn("<handoff-document>\n# Handoff ส่งต่องาน", msg)

    def test_points_to_large_doc(self):
        self.write_doc("x" * 9001, 1000)
        msg = self.run_hook()
        self.assertIn(str(self.doc), msg)
        self.assertNotIn("x" * 100, msg)
        self.assertIn("Read that file in full", msg)

    def test_attaches_latest_version_after_every_compact(self):
        self.write_doc("v1", 1000)
        self.assertIn("v1", self.run_hook())
        self.assertIn("v1", self.run_hook())
        self.write_doc("v2", 2000)
        msg = self.run_hook()
        self.assertIn("v2", msg)
        self.assertNotIn("v1", msg)


if __name__ == "__main__":
    unittest.main()
