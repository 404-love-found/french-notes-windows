"""Export saved French notes to a local Word document."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from .core import Note


def export_docx(notes: Sequence[Note], path: Path) -> Path:
    """Export all notes, grouped by category, without risking an existing file.

    ``python-docx`` is imported only when exporting. Saving uses a temporary
    file in the destination directory, so replacing the completed document is
    atomic. An open Word document on Windows can prevent replacement; that
    error is propagated while the original document is retained.
    """
    path = Path(path)
    if path.suffix.lower() != ".docx":
        raise ValueError("Le fichier Word exporté doit porter l’extension .docx.")
    records = tuple(notes)
    if not records:
        raise ValueError("Aucune note à exporter.")
    if any(note.category not in {"word", "sentence"} for note in records):
        raise ValueError("Chaque note doit appartenir à la catégorie « mot » ou « phrase ».")

    # Keep CSV reading and deduplication usable without the optional exporter.
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    document = Document()
    section = document.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin = section.right_margin = Cm(2)

    for style_name in ("Normal", "Title", "Heading 1"):
        style = document.styles[style_name]
        style.font.name = "Arial"
        style.font.color.rgb = RGBColor(0, 0, 0)
        run_properties = style.element.get_or_add_rPr()
        fonts = run_properties.get_or_add_rFonts()
        fonts.set(qn("w:ascii"), "Arial")
        fonts.set(qn("w:hAnsi"), "Arial")
        fonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        # Theme formatting must not override the deliberately chosen fonts.
        for attribute in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme"):
            fonts.attrib.pop(qn(f"w:{attribute}"), None)
        language = run_properties.find(qn("w:lang"))
        if language is None:
            language = OxmlElement("w:lang")
            run_properties.append(language)
        language.set(qn("w:val"), "fr-FR")
        color = run_properties.find(qn("w:color"))
        if color is not None:
            for attribute in ("themeColor", "themeTint", "themeShade"):
                color.attrib.pop(qn(f"w:{attribute}"), None)
        paragraph_properties = style.element.find(qn("w:pPr"))
        if paragraph_properties is not None:
            border = paragraph_properties.find(qn("w:pBdr"))
            if border is not None:
                paragraph_properties.remove(border)

    normal = document.styles["Normal"]
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15
    normal.paragraph_format.widow_control = True
    document.styles["Title"].font.size = Pt(24)
    document.styles["Title"].paragraph_format.space_after = Pt(12)
    document.styles["Heading 1"].font.size = Pt(16)
    document.styles["Heading 1"].paragraph_format.space_before = Pt(12)
    document.styles["Heading 1"].paragraph_format.space_after = Pt(6)

    words = [note for note in records if note.category == "word"]
    sentences = [note for note in records if note.category == "sentence"]
    groups = (
        ("Mots", words, "Aucun mot enregistré."),
        ("Phrases", sentences, "Aucune phrase enregistrée."),
    )
    note_label = "note enregistrée" if len(records) == 1 else "notes enregistrées"
    word_label = "mot" if len(words) < 2 else "mots"
    sentence_label = "phrase" if len(sentences) < 2 else "phrases"
    document.add_paragraph("Notes de français", style="Title")
    document.add_paragraph(
        f"{len(records)} {note_label} : {len(words)} {word_label} et "
        f"{len(sentences)} {sentence_label}. Le contenu est regroupé par catégorie."
    )
    for heading, group, empty_message in groups:
        document.add_heading(heading, level=1)
        if not group:
            document.add_paragraph(empty_message)
            continue
        for number, note in enumerate(group, start=1):
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Cm(0.8)
            paragraph.paragraph_format.first_line_indent = Cm(-0.8)
            paragraph.paragraph_format.tab_stops.add_tab_stop(Cm(0.8))
            # Long sentences may flow across pages instead of leaving gaps.
            paragraph.paragraph_format.keep_together = False
            paragraph.add_run(f"{number}.\t")
            paragraph.add_run(note.french)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as destination:
            document.save(destination)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return path
