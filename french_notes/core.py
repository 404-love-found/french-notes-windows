"""Local CSV storage and deterministic classification for French notes.

This module deliberately uses only Python's standard library.  The lock file is
shared by cooperating instances of the application.  External file edits are
checked again immediately before replacement.
"""

from __future__ import annotations

import csv
import io
import os
import tempfile
import unicodedata
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


CATEGORIES = ("word", "sentence")
CSV_HEADER = ("id", "category", "french", "created_at")
_STAT_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
_SENTENCE_PUNCTUATION = frozenset(".,;:!?…。！？；：，")
_CANDIDATE_STATUSES = frozenset(("new", "existing", "batch"))


class StoreError(Exception):
    """A storage problem whose message can be displayed directly to the user."""

    def __init__(self, message: str, *, saved_result: SaveResult | None = None):
        super().__init__(message)
        # A cleanup problem after a successful commit is distinguishable from
        # a save failure, so callers can report the real outcome without asking
        # the user to resubmit notes that are already on disk.
        self.saved_result = saved_result


@dataclass
class Note:
    note_id: str
    category: str
    french: str
    created_at: str


@dataclass
class Candidate:
    french: str
    category: str
    status: str


@dataclass
class SaveResult:
    added: list[Note]
    skipped: int


@dataclass(frozen=True)
class _Snapshot:
    data: bytes | None
    signature: tuple[int, ...] | None


@dataclass
class _LockState:
    saved_result: SaveResult | None = None


def clean_text(text: str) -> str:
    """Use NFC and one space per whitespace run, preserving case and punctuation."""
    if not isinstance(text, str):
        raise ValueError("Le contenu en français doit être du texte.")
    for char in text:
        if unicodedata.category(char) in ("Cc", "Cs") and char not in "\t\r\n":
            raise ValueError(
                "Le contenu contient des caractères de contrôle non pris en charge. "
                "Supprimez-les, puis réessayez."
            )
    return " ".join(unicodedata.normalize("NFC", text).split())


def normalize_key(text: str) -> str:
    """Duplicate key: ignore whitespace/case, retain accents and punctuation."""
    return unicodedata.normalize("NFC", clean_text(text).casefold())


