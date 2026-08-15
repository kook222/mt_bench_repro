import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.tools import verify_release


class GitlessReleaseDiscoveryTest(unittest.TestCase):
    def test_fallback_matches_archive_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            included = (
                "README.md",
                ".github/workflows/validate.yml",
                "data/en/questions.jsonl",
                "unexpected-manuscript.hwp",
            )
            excluded = (
                ".venv/bin/python",
                "runs/logs/judge.log",
                "models/model.safetensors",
                "data/ko/questions_back.jsonl",
                ".env.local",
                ".coverage",
                "src/mtbench_repro.egg-info/PKG-INFO",
            )
            for relative in (*included, *excluded):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test", encoding="utf-8")

            with patch.object(verify_release, "ROOT", root), patch.object(
                verify_release.subprocess, "run"
            ) as git_run:
                observed = {
                    path.relative_to(root).as_posix()
                    for path in verify_release.public_files()
                }

            self.assertEqual(observed, set(included))
            self.assertIn("unexpected-manuscript.hwp", observed)
            git_run.assert_not_called()

    def test_fallback_when_git_metadata_is_unusable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / "README.md").write_text("test", encoding="utf-8")
            with patch.object(verify_release, "ROOT", root), patch.object(
                verify_release.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(128, ["git", "ls-files"]),
            ):
                observed = {
                    path.relative_to(root).as_posix()
                    for path in verify_release.public_files()
                }
            self.assertEqual(observed, {"README.md"})


if __name__ == "__main__":
    unittest.main()
