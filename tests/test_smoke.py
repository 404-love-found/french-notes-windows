"""Packaged self-test checks and safeguards for existing local data."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from french_notes import __version__
from french_notes.smoke import REPORT_NAME, run_self_test


class SelfTestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.folder = self.parent / "new-self-test"

    def run_quietly(self, path: Path) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = run_self_test(path)
        return code, output.getvalue()

    def diagnostic_report(self) -> dict:
        reports = list(self.parent.glob(f"french-notes-self-test-error-*/{REPORT_NAME}"))
        self.assertEqual(len(reports), 1)
        return json.loads(reports[0].read_text(encoding="utf-8"))

    def test_real_self_test_produces_success_report(self) -> None:
        # Ordinary test suites can run without a desktop.  The CLI self-test
        # itself never skips Tk: a missing display/dependency remains failure.
        import tkinter as tk

        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Desktop display unavailable: {error}")
        root.withdraw()
        root.destroy()

        code, output = self.run_quietly(self.folder)
        report_path = self.folder / REPORT_NAME
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(code, 0, report)
        self.assertEqual(report["success"], True)
        self.assertEqual(report["version"], __version__)
        self.assertEqual(
            report["checks"],
            [
                "isolated_directory",
                "csv_preview_classify_and_save",
                "csv_reload_and_unicode",
                "duplicate_batch_preserves_csv",
                "tk_interface_and_existing_library",
                "tk_analysis_and_manual_category",
                "docx_export_and_parse",
            ],
        )
        self.assertNotIn("error", report)
        self.assertNotIn("traceback", report)
        self.assertIn(str(report_path), output)
        self.assertTrue((self.folder / "notes.csv").is_file())
        self.assertTrue((self.folder / "notes.docx").is_file())
        self.assertFalse((self.folder / "notes.csv.lock").exists())

        # Rerunning on the same directory cannot replace a result or notes.
        original = {path.name: path.read_bytes() for path in self.folder.iterdir()}
        code, output = self.run_quietly(self.folder)
        self.assertEqual(code, 1)
        self.assertIn("failed", output)
        self.assertEqual({path.name: path.read_bytes() for path in self.folder.iterdir()}, original)
        failure = self.diagnostic_report()
        self.assertFalse(failure["success"])
        self.assertEqual(failure["checks"], [])

    def test_existing_user_csv_and_report_are_never_modified(self) -> None:
        self.folder.mkdir()
        (self.folder / "notes.csv").write_bytes(b"user CSV must stay unchanged")
        (self.folder / REPORT_NAME).write_bytes(b"existing report must stay unchanged")
        original = {path.name: path.read_bytes() for path in self.folder.iterdir()}

        code, output = self.run_quietly(self.folder)

        self.assertEqual(code, 1)
        self.assertEqual({path.name: path.read_bytes() for path in self.folder.iterdir()}, original)
        failure = self.diagnostic_report()
        self.assertFalse(failure["success"])
        self.assertEqual(failure["version"], __version__)
        self.assertEqual(failure["checks"], [])
        self.assertIn("FileExistsError", failure["traceback"])
        self.assertTrue(failure["error"])
        self.assertIn("french-notes-self-test-error-", output)

    def test_existing_empty_directory_is_refused(self) -> None:
        self.folder.mkdir()
        code, _output = self.run_quietly(self.folder)
        self.assertEqual(code, 1)
        self.assertEqual(list(self.folder.iterdir()), [])
        self.assertFalse(self.diagnostic_report()["success"])

    def test_existing_file_is_refused_and_preserved(self) -> None:
        self.folder.write_bytes(b"important local file")
        code, _output = self.run_quietly(self.folder)
        self.assertEqual(code, 1)
        self.assertEqual(self.folder.read_bytes(), b"important local file")
        self.assertFalse(self.diagnostic_report()["success"])

    def test_directory_symlink_does_not_modify_its_target(self) -> None:
        target = self.parent / "user-data"
        target.mkdir()
        csv_path = target / "notes.csv"
        csv_path.write_bytes(b"user notes")
        try:
            self.folder.symlink_to(target, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Directory symlinks unavailable: {error}")
        code, _output = self.run_quietly(self.folder)
        self.assertEqual(code, 1)
        self.assertTrue(self.folder.is_symlink())
        self.assertEqual(list(target.iterdir()), [csv_path])
        self.assertEqual(csv_path.read_bytes(), b"user notes")
        self.assertFalse(self.diagnostic_report()["success"])

    def test_broken_symlink_is_refused(self) -> None:
        target = self.parent / "missing-target"
        try:
            self.folder.symlink_to(target, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Directory symlinks unavailable: {error}")
        code, _output = self.run_quietly(self.folder)
        self.assertEqual(code, 1)
        self.assertTrue(self.folder.is_symlink())
        self.assertFalse(target.exists())
        self.assertFalse(self.diagnostic_report()["success"])


if __name__ == "__main__":
    unittest.main()