def _valid_french(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        raise ValueError("Le contenu en français ne peut pas être vide.")
    if not any(char.isalpha() for char in cleaned):
        raise ValueError(
            "Chaque note doit contenir au moins une lettre ; "
            "les nombres ou la ponctuation seuls ne suffisent pas."
        )
    return cleaned


def classify(text: str) -> str:
    """Classify one token as a word; spaces or sentence punctuation mean sentence.

    Apostrophes and hyphens do not split a word.  This is a simple, editable
    heuristic, rather than a grammatical judgement about whether a phrase is a
    complete French sentence.
    """
    cleaned = _valid_french(text)
    if " " in cleaned or any(char in _SENTENCE_PUNCTUATION for char in cleaned):
        return "sentence"
    return "word"


def _signature(stat_result: os.stat_result) -> tuple[int, ...]:
    return tuple(getattr(stat_result, name) for name in _STAT_FIELDS)


class CSVStore:
    """Read, preview, and atomically add notes to a local UTF-8 CSV file."""

    def __init__(self, path: Path):
        self.path = Path(path).expanduser().absolute()
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.backup_path = self.path.with_name(self.path.name + ".bak")

    def _read_snapshot(self) -> _Snapshot:
        path_observed = False
        try:
            if self.path.is_symlink():
                raise StoreError(
                    "Le chemin du CSV est un lien symbolique. "
                    "Sélectionnez le fichier CSV réel."
                )
            before_path = _signature(self.path.stat())
            path_observed = True
            with self.path.open("rb") as source:
                before_fd = _signature(os.fstat(source.fileno()))
                data = source.read()
                after_fd = _signature(os.fstat(source.fileno()))
            after_path = _signature(self.path.stat())
        except FileNotFoundError:
            # A file disappearing midway through reading is a concurrent edit,
            # not an empty store.  Only the initial path query may mean absence.
            if path_observed:
                raise StoreError(
                    "Le fichier CSV a changé pendant sa lecture. "
                    "Actualisez l'aperçu, puis réessayez."
                ) from None
            return _Snapshot(None, None)
        except OSError as exc:
            raise StoreError(f"Impossible de lire le fichier CSV : {exc}") from exc
        # Compare each API with itself.  On Windows Python 3.12, path stat()
        # keeps creation time in st_ctime, while fstat() can report ChangeTime.
        # Comparing those signatures directly falsely flags atomic replacements.
        # Path queries still detect replacement; fd queries detect edits during
        # the read.  Save-time checks also compare the complete snapshot bytes.
        if before_fd != after_fd or before_path != after_path:
            raise StoreError(
                "Le fichier CSV a changé pendant sa lecture. "
                "Actualisez l'aperçu, puis réessayez."
            )
        return _Snapshot(data, after_path)

    def _parse_snapshot(self, snapshot: _Snapshot) -> list[Note]:
        if snapshot.data is None:
            return []
        try:
            decoded = snapshot.data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise StoreError(
                "L'encodage du CSV est invalide. Enregistrez le fichier en UTF-8. "
                "Le fichier d'origine n'a pas été modifié."
            ) from exc

        notes: list[Note] = []
        ids: set[str] = set()
        try:
            reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
            header = next(reader, None)
            if header != list(CSV_HEADER):
                raise StoreError(
                    "L'en-tête du CSV doit contenir, dans cet ordre : "
                    "id,category,french,created_at. Le fichier d'origine n'a pas été modifié."
                )
            for row in reader:
                line_number = reader.line_num
                if len(row) != len(CSV_HEADER):
                    raise StoreError(
                        f"Ligne {line_number} du CSV : nombre de champs incorrect "
                        "(4 champs attendus). Le fichier d'origine n'a pas été modifié."
                    )
                note = Note(*row)
                try:
                    parsed_id = uuid.UUID(note.note_id)
                    if str(parsed_id) != note.note_id:
                        raise ValueError(
                            "L'identifiant doit être un UUID au format standard, en minuscules."
                        )
                    if note.note_id in ids:
                        raise ValueError("Un identifiant est présent plusieurs fois.")
                    if note.category not in CATEGORIES:
                        raise ValueError("La catégorie doit être « word » ou « sentence ».")
                    _valid_french(note.french)
                    if "T" not in note.created_at:
                        raise ValueError(
                            "La date de création doit inclure une date et une heure au format ISO."
                        )
                    timestamp = note.created_at
                    if timestamp.endswith("Z"):
                        timestamp = timestamp[:-1] + "+00:00"
                    datetime.fromisoformat(timestamp)
                except (ValueError, TypeError, AttributeError) as exc:
                    raise StoreError(
                        f"Ligne {line_number} du CSV : données invalides. "
                        f"{exc} Le fichier d'origine n'a pas été modifié."
                    ) from exc
                ids.add(note.note_id)
                notes.append(note)
        except csv.Error as exc:
            raise StoreError(
                f"Le CSV est mal formé : {exc}. Le fichier d'origine n'a pas été modifié."
            ) from exc
        return notes

    def load(self) -> list[Note]:
        """Return all stored records; a missing file is an empty collection."""
        return self._parse_snapshot(self._read_snapshot())

    def preview(self, text: str) -> list[Candidate]:
        """Split input by line and identify existing and within-batch duplicates."""
        if not isinstance(text, str):
            raise ValueError("La saisie doit être du texte.")
        existing = {normalize_key(note.french) for note in self.load()}
        seen: set[str] = set()
        candidates: list[Candidate] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            try:
                french = clean_text(line)
                if not french:
                    continue
                category = classify(french)
            except ValueError as exc:
                raise ValueError(
                    f"Ligne {line_number} de la saisie : contenu invalide. {exc}"
                ) from exc
            key = normalize_key(french)
            if key in existing:
                status = "existing"
            elif key in seen:
                status = "batch"
            else:
                status = "new"
            candidates.append(Candidate(french, category, status))
            seen.add(key)
        return candidates

    def _assert_unchanged(self, expected: _Snapshot) -> None:
        actual = self._read_snapshot()
        if actual != expected:
            raise StoreError(
                "Le fichier CSV a été modifié par un autre programme. "
                "Enregistrement annulé. Actualisez l'aperçu, puis réessayez."
            )

    @contextmanager
    def _lock(self) -> Iterator[_LockState]:
        """Acquire an exclusive cooperating-process lock; never remove stale locks."""
        token = uuid.uuid4().hex
        payload = (
            f"pid={os.getpid()}\n"
            f"created_at={datetime.now(timezone.utc).isoformat()}\n"
            f"token={token}\n"
        ).encode("utf-8")
        acquired = False
        lock_written = False
        lock_identity: tuple[int, int] | None = None
        pending_error: BaseException | None = None
        state = _LockState()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                descriptor = os.open(
                    self.lock_path,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                    0o600,
                )
            except FileExistsError as exc:
                raise StoreError(
                    "Le fichier CSV est en cours d'enregistrement par une autre instance. "
                    "Fermez les autres instances, puis réessayez. "
                    "Si l'application s'est arrêtée de façon inattendue, vérifiez "
                    "qu'aucun enregistrement n'est en cours avant de supprimer "
                    "manuellement le fichier de verrouillage : "
                    f"{self.lock_path}"
                ) from exc
            acquired = True
            with os.fdopen(descriptor, "wb") as lock_file:
                # Keep identity comparisons within the path-stat API as well.
                stat_result = self.lock_path.stat()
                lock_identity = (stat_result.st_dev, stat_result.st_ino)
                lock_file.write(payload)
                lock_file.flush()
                os.fsync(lock_file.fileno())
            lock_written = True
            yield state
        except OSError as exc:
            pending_error = StoreError(f"Impossible d'enregistrer le fichier CSV : {exc}")
            raise pending_error from exc
        except BaseException as exc:
            pending_error = exc
            raise
        finally:
            if acquired:
                if state.saved_result is None:
                    outcome = "L'enregistrement n'a pas abouti"
                elif state.saved_result.added:
                    outcome = "Les notes ont été enregistrées dans le CSV"
                else:
                    outcome = "Aucune nouvelle note n'a été ajoutée ; le CSV n'a pas été modifié"
                cleanup_message: str | None = None
                try:
                    current_stat = self.lock_path.stat()
                    current_identity = (current_stat.st_dev, current_stat.st_ino)
                    if current_identity != lock_identity or (
                        lock_written and self.lock_path.read_bytes() != payload
                    ):
                        cleanup_message = (
                            f"{outcome}, mais le fichier de verrouillage a été modifié "
                            "par un autre programme et n'a pas été supprimé automatiquement. "
                            "Assurez-vous qu'aucun programme n'enregistre ce CSV, "
                            f"puis vérifiez ce fichier : {self.lock_path}"
                        )
                    else:
                        self.lock_path.unlink()
                except OSError as exc:
                    cleanup_message = (
                        f"{outcome}, mais le fichier de verrouillage ne peut pas être "
                        f"supprimé : {self.lock_path}. Vérifiez qu'aucun programme "
                        "n'enregistre ce CSV avant de le supprimer manuellement. "
                        f"Détail : {exc}"
                    )
                if cleanup_message is not None:
                    if pending_error is None:
                        raise StoreError(cleanup_message, saved_result=state.saved_result)
                    if isinstance(pending_error, (StoreError, ValueError)):
                        # Preserve the original failure and its cause.  Cleanup
                        # diagnostics must not replace the reason saving failed.
                        pending_error.args = (f"{pending_error}\nAutre problème : {cleanup_message}",)
                    elif hasattr(pending_error, "add_note"):
                        pending_error.add_note(cleanup_message)

    def _stage_notes(self, notes: list[Note]) -> Path:
        descriptor, filename = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temporary = Path(filename)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8-sig", newline="") as target:
                writer = csv.writer(target)
                writer.writerow(CSV_HEADER)
                writer.writerows(
                    (note.note_id, note.category, note.french, note.created_at)
                    for note in notes
                )
                target.flush()
                os.fsync(target.fileno())
            return temporary
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def _stage_backup(self, data: bytes) -> Path:
        descriptor, filename = tempfile.mkstemp(
            prefix=f".{self.path.name}.backup.", suffix=".tmp", dir=self.path.parent
        )
        temporary = Path(filename)
        try:
            with os.fdopen(descriptor, "wb") as target:
                target.write(data)
                target.flush()
                os.fsync(target.fileno())
            return temporary
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def append(self, candidates: list[Candidate]) -> SaveResult:
        """Add only new candidates, checking the latest CSV and batch once more."""
        prepared: list[tuple[str, str]] = []
        skipped = 0
        for candidate in candidates:
            if not isinstance(candidate, Candidate):
                raise ValueError("Les données à enregistrer doivent provenir de l'aperçu des notes.")
            if candidate.status not in _CANDIDATE_STATUSES:
                raise ValueError("L'état de l'aperçu est invalide. Actualisez l'aperçu avant d'enregistrer.")
            if candidate.status != "new":
                skipped += 1
                continue
            if candidate.category not in CATEGORIES:
                raise ValueError("La catégorie de la note doit être « word » ou « sentence ».")
            prepared.append((_valid_french(candidate.french), candidate.category))

        # Even a no-op checks the file's format, but creates no lock, directories,
        # CSV, or backup.  This also keeps preview/save failures consistent.
        if not prepared:
            self.load()
            return SaveResult([], skipped)

        with self._lock() as lock_state:
            snapshot = self._read_snapshot()
            notes = self._parse_snapshot(snapshot)
            keys = {normalize_key(note.french) for note in notes}
            added: list[Note] = []
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            for french, category in prepared:
                key = normalize_key(french)
                if key in keys:
                    skipped += 1
                    continue
                note = Note(str(uuid.uuid4()), category, french, timestamp)
                added.append(note)
                keys.add(key)
            if not added:
                result = SaveResult([], skipped)
                lock_state.saved_result = result
                return result

            staged_csv: Path | None = None
            staged_backup: Path | None = None
            try:
                staged_csv = self._stage_notes(notes + added)
                self._assert_unchanged(snapshot)
                if snapshot.data is not None:
                    staged_backup = self._stage_backup(snapshot.data)
                    self._assert_unchanged(snapshot)
                    os.replace(staged_backup, self.backup_path)
                    staged_backup = None
                self._assert_unchanged(snapshot)
                os.replace(staged_csv, self.path)
                staged_csv = None
            finally:
                if staged_csv is not None:
                    staged_csv.unlink(missing_ok=True)
                if staged_backup is not None:
                    staged_backup.unlink(missing_ok=True)
            result = SaveResult(added, skipped)
            lock_state.saved_result = result
            return result
