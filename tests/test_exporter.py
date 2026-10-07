"""Word export checks that do not require a running desktop Word instance."""

from __future__ import annotations

import builtins
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from french_notes.core import Note
from french_notes.exporter import export_docx


NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"


def paragraph_text(paragraph: ET.Element) -> str:
    pieces = []
    # Paragraph properties can contain w:tab tab-stop definitions, which are
    # layout metadata rather than visible tabs inside a text run.
    for run in paragraph.iter(W + "r"):
        for element in run.iter():
            if element.tag == W + "t":
                pieces.append(element.text or "")
            elif element.tag == W + "tab":
                pieces.append("\t")
            elif element.tag == W + "br":
                pieces.append("\n")
    return "".join(pieces)


class ExporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "notes.docx"
        self.notes = [
            Note("sentence-1", "sentence", "Où est l’école ?\nÀ côté du café.", "2026-10-07T12:00:00"),
            Note("word-1", "word", "cœur", "2026-10-07T12:01:00"),
            Note("word-2", "word", "Éléphant", "2026-10-07T12:02:00"),
            Note("sentence-2", "sentence", "Je voudrais un café, s’il vous plaît.", "2026-10-07T12:03:00"),
        ]

    def xml(self, member: str = "word/document.xml") -> ET.Element:
        with ZipFile(self.path) as archive:
            self.assertIsNone(archive.testzip())
            return ET.fromstring(archive.read(member))

    def test_export_contains_every_note_grouped_with_preserved_unicode(self) -> None:
        self.assertEqual(export_docx(self.notes, self.path), self.path)
        root = self.xml()
        paragraphs = root.findall("./w:body/w:p", NS)
        self.assertEqual(
            [paragraph_text(paragraph) for paragraph in paragraphs],
            [
                "Notes de français",
                "4 notes enregistrées : 2 mots et 2 phrases. Le contenu est regroupé par catégorie.",
                "Mots",
                "1.\tcœur",
                "2.\tÉléphant",
                "Phrases",
                "1.\tOù est l’école ?\nÀ côté du café.",
                "2.\tJe voudrais un café, s’il vous plaît.",
            ],
        )
        self.assertIsNone(root.find(".//w:tbl", NS))
        self.assertEqual(
            paragraphs[0].find("w:pPr/w:pStyle", NS).get(W + "val"), "Title"
        )
        self.assertEqual(
            paragraphs[2].find("w:pPr/w:pStyle", NS).get(W + "val"), "Heading1"
        )

    def test_document_uses_a4_margins_and_black_bilingual_styles(self) -> None:
        export_docx(self.notes, self.path)
        document = self.xml()
        size = document.find("./w:body/w:sectPr/w:pgSz", NS)
        self.assertAlmostEqual(int(size.get(W + "w")), 11906, delta=1)
        self.assertAlmostEqual(int(size.get(W + "h")), 16838, delta=1)
        margins = document.find("./w:body/w:sectPr/w:pgMar", NS)
        for direction in ("top", "right", "bottom", "left"):
            self.assertAlmostEqual(int(margins.get(W + direction)), 1134, delta=1)
        styles = self.xml("word/styles.xml")
        for style_id in ("Normal", "Title", "Heading1"):
            style = styles.find(f"w:style[@w:styleId='{style_id}']", NS)
            properties = style.find("w:rPr", NS)
            self.assertEqual(properties.find("w:color", NS).get(W + "val"), "000000")
            fonts = properties.find("w:rFonts", NS)
            self.assertEqual(fonts.get(W + "ascii"), "Arial")
            self.assertEqual(fonts.get(W + "hAnsi"), "Arial")
            self.assertEqual(fonts.get(W + "eastAsia"), "Microsoft YaHei")
            self.assertIsNone(fonts.get(W + "asciiTheme"))
            self.assertEqual(properties.find("w:lang", NS).get(W + "val"), "fr-FR")
            self.assertIsNone(style.find("w:pPr/w:pBdr", NS))

    def test_empty_category_is_explicit_and_numbering_starts_at_one(self) -> None:
        export_docx([self.notes[1]], self.path)
        paragraphs = self.xml().findall("./w:body/w:p", NS)
        texts = [paragraph_text(paragraph) for paragraph in paragraphs]
        self.assertIn("1.\tcœur", texts)
        self.assertEqual(texts[-2:], ["Phrases", "Aucune phrase enregistrée."])
        self.assertEqual(
            texts[1],
            "1 note enregistrée : 1 mot et 0 phrase. Le contenu est regroupé par catégorie.",
        )

    def test_sentence_only_export_uses_singular_and_empty_word_message(self) -> None:
        export_docx([self.notes[0]], self.path)
        texts = [paragraph_text(paragraph) for paragraph in self.xml().findall("./w:body/w:p", NS)]
        self.assertEqual(
            texts[1],
            "1 note enregistrée : 0 mot et 1 phrase. Le contenu est regroupé par catégorie.",
        )
        self.assertEqual(texts[2:4], ["Mots", "Aucun mot enregistré."])

    def test_mixed_single_categories_use_plural_total_and_singular_categories(self) -> None:
        export_docx(self.notes[:2], self.path)
        texts = [paragraph_text(paragraph) for paragraph in self.xml().findall("./w:body/w:p", NS)]
        self.assertEqual(
            texts[1],
            "2 notes enregistrées : 1 mot et 1 phrase. Le contenu est regroupé par catégorie.",
        )

    def test_empty_notes_leave_existing_document_untouched(self) -> None:
        self.path.write_bytes(b"original document")
        with self.assertRaisesRegex(ValueError, "Aucune note à exporter"):
            export_docx([], self.path)
        self.assertEqual(self.path.read_bytes(), b"original document")
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_non_docx_destination_cannot_overwrite_csv(self) -> None:
        csv_path = self.root / "notes.csv"
        csv_path.write_bytes(b"source csv")
        with self.assertRaisesRegex(ValueError, "Le fichier Word exporté doit porter l’extension"):
            export_docx(self.notes, csv_path)
        self.assertEqual(csv_path.read_bytes(), b"source csv")
        self.assertEqual(list(self.root.iterdir()), [csv_path])

    def test_invalid_category_reports_a_french_validation_error(self) -> None:
        invalid_note = Note("invalid", "unknown", "café", "2026-10-07T12:00:00")
        with self.assertRaisesRegex(ValueError, "Chaque note doit appartenir à la catégorie « mot » ou « phrase »"):
            export_docx([invalid_note], self.path)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_successful_export_replaces_old_document_and_leaves_no_temp(self) -> None:
        self.path.write_bytes(b"old document")
        export_docx(self.notes, self.path)
        self.xml()
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_replace_failure_keeps_existing_document_and_cleans_temp(self) -> None:
        self.path.write_bytes(b"original document")
        with patch("french_notes.exporter.os.replace", side_effect=PermissionError("Word is open")):
            with self.assertRaises(PermissionError):
                export_docx(self.notes, self.path)
        self.assertEqual(self.path.read_bytes(), b"original document")
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_fsync_failure_keeps_existing_document_and_cleans_temp(self) -> None:
        self.path.write_bytes(b"original document")
        with patch("french_notes.exporter.os.fsync", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                export_docx(self.notes, self.path)
        self.assertEqual(self.path.read_bytes(), b"original document")
        self.assertEqual(list(self.root.iterdir()), [self.path])

    def test_docx_import_is_deferred_until_export(self) -> None:
        module_path = Path(__file__).resolve().parents[1] / "french_notes" / "exporter.py"
        specification = importlib.util.spec_from_file_location("exporter_import_test", module_path)
        module = importlib.util.module_from_spec(specification)
        original_import = builtins.__import__

        def reject_docx(name, *args, **kwargs):
            if name == "docx" or name.startswith("docx."):
                raise AssertionError("python-docx was imported eagerly")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=reject_docx):
            specification.loader.exec_module(module)
        self.assertTrue(callable(module.export_docx))


if __name__ == "__main__":
    unittest.main()
