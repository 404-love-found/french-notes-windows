"""End-to-end desktop flows against a temporary local CSV."""

from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from french_notes.ui import FrenchNotesApp


class DesktopFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / "notes.csv"
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            if sys.platform == "win32":
                raise
            self.skipTest(f"Desktop display unavailable: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.settings_patch = patch("french_notes.ui.app_data_dir", return_value=self.folder / "settings")
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.messages = patch("french_notes.ui.messagebox.showerror")
        self.error_dialog = self.messages.start()
        self.addCleanup(self.messages.stop)
        self.app = FrenchNotesApp(self.root, self.path)
        self.root.update()

    def enter(self, text):
        self.app.input.delete("1.0", "end")
        self.app.input.insert("1.0", text)
        self.root.update()
        self.app.analyze()
        self.root.update()

    def test_input_preview_save_reload_and_search(self):
        self.enter("École\nécole\nJe suis étudiant.\n\nà")
        self.assertEqual([item.status for item in self.app.candidates], ["new", "batch", "new", "new"])
        self.assertFalse(self.path.exists(), "Preview must not write the CSV")
        self.app.save_new()
        self.root.update()
        self.assertEqual(self.app.input.get("1.0", "end-1c"), "")
        self.assertEqual(len(self.app.store.load()), 3)
        self.assertIn("Notes enregistrées : 3", self.app.summary.get())
        self.app.search.set("ÉCOLE")
        self.assertEqual(len(self.app.library_tree.get_children()), 1)
        self.app.search.set("")
        self.app.category_filter.set("Phrases")
        self.assertEqual(len(self.app.library_tree.get_children()), 1)
        self.app.category_filter.set("Mots")
        self.assertEqual(len(self.app.library_tree.get_children()), 2)
        self.app.category_filter.set("Tous")
        self.assertEqual(len(self.app.library_tree.get_children()), 3)
        self.enter(" école \nJE  SUIS étudiant.")
        self.assertEqual([item.status for item in self.app.candidates], ["existing", "existing"])
        self.assertIn("disabled", self.app.save_button.state())
        self.assertFalse(self.path.with_suffix(".csv.bak").exists())

    def test_editing_input_invalidates_previous_preview(self):
        self.enter("bonjour")
        self.assertNotIn("disabled", self.app.save_button.state())
        self.app.input.insert("end", "\nBonsoir")
        self.root.update()
        self.assertEqual(self.app.candidates, [])
        self.assertIn("disabled", self.app.save_button.state())
        self.assertFalse(self.path.exists())

    def test_save_and_export_buttons_fit_default_and_minimum_windows(self):
        # Windows does not lay out a withdrawn toplevel. Map a transparent test
        # window so the actual geometry is calculated without obscuring the desktop.
        self.root.attributes("-alpha", 0.0)
        self.root.deiconify()
        self.root.update()

        def check_bounds():
            self.app.notebook.select(self.app.intake_tab)
            for width, height in ((1180, 760), (1024, 640)):
                self.root.geometry(f"{width}x{height}")
                self.root.update()
                actual_size = (self.root.winfo_width(), self.root.winfo_height())
                if (width, height) == (1024, 640):
                    self.assertEqual(actual_size, (width, height))
                else:
                    # A small desktop can constrain the default window. Check
                    # controls in its actual viewport, including that constraint.
                    self.assertGreaterEqual(actual_size[0], 1024)
                    self.assertGreaterEqual(actual_size[1], 640)
                for button in (self.app.save_button, self.app.export_button):
                    with self.subTest(requested=(width, height), actual=actual_size, button=button.cget("text")):
                        # Assert mapping as well as bounds; filtering unmapped
                        # widgets would silently omit controls hidden by the layout.
                        self.assertTrue(button.winfo_ismapped())
                        self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
                        self.assertGreaterEqual(button.winfo_height(), button.winfo_reqheight())
                        x = button.winfo_rootx() - self.root.winfo_rootx()
                        y = button.winfo_rooty() - self.root.winfo_rooty()
                        self.assertGreaterEqual(x, 0)
                        self.assertGreaterEqual(y, 0)
                        self.assertLessEqual(x + button.winfo_width(), self.root.winfo_width())
                        self.assertLessEqual(y + button.winfo_height(), self.root.winfo_height())

        check_bounds()
        self.enter("bonjour\nBonjour\nJe suis étudiant.")
        self.assertNotIn("disabled", self.app.save_button.state())
        check_bounds()
        self.app.save_new()
        self.root.update()
        self.assertNotIn("disabled", self.app.export_button.state())
        check_bounds()
        self.enter("bonjour\nBonjour\nJe suis étudiant.")
        self.assertIn("disabled", self.app.save_button.state())
        check_bounds()

    def test_manual_category_is_saved(self):
        self.enter("pomme de terre")
        self.app.preview_tree.selection_set("0")
        self.app.set_category("word")
        self.app.save_new()
        self.root.update()
        self.assertEqual(self.app.store.load()[0].category, "word")

    def test_save_failure_preserves_unsaved_text(self):
        self.enter("aujourd’hui")
        with patch.object(self.app.store, "append", side_effect=OSError("disk is full")):
            self.app.save_new()
        self.assertEqual(self.app.input.get("1.0", "end-1c"), "aujourd’hui")
        self.assertEqual(len(self.app.candidates), 1)
        self.assertFalse(self.path.exists())
        self.error_dialog.assert_called_once()

    def test_storage_error_keeps_input_and_shows_dialog(self):
        self.enter("bonjour")
        self.app.store.lock_path.write_text("another instance", encoding="utf-8")
        self.app.save_new()
        self.assertEqual(self.app.input.get("1.0", "end-1c"), "bonjour")
        self.assertFalse(self.path.exists())
        self.error_dialog.assert_called_once()

    def test_bad_csv_switch_does_not_replace_current_path(self):
        self.enter("bonjour")
        malformed = self.folder / "invalid.csv"
        malformed.write_text("french,category\nbonjour,word\n", encoding="utf-8")
        with patch("french_notes.ui.filedialog.asksaveasfilename", return_value=str(malformed)):
            self.app.choose_csv()
        self.assertEqual(self.app.store.path, self.path)
        self.assertEqual(self.app.input.get("1.0", "end-1c"), "bonjour")
        self.error_dialog.assert_called_once()

    def test_saved_data_with_lock_cleanup_error_is_reported_as_saved(self):
        self.enter("école")
        original_unlink = Path.unlink

        def fail_only_lock(path, *args, **kwargs):
            if path == self.app.store.lock_path:
                raise PermissionError("lock cannot be removed")
            return original_unlink(path, *args, **kwargs)

        with patch.object(Path, "unlink", autospec=True, side_effect=fail_only_lock), patch("french_notes.ui.messagebox.showwarning") as warning:
            self.app.save_new()
        self.root.update()
        self.assertEqual(self.app.input.get("1.0", "end-1c"), "")
        self.assertEqual(len(self.app.store.load()), 1)
        self.assertEqual(len(self.app.notes), 1)
        self.assertIn("Notes enregistrées : 1", self.app.summary.get())
        warning.assert_called_once()
        self.error_dialog.assert_not_called()

    def test_switch_csv_keeps_input_and_requires_new_analysis(self):
        self.enter("bonjour")
        replacement = self.folder / "other.csv"
        with patch("french_notes.ui.filedialog.asksaveasfilename", return_value=str(replacement)):
            self.app.choose_csv()
        self.assertEqual(self.app.store.path, replacement)
        self.assertEqual(self.app.input.get("1.0", "end-1c"), "bonjour")
        self.assertEqual(self.app.candidates, [])
        self.assertIn("disabled", self.app.save_button.state())
        self.app.analyze()
        self.app.save_new()
        self.assertTrue(replacement.exists())
        self.assertFalse(self.path.exists())

    def test_export_contains_entire_csv_despite_filter(self):
        from docx import Document

        self.enter("école\nJe suis étudiant.")
        self.app.save_new()
        self.root.update()
        self.app.search.set("école")
        output = self.folder / "notes.docx"
        with patch("french_notes.ui.filedialog.asksaveasfilename", return_value=str(output)), patch("french_notes.ui.messagebox.showinfo"):
            self.app.export_all()
        text = "\n".join(paragraph.text for paragraph in Document(output).paragraphs)
        self.assertIn("école", text)
        self.assertIn("Je suis étudiant.", text)


if __name__ == "__main__":
    unittest.main()
