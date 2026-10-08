from __future__ import annotations

import csv
import io
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from french_notes.core import (
    CSV_HEADER,
    CSVStore,
    Candidate,
    Note,
    StoreError,
    ValidationError,
    classify,
    clean_text,
    normalize_key,
)


def make_note(french: str, category: str = "word") -> Note:
    return Note(str(uuid.uuid4()), category, french, "2026-10-07T12:00:00+00:00")


def csv_bytes(notes: list[Note], header=CSV_HEADER) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(header)
    for note in notes:
        writer.writerow((note.note_id, note.category, note.french, note.created_at))
    return buffer.getvalue().encode("utf-8-sig")


class TextTests(unittest.TestCase):
    def test_validation_error_keeps_value_error_compatibility_and_localizes(self):
        with self.assertRaises(ValueError) as caught:
            clean_text(123)
        error = caught.exception
        self.assertIsInstance(error, ValidationError)
        self.assertEqual(error.key, "content_text_required")
        self.assertEqual(error.params, {})
        self.assertEqual(str(error), "Le contenu en français doit être du texte.")
        self.assertEqual(error.localized_message("zh"), "法语内容必须是文字。")
        self.assertEqual(error.localized_message("en"), "French content must be text.")
        self.assertEqual(error.localized_message("unknown"), str(error))

    def test_legacy_store_error_constructor_preserves_literal_message(self):
        error = StoreError("external raw diagnostic")
        self.assertIsNone(error.key)
        self.assertEqual(str(error), "external raw diagnostic")
        self.assertEqual(error.localized_message("zh"), str(error))
        self.assertEqual(error.localized_message("en"), str(error))

    def test_clean_and_key_keep_accents_and_punctuation(self):
        self.assertEqual(clean_text("  BONJOUR\t  le\u00a0monde  "), "BONJOUR le monde")
        self.assertEqual(normalize_key("  ÉTÉ   doux "), normalize_key("été\tdoux"))
        self.assertNotEqual(normalize_key("cote"), normalize_key("côte"))
        self.assertNotEqual(normalize_key("bonjour"), normalize_key("bonjour!"))
        self.assertNotEqual(normalize_key("l'amour"), normalize_key("l’amour"))

    def test_unicode_nfc_equivalence(self):
        self.assertEqual(clean_text("e\u0301cole"), "école")
        self.assertEqual(normalize_key("E\u0301COLE"), normalize_key("école"))

    def test_classification(self):
        for word in ("bonjour", "œuvre", "électricité", "l’amour", "aujourd'hui", "porte-monnaie"):
            with self.subTest(word=word):
                self.assertEqual(classify(word), "word")
        for sentence in ("Je suis ici", "Bonjour!", "salut…", "oui,", "mot;", "mot:", "deux\tmots"):
            with self.subTest(sentence=sentence):
                self.assertEqual(classify(sentence), "sentence")

    def test_invalid_lines(self):
        for value in (
            "", " \t", "1234", "12,3!", "—…", "🙂", "bonjour\x00",
            "bonjour\x0b", "bonjour\x0c", "bonjour\x1c", "\ud800",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    classify(value)


class CSVStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "notes.csv"
        self.store = CSVStore(self.path)

    def write_notes(self, notes: list[Note]):
        self.path.write_bytes(csv_bytes(notes))

    def assert_clean(self):
        self.assertFalse(self.store.lock_path.exists())
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])
        self.assertEqual(list(self.path.parent.glob(".*.tmp")), [])

    def test_missing_file_and_empty_input_do_not_create_files(self):
        self.assertEqual(self.store.load(), [])
        self.assertEqual(self.store.preview("\n \t\n"), [])
        result = self.store.append([])
        self.assertEqual(result.added, [])
        self.assertEqual(result.skipped, 0)
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_preview_existing_and_batch_duplicates(self):
        self.write_notes([make_note("école"), make_note("Je suis ici", "sentence")])
        preview = self.store.preview(" E\u0301COLE \n\n JE   suis ICI \nété\nÉTÉ\n ete \nété!\n")
        self.assertEqual(
            [(item.french, item.category, item.status) for item in preview],
            [
                ("ÉCOLE", "word", "existing"),
                ("JE suis ICI", "sentence", "existing"),
                ("été", "word", "new"),
                ("ÉTÉ", "word", "batch"),
                ("ete", "word", "new"),
                ("été!", "sentence", "new"),
            ],
        )

    def test_preview_reports_invalid_line(self):
        with self.assertRaisesRegex(ValueError, "Ligne 3 de la saisie"):
            self.store.preview("bonjour\n\n1234\n")
        self.assertFalse(self.path.exists())

    def test_input_line_error_localizes_nested_validation_reason(self):
        with self.assertRaises(ValidationError) as caught:
            self.store.preview("bonjour\n\n1234")
        error = caught.exception
        self.assertEqual(error.key, "input_line_invalid")
        self.assertEqual(error.params["line"], 3)
        self.assertEqual(error.params["detail"].key, "letter_required")
        chinese = error.localized_message("zh")
        english = error.localized_message("en")
        self.assertIn("输入第 3 行", chinese)
        self.assertIn("至少需要一个字母", chinese)
        self.assertIn("Input line 3", english)
        self.assertIn("at least one letter", english)
        for message in (chinese, english):
            self.assertNotIn("Ligne", message)
            self.assertNotIn("Chaque note", message)
        self.assertFalse(self.path.exists())

    def test_csv_header_error_localizes_without_changing_damaged_file(self):
        original = b"wrong,header\r\n"
        self.path.write_bytes(original)
        with self.assertRaises(StoreError) as caught:
            self.store.load()
        error = caught.exception
        self.assertEqual(error.key, "csv_header")
        self.assertIn("CSV 表头", error.localized_message("zh"))
        self.assertIn("CSV header must contain", error.localized_message("en"))
        self.assertNotIn("L'en-tête", error.localized_message("zh"))
        self.assertNotIn("L'en-tête", error.localized_message("en"))
        self.assertEqual(self.path.read_bytes(), original)

    def test_csv_row_error_localizes_nested_application_reason(self):
        note = make_note("bonjour", "invalid")
        self.write_notes([note])
        original = self.path.read_bytes()
        with self.assertRaises(StoreError) as caught:
            self.store.load()
        error = caught.exception
        self.assertEqual(error.key, "csv_row_invalid")
        self.assertEqual(error.params["line"], 2)
        self.assertEqual(error.params["detail"].key, "category_invalid")
        chinese = error.localized_message("zh")
        english = error.localized_message("en")
        self.assertIn("CSV 第 2 行", chinese)
        self.assertIn("分类必须为 word 或 sentence", chinese)
        self.assertIn("CSV line 2", english)
        self.assertIn("category must be 'word' or 'sentence'", english)
        for message in (chinese, english):
            self.assertNotIn("Ligne", message)
            self.assertNotIn("La catégorie", message)
        self.assertEqual(self.path.read_bytes(), original)

    def test_append_only_new_and_allow_category_override(self):
        preview = self.store.preview("bonjour\n BONJOUR \nJe suis ici\n")
        preview[0].category = "sentence"
        result = self.store.append(preview)
        self.assertEqual([note.french for note in result.added], ["bonjour", "Je suis ici"])
        self.assertEqual(result.added[0].category, "sentence")
        self.assertEqual(result.skipped, 1)
        self.assertEqual(self.store.load(), result.added)
        self.assertTrue(self.path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertFalse(self.store.backup_path.exists())
        self.assert_clean()

    def test_batch_duplicates_are_checked_even_if_marked_new(self):
        result = self.store.append(
            [Candidate("école", "word", "new"), Candidate(" E\u0301COLE ", "word", "new")]
        )
        self.assertEqual(len(result.added), 1)
        self.assertEqual(result.skipped, 1)

    def test_successful_saves_keep_history_in_one_current_csv(self):
        first = self.store.append(self.store.preview("bonjour"))
        second = self.store.append(self.store.preview("merci\nJe suis ici"))
        self.assertEqual(self.store.load(), first.added + second.added)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])
        self.assertFalse(self.store.backup_path.exists())
        self.assert_clean()

    def test_successful_save_removes_only_matching_legacy_backup(self):
        original = make_note("bonjour")
        self.write_notes([original])
        self.store.backup_path.write_bytes(b"legacy backup")
        unrelated = (
            self.path.parent / "other.csv.bak",
            self.path.parent / "notes.csv.bak.old",
            self.path.parent / "other.csv",
        )
        for other in unrelated:
            other.write_bytes(b"keep unrelated data")
        result = self.store.append(self.store.preview("merci"))
        self.assertEqual(self.store.load(), [original] + result.added)
        self.assertFalse(self.store.backup_path.exists())
        for other in unrelated:
            self.assertEqual(other.read_bytes(), b"keep unrelated data")
        self.assert_clean()

    def test_save_reloads_after_preview(self):
        preview = self.store.preview("bonjour\nmerci")
        external = make_note("BONJOUR")
        self.write_notes([external])
        result = self.store.append(preview)
        self.assertEqual([note.french for note in result.added], ["merci"])
        self.assertEqual(result.skipped, 1)
        self.assertEqual(self.store.load()[0], external)
        self.assertFalse(self.store.backup_path.exists())
        self.assert_clean()

    def test_zero_new_does_not_touch_csv_or_backup(self):
        self.store.append(self.store.preview("bonjour"))
        self.store.append(self.store.preview("merci"))
        self.store.backup_path.write_bytes(b"keep legacy backup on a no-op")
        original = self.path.read_bytes()
        backup = self.store.backup_path.read_bytes()
        csv_stat = self.path.stat().st_mtime_ns
        backup_stat = self.store.backup_path.stat().st_mtime_ns
        result = self.store.append(self.store.preview("BONJOUR\nMERCI\nbonjour"))
        self.assertEqual(result.added, [])
        self.assertEqual(result.skipped, 3)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.store.backup_path.read_bytes(), backup)
        self.assertEqual(self.path.stat().st_mtime_ns, csv_stat)
        self.assertEqual(self.store.backup_path.stat().st_mtime_ns, backup_stat)
        self.assert_clean()

    def test_all_new_but_now_existing_does_not_touch_files(self):
        preview = self.store.preview("bonjour")
        self.write_notes([make_note("BONJOUR")])
        self.store.backup_path.write_bytes(b"older backup")
        original = self.path.read_bytes()
        result = self.store.append(preview)
        self.assertEqual(result.added, [])
        self.assertEqual(result.skipped, 1)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.store.backup_path.read_bytes(), b"older backup")
        self.assert_clean()

    def test_multiline_comma_quotes_are_preserved(self):
        note = make_note('Il dit : "Bonjour, ami."\nEt il sourit.', "sentence")
        self.write_notes([note])
        self.assertEqual(self.store.load(), [note])
        result = self.store.append(self.store.preview("merci"))
        self.assertEqual(self.store.load(), [note] + result.added)
        self.assertFalse(self.store.backup_path.exists())
        self.assert_clean()

    def test_different_fd_and_path_signatures_do_not_report_false_edits(self):
        real_fstat = os.fstat
        original_note = make_note("bonjour")
        # Windows Python 3.12 can expose ChangeTime through fstat(), but
        # CreationTime through stat().  Other filesystem/API differences should
        # also remain harmless as long as each API's own result stays stable.
        variants = (
            {"st_ctime_ns": 1_000_000_000},
            {"st_dev": 1 << 48, "st_ino": 1 << 96, "st_mtime_ns": 100},
        )
        for differences in variants:
            with self.subTest(differences=differences):
                self.write_notes([original_note])

                def distinct_fd_stat(descriptor):
                    actual = real_fstat(descriptor)
                    fields = {
                        name: getattr(actual, name)
                        for name in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
                    }
                    for name, offset in differences.items():
                        fields[name] += offset
                    return SimpleNamespace(**fields)

                with patch("french_notes.core.os.fstat", side_effect=distinct_fd_stat):
                    self.assertEqual(self.store.load(), [original_note])
                    result = self.store.append(self.store.preview("merci"))
                    self.assertEqual([note.french for note in result.added], ["merci"])
                    self.assertEqual(self.store.load(), [original_note] + result.added)
                self.assertFalse(self.store.backup_path.exists())
                self.assert_clean()

    def test_fd_metadata_change_during_read_is_still_detected(self):
        self.write_notes([make_note("bonjour")])
        actual = self.path.stat()
        fields = {
            name: getattr(actual, name)
            for name in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        }
        before = SimpleNamespace(**fields)
        fields["st_mtime_ns"] += 1_000_000_000
        after = SimpleNamespace(**fields)
        with patch("french_notes.core.os.fstat", side_effect=[before, after]):
            with self.assertRaisesRegex(StoreError, "a changé pendant sa lecture"):
                self.store.load()

    def test_path_replacement_during_read_is_still_detected(self):
        self.write_notes([make_note("bonjour")])
        real_stat = Path.stat
        queries = 0

        def changed_path_stat(path, *args, **kwargs):
            nonlocal queries
            actual = real_stat(path, *args, **kwargs)
            if path != self.path or kwargs.get("follow_symlinks") is False:
                return actual
            queries += 1
            if queries != 2:
                return actual
            fields = {
                name: getattr(actual, name)
                for name in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
            }
            fields["st_ino"] += 1
            return SimpleNamespace(**fields)

        with patch("french_notes.core.Path.stat", autospec=True, side_effect=changed_path_stat):
            with self.assertRaisesRegex(StoreError, "a changé pendant sa lecture"):
                self.store.load()

    def test_file_disappearing_after_initial_stat_is_not_treated_as_empty(self):
        self.write_notes([make_note("bonjour")])
        with patch("french_notes.core.Path.open", side_effect=FileNotFoundError("removed")):
            with self.assertRaisesRegex(StoreError, "a changé pendant sa lecture"):
                self.store.load()

    def test_existing_lock_is_not_deleted(self):
        self.store.lock_path.write_text("pid=123\n", encoding="utf-8")
        with self.assertRaisesRegex(StoreError, "supprimer manuellement le fichier de verrouillage") as caught:
            self.store.append([Candidate("bonjour", "word", "new")])
        error = caught.exception
        self.assertEqual(error.key, "csv_lock_exists")
        self.assertIn("另一个实例正在保存", error.localized_message("zh"))
        self.assertIn("Another instance is saving", error.localized_message("en"))
        self.assertNotIn("Fermez les autres", error.localized_message("zh"))
        self.assertNotIn("Fermez les autres", error.localized_message("en"))
        self.assertEqual(self.store.lock_path.read_text(encoding="utf-8"), "pid=123\n")
        self.assertFalse(self.path.exists())

    def test_second_instance_cannot_save_during_first_instance_lock(self):
        second_store = CSVStore(self.path)
        with self.store._lock():
            with self.assertRaisesRegex(StoreError, "une autre instance"):
                second_store.append([Candidate("bonjour", "word", "new")])
            self.assertTrue(self.store.lock_path.exists())
        self.assertFalse(self.path.exists())
        self.assert_clean()

    def test_invalid_candidates_do_not_modify_csv(self):
        self.write_notes([make_note("bonjour")])
        original = self.path.read_bytes()
        for candidate in (
            Candidate("merci", "invalid", "new"),
            Candidate("1234", "word", "new"),
            Candidate("merci", "word", "invalid"),
            Candidate("merci\x00", "word", "new"),
        ):
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    self.store.append([candidate])
                self.assertEqual(self.path.read_bytes(), original)
                self.assert_clean()

    def test_damaged_or_malicious_csv_does_not_overwrite_data(self):
        good = make_note("bonjour")
        invalid_id = make_note("bonjour")
        invalid_id.note_id = "=HYPERLINK(\"https://example.invalid\")"
        invalid_category = make_note("bonjour")
        invalid_category.category = "other"
        invalid_time = make_note("bonjour")
        invalid_time.created_at = "yesterday"
        invalid_text = make_note("12,3")
        nul_text = make_note("bonjour\x00")
        xml_control_text = make_note("bonjour\x0b")
        duplicate_id = make_note("merci")
        duplicate_id.note_id = good.note_id
        cases = [
            b"",
            b"\xef\xbb\xbf",
            b"\xff\xfe broken encoding",
            csv_bytes([good], header=("french", "id", "category", "created_at")),
            csv_bytes([good]) + b"too,few,fields\r\n",
            csv_bytes([good]) + b"too,many,fields,in,this,row\r\n",
            csv_bytes([good]) + b'"unterminated field\r\n',
            csv_bytes([invalid_id]),
            csv_bytes([invalid_category]),
            csv_bytes([invalid_time]),
            csv_bytes([invalid_text]),
            csv_bytes([nul_text]),
            csv_bytes([xml_control_text]),
            csv_bytes([good, duplicate_id]),
            csv_bytes([good]) + b"\r\n",
        ]
        for data in cases:
            with self.subTest(data=data):
                self.path.write_bytes(data)
                self.store.backup_path.write_bytes(b"keep existing backup")
                with self.assertRaises(StoreError):
                    self.store.load()
                with self.assertRaises(StoreError):
                    self.store.append([Candidate("merci", "word", "new")])
                self.assertEqual(self.path.read_bytes(), data)
                self.assertEqual(self.store.backup_path.read_bytes(), b"keep existing backup")
                self.assert_clean()

    def test_atomic_replace_failure_keeps_original_and_cleans_up(self):
        self.write_notes([make_note("bonjour")])
        self.store.backup_path.write_bytes(b"keep legacy backup")
        original = self.path.read_bytes()
        real_replace = os.replace

        def fail_csv_replace(source, destination):
            if Path(destination) == self.path:
                raise PermissionError("simulated access denied")
            return real_replace(source, destination)

        with patch("french_notes.core.os.replace", side_effect=fail_csv_replace):
            with self.assertRaisesRegex(StoreError, "Impossible d'enregistrer le fichier CSV") as caught:
                self.store.append([Candidate("merci", "word", "new")])
        self.assertIsNone(caught.exception.saved_result)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.store.backup_path.read_bytes(), b"keep legacy backup")
        self.assert_clean()

    def test_first_save_replace_failure_does_not_leave_csv_or_temp_files(self):
        with patch("french_notes.core.os.replace", side_effect=PermissionError("denied")):
            with self.assertRaises(StoreError) as caught:
                self.store.append([Candidate("bonjour", "word", "new")])
        self.assertIsNone(caught.exception.saved_result)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.store.backup_path.exists())
        self.assert_clean()

    def test_lock_cleanup_failure_reports_already_saved_result(self):
        real_unlink = Path.unlink

        def fail_lock_unlink(path, *args, **kwargs):
            if path == self.store.lock_path:
                raise PermissionError("simulated cleanup failure")
            return real_unlink(path, *args, **kwargs)

        with patch("french_notes.core.Path.unlink", autospec=True, side_effect=fail_lock_unlink):
            with self.assertRaisesRegex(StoreError, "Les notes ont été enregistrées dans le CSV") as caught:
                self.store.append([Candidate("bonjour", "word", "new")])
        saved_result = caught.exception.saved_result
        self.assertIsNotNone(saved_result)
        self.assertEqual(self.store.load(), saved_result.added)
        self.assertEqual(saved_result.skipped, 0)
        self.assertEqual(caught.exception.key, "csv_lock_cleanup")
        self.assertIn("笔记已保存到 CSV", caught.exception.localized_message("zh"))
        self.assertIn("无法删除锁文件", caught.exception.localized_message("zh"))
        self.assertIn("notes have been saved", caught.exception.localized_message("en"))
        self.assertIn("lock file could not be deleted", caught.exception.localized_message("en"))
        self.assertTrue(self.store.lock_path.exists())
        self.store.lock_path.unlink()
        self.assert_clean()

    def test_lock_cleanup_failure_does_not_hide_original_save_failure(self):
        self.write_notes([make_note("bonjour")])
        original = self.path.read_bytes()
        real_unlink = Path.unlink

        def fail_lock_unlink(path, *args, **kwargs):
            if path == self.store.lock_path:
                raise PermissionError("simulated cleanup failure")
            return real_unlink(path, *args, **kwargs)

        with patch.object(self.store, "_stage_notes", side_effect=OSError("original write failure")):
            with patch("french_notes.core.Path.unlink", autospec=True, side_effect=fail_lock_unlink):
                with self.assertRaises(StoreError) as caught:
                    self.store.append([Candidate("merci", "word", "new")])
        self.assertIn("original write failure", str(caught.exception))
        self.assertIn("le fichier de verrouillage ne peut pas être supprimé", str(caught.exception))
        self.assertIsNone(caught.exception.saved_result)
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertEqual(caught.exception.key, "csv_save_failed")
        self.assertIn("无法保存 CSV 文件", caught.exception.localized_message("zh"))
        self.assertIn("保存未完成", caught.exception.localized_message("zh"))
        self.assertIn("另一个问题", caught.exception.localized_message("zh"))
        self.assertIn("Unable to save the CSV file", caught.exception.localized_message("en"))
        self.assertIn("Saving did not complete", caught.exception.localized_message("en"))
        self.assertNotIn("Autre problème", caught.exception.localized_message("en"))
        self.assertEqual(self.path.read_bytes(), original)
        self.store.lock_path.unlink()
        self.assert_clean()

    def test_staging_failure_keeps_original_and_old_backup(self):
        self.write_notes([make_note("bonjour")])
        self.store.backup_path.write_bytes(b"older backup")
        original = self.path.read_bytes()
        with patch.object(self.store, "_stage_notes", side_effect=OSError("staging failed")):
            with self.assertRaises(StoreError):
                self.store.append([Candidate("merci", "word", "new")])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.store.backup_path.read_bytes(), b"older backup")
        self.assert_clean()

    def test_legacy_backup_cleanup_failure_reports_already_saved_result(self):
        original = make_note("bonjour")
        self.write_notes([original])
        self.store.backup_path.write_bytes(b"keep legacy backup")
        real_unlink = Path.unlink

        def fail_backup_unlink(path, *args, **kwargs):
            if path == self.store.backup_path:
                raise PermissionError("simulated backup cleanup failure")
            return real_unlink(path, *args, **kwargs)

        with patch("french_notes.core.Path.unlink", autospec=True, side_effect=fail_backup_unlink):
            with self.assertRaisesRegex(StoreError, "l'ancienne sauvegarde") as caught:
                self.store.append([Candidate("merci", "word", "new")])
        result = caught.exception.saved_result
        self.assertIsNotNone(result)
        self.assertEqual(self.store.load(), [original] + result.added)
        self.assertEqual([note.french for note in result.added], ["merci"])
        self.assertEqual(result.skipped, 0)
        self.assertIsInstance(caught.exception.__cause__, PermissionError)
        self.assertEqual(caught.exception.key, "csv_backup_cleanup")
        self.assertIn("无法删除旧备份", caught.exception.localized_message("zh"))
        self.assertIn("old backup could not be deleted", caught.exception.localized_message("en"))
        self.assertEqual(self.store.backup_path.read_bytes(), b"keep legacy backup")
        self.assert_clean()

    def test_backup_and_lock_cleanup_failures_keep_committed_result(self):
        original = make_note("bonjour")
        self.write_notes([original])
        self.store.backup_path.write_bytes(b"keep legacy backup")
        real_unlink = Path.unlink

        def fail_cleanup_unlink(path, *args, **kwargs):
            if path in (self.store.backup_path, self.store.lock_path):
                raise PermissionError(f"simulated cleanup failure for {path.name}")
            return real_unlink(path, *args, **kwargs)

        with patch("french_notes.core.Path.unlink", autospec=True, side_effect=fail_cleanup_unlink):
            with self.assertRaises(StoreError) as caught:
                self.store.append([Candidate("merci", "word", "new")])
        result = caught.exception.saved_result
        self.assertIsNotNone(result)
        self.assertEqual(self.store.load(), [original] + result.added)
        self.assertIn("l'ancienne sauvegarde", str(caught.exception))
        self.assertIn("le fichier de verrouillage ne peut pas être supprimé", str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, PermissionError)
        chinese = caught.exception.localized_message("zh")
        english = caught.exception.localized_message("en")
        self.assertIn("笔记已保存到 CSV", chinese)
        self.assertIn("无法删除旧备份", chinese)
        self.assertIn("无法删除锁文件", chinese)
        self.assertIn("另一个问题", chinese)
        self.assertIn("old backup could not be deleted", english)
        self.assertIn("lock file could not be deleted", english)
        self.assertIn("Additional problem", english)
        for message in (chinese, english):
            self.assertNotIn("Les notes", message)
            self.assertNotIn("Autre problème", message)
            self.assertNotIn("Détail", message)
        self.assertEqual(self.store.backup_path.read_bytes(), b"keep legacy backup")
        self.assertTrue(self.store.lock_path.exists())
        self.store.lock_path.unlink()
        self.assert_clean()

    def test_external_modification_while_staging_is_detected(self):
        original_note = make_note("bonjour")
        external_note = make_note("salut")
        self.write_notes([original_note])
        self.store.backup_path.write_bytes(b"older backup")
        real_stage = self.store._stage_notes

        def externally_edit(notes):
            staged = real_stage(notes)
            self.write_notes([original_note, external_note])
            return staged

        with patch.object(self.store, "_stage_notes", side_effect=externally_edit):
            with self.assertRaisesRegex(StoreError, "modifié par un autre programme"):
                self.store.append([Candidate("merci", "word", "new")])
        self.assertEqual(self.store.load(), [original_note, external_note])
        self.assertEqual(self.store.backup_path.read_bytes(), b"older backup")
        self.assert_clean()

    def test_changed_bytes_are_detected_even_when_path_metadata_is_unchanged(self):
        self.write_notes([make_note("bonjour")])
        original = self.path.read_bytes()
        original_stat = self.path.stat()
        changed = original.replace(b"bonjour", b"bonsoir")
        self.assertEqual(len(changed), len(original))
        self.store.backup_path.write_bytes(b"older backup")
        real_stat = Path.stat
        real_stage = self.store._stage_notes

        def unchanged_path_stat(path, *args, **kwargs):
            if path == self.path:
                return original_stat
            return real_stat(path, *args, **kwargs)

        def externally_edit(notes):
            staged = real_stage(notes)
            self.path.write_bytes(changed)
            return staged

        with patch("french_notes.core.Path.stat", autospec=True, side_effect=unchanged_path_stat):
            with patch.object(self.store, "_stage_notes", side_effect=externally_edit):
                with self.assertRaisesRegex(StoreError, "modifié par un autre programme"):
                    self.store.append([Candidate("merci", "word", "new")])
        self.assertEqual(self.path.read_bytes(), changed)
        self.assertEqual(self.store.backup_path.read_bytes(), b"older backup")
        self.assert_clean()

    def test_external_creation_while_staging_is_detected(self):
        external_note = make_note("salut")
        real_stage = self.store._stage_notes

        def externally_create(notes):
            staged = real_stage(notes)
            self.write_notes([external_note])
            return staged

        with patch.object(self.store, "_stage_notes", side_effect=externally_create):
            with self.assertRaisesRegex(StoreError, "modifié par un autre programme"):
                self.store.append([Candidate("merci", "word", "new")])
        self.assertEqual(self.store.load(), [external_note])
        self.assertFalse(self.store.backup_path.exists())
        self.assert_clean()

    def test_fsync_failure_keeps_original_and_cleans_up(self):
        self.write_notes([make_note("bonjour")])
        self.store.backup_path.write_bytes(b"keep legacy backup")
        original = self.path.read_bytes()
        real_fsync = os.fsync
        calls = 0

        def fail_csv_fsync(descriptor):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated disk failure")
            return real_fsync(descriptor)

        with patch("french_notes.core.os.fsync", side_effect=fail_csv_fsync):
            with self.assertRaises(StoreError):
                self.store.append([Candidate("merci", "word", "new")])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.store.backup_path.read_bytes(), b"keep legacy backup")
        self.assert_clean()

    def test_utf8_without_bom_is_readable(self):
        note = make_note("été")
        self.path.write_bytes(csv_bytes([note])[3:])
        self.assertEqual(self.store.load(), [note])


if __name__ == "__main__":
    unittest.main()
