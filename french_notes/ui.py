"""Desktop interface. All note content stays on the user's computer."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .core import CSVStore, Candidate, Note, StoreError, normalize_key
from .exporter import export_docx


CATEGORY_LABELS = {"word": "Mot", "sentence": "Phrase"}
CATEGORY_FILTERS = {"Tous": None, "Mots": "word", "Phrases": "sentence"}
STATUS_LABELS = {"new": "À ajouter", "existing": "Déjà dans le CSV", "batch": "Doublon du lot"}


def display_time(value: str) -> str:
    """Show timestamp offsets in the computer's local timezone."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def app_data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "FrenchNotes"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FrenchNotes"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "FrenchNotes"


class FrenchNotesApp:
    def __init__(self, root: tk.Tk, csv_path: Path | None = None) -> None:
        self.root = root
        self.config_path = app_data_dir() / "settings.json"
        self.store = CSVStore(csv_path or self._configured_path())
        self.candidates: list[Candidate] = []
        self.notes: list[Note] = []
        self.search = tk.StringVar()
        self.category_filter = tk.StringVar(value="Tous")
        self.status = tk.StringVar(value="Saisissez une note en français par ligne, puis cliquez sur « Analyser ».")
        self.path_label = tk.StringVar(value=str(self.store.path))
        self.summary = tk.StringVar(value="L’analyse affichera les catégories et les doublons.")
        self.library_summary = tk.StringVar()
        self._setup_style()
        self._build()
        self.refresh_library()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Control-Return>", lambda _event: self.analyze())

    def _configured_path(self) -> Path:
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            stored = data.get("csv_path")
            if isinstance(stored, str) and Path(stored).is_absolute():
                return Path(stored)
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return app_data_dir() / "notes.csv"

    def _setup_style(self) -> None:
        self.root.title("Notes de français · FrenchNotes")
        self.root.geometry("1180x760")
        self.root.minsize(1024, 640)
        font = "Segoe UI" if sys.platform == "win32" else "Helvetica"
        self.root.option_add("*Font", (font, 11))
        self.root.configure(bg="#f3f5f8")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f3f5f8")
        style.configure("TLabel", background="#f3f5f8", foreground="#233047")
        style.configure("Title.TLabel", font=(font, 25, "bold"), foreground="#182b45")
        style.configure("Muted.TLabel", foreground="#5b687a")
        style.configure("Section.TLabel", font=(font, 13, "bold"))
        style.configure("TButton", padding=(12, 8))
        style.configure("Primary.TButton", background="#245a93", foreground="white", padding=(18, 10))
        style.map("Primary.TButton", background=[("disabled", "#bcc6d1"), ("active", "#1a4777")])
        style.configure("Treeview", font=(font, 11), rowheight=33, background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=(font, 11, "bold"), padding=(7, 9))
        style.configure("TNotebook", background="#f3f5f8", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10))

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=22)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 14))
        self.export_button = ttk.Button(header, text="Tout exporter vers Word", command=self.export_all)
        self.export_button.pack(side="right")
        title = ttk.Frame(header)
        title.pack(side="left", fill="x", expand=True)
        ttk.Label(title, text="Notes de français", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title, text="Stockage local · Classement automatique · Ajout sans doublon", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))
        path_row = ttk.Frame(outer)
        path_row.pack(fill="x", pady=(0, 14))
        ttk.Label(path_row, text="Fichier CSV :").pack(side="left")
        ttk.Entry(path_row, textvariable=self.path_label, state="readonly").pack(side="left", fill="x", expand=True, padx=7)
        ttk.Button(path_row, text="Choisir un CSV", command=self.choose_csv).pack(side="left", padx=(3, 6))
        ttk.Button(path_row, text="Ouvrir le dossier", command=self.open_folder).pack(side="left")
        ttk.Label(outer, textvariable=self.status, style="Muted.TLabel", wraplength=960).pack(side="bottom", fill="x", pady=(13, 0))
        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)
        self.intake_tab = ttk.Frame(self.notebook, padding=16)
        self.library_tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(self.intake_tab, text="Saisie par lot")
        self.notebook.add(self.library_tab, text="Notes enregistrées")
        self._build_intake()
        self._build_library()

    @staticmethod
    def _scroll_tree(parent: ttk.Frame, columns: tuple[str, ...]) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        return tree

    def _build_intake(self) -> None:
        columns = ttk.Frame(self.intake_tab)
        columns.pack(fill="both", expand=True)
        columns.columnconfigure(0, weight=2)
        columns.columnconfigure(1, weight=3)
        columns.rowconfigure(0, weight=1)
        left = ttk.Frame(columns, padding=(0, 0, 18, 0))
        right = ttk.Frame(columns)
        left.grid(row=0, column=0, sticky="nsew")
        right.grid(row=0, column=1, sticky="nsew")
        ttk.Label(left, text="1  Saisir vos notes", style="Section.TLabel").pack(anchor="w")
        ttk.Label(left, text="Une note par ligne. Vous pouvez coller plusieurs lignes ; les lignes vides sont ignorées.", style="Muted.TLabel", wraplength=350).pack(anchor="w", pady=(7, 11))
        input_actions = ttk.Frame(left)
        input_actions.pack(side="bottom", fill="x")
        buttons = ttk.Frame(input_actions)
        buttons.pack(fill="x", pady=(12, 9))
        ttk.Button(buttons, text="Analyser", style="Primary.TButton", command=self.analyze).pack(side="left")
        ttk.Button(buttons, text="Effacer", command=self.clear_input).pack(side="right")
        ttk.Label(input_actions, text="La comparaison ignore la casse et les différences d’espacement. Les accents et la ponctuation restent distincts.", style="Muted.TLabel", wraplength=350).pack(anchor="w")
        input_frame = ttk.Frame(left)
        input_frame.pack(fill="both", expand=True)
        self.input = tk.Text(input_frame, wrap="word", undo=True, width=27, height=13, bg="white", fg="#20314b", insertbackground="#20314b", relief="solid", borderwidth=1, padx=12, pady=12)
        input_scroll = ttk.Scrollbar(input_frame, command=self.input.yview)
        self.input.configure(yscrollcommand=input_scroll.set)
        self.input.pack(side="left", fill="both", expand=True)
        input_scroll.pack(side="right", fill="y")
        self.input.bind("<<Modified>>", self._input_changed)
        ttk.Label(right, text="2  Vérifier le classement et les doublons", style="Section.TLabel").pack(anchor="w")
        ttk.Label(right, text="Sélectionnez les nouvelles notes pour corriger leur catégorie, notamment les expressions et les abréviations.", style="Muted.TLabel", wraplength=560).pack(anchor="w", pady=(7, 11))
        preview_actions = ttk.Frame(right)
        preview_actions.pack(side="bottom", fill="x", pady=(10, 0))
        category_buttons = ttk.Frame(preview_actions)
        category_buttons.pack(fill="x", pady=(10, 6))
        ttk.Label(category_buttons, text="Classer la sélection :").pack(side="left")
        ttk.Button(category_buttons, text="Mot", command=lambda: self.set_category("word")).pack(side="left", padx=4)
        ttk.Button(category_buttons, text="Phrase", command=lambda: self.set_category("sentence")).pack(side="left")
        ttk.Label(preview_actions, textvariable=self.summary, style="Muted.TLabel", wraplength=560).pack(anchor="w", pady=(4, 9))
        self.save_button = ttk.Button(preview_actions, text="3  Enregistrer les nouvelles notes", style="Primary.TButton", command=self.save_new, state="disabled")
        self.save_button.pack(fill="x")
        self.preview_tree = self._scroll_tree(right, ("category", "french", "status"))
        for key, label, width in (("category", "Catégorie", 110), ("french", "Contenu en français", 285), ("status", "Résultat", 160)):
            self.preview_tree.heading(key, text=label)
            self.preview_tree.column(key, width=width, minwidth=width, stretch=key == "french", anchor="w")
        self.preview_tree.tag_configure("duplicate", foreground="#7a8491")
        self.preview_tree.bind("<Double-1>", self.show_preview_text)

    def _build_library(self) -> None:
        controls = ttk.Frame(self.library_tab)
        controls.pack(fill="x", pady=(0, 12))
        ttk.Label(controls, text="Rechercher :").pack(side="left")
        ttk.Entry(controls, textvariable=self.search).pack(side="left", fill="x", expand=True, padx=(4, 14))
        ttk.Combobox(controls, values=tuple(CATEGORY_FILTERS), textvariable=self.category_filter, state="readonly", width=9).pack(side="left", padx=(0, 10))
        ttk.Button(controls, text="Actualiser le CSV", command=self.refresh_library).pack(side="left")
        ttk.Label(self.library_tab, textvariable=self.library_summary, style="Muted.TLabel", wraplength=960).pack(side="bottom", anchor="w", pady=(12, 0))
        self.library_tree = self._scroll_tree(self.library_tab, ("category", "french", "created"))
        for key, label, width in (("category", "Catégorie", 110), ("french", "Contenu en français", 620), ("created", "Date d’ajout", 180)):
            self.library_tree.heading(key, text=label)
            self.library_tree.column(key, width=width, minwidth=width, stretch=key == "french")
        self.library_tree.bind("<Double-1>", self.show_library_text)
        self.search.trace_add("write", lambda *_args: self._render_library())
        self.category_filter.trace_add("write", lambda *_args: self._render_library())

    def _input_changed(self, _event: tk.Event | None = None) -> None:
        if self.input.edit_modified():
            self.input.edit_modified(False)
            self._invalidate_preview()

    def _invalidate_preview(self) -> None:
        self.candidates = []
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.save_button.configure(state="disabled")
        self.summary.set("La saisie ou le CSV a changé. Relancez l’analyse.")

    def clear_input(self) -> None:
        self.input.delete("1.0", "end")
        self.input.edit_modified(False)
        self._invalidate_preview()
        self.status.set("La saisie a été effacée. Les notes du CSV sont conservées.")

    def analyze(self) -> None:
        text = self.input.get("1.0", "end-1c")
        if not text.strip():
            self.status.set("Saisissez d’abord des mots ou des phrases en français, une note par ligne.")
            self.input.focus_set()
            return
        # Consume pending Text modification notifications before generating preview.
        self.input.edit_modified(False)
        try:
            candidates = self.store.preview(text)
        except (StoreError, OSError, ValueError, RuntimeError) as error:
            self._invalidate_preview()
            self._error("Analyse impossible", error)
            return
        self.candidates = candidates
        self.preview_tree.delete(*self.preview_tree.get_children())
        for index, item in enumerate(candidates):
            self.preview_tree.insert("", "end", iid=str(index), values=(CATEGORY_LABELS[item.category], item.french, STATUS_LABELS[item.status]), tags=() if item.status == "new" else ("duplicate",))
        new = sum(item.status == "new" for item in candidates)
        existing = sum(item.status == "existing" for item in candidates)
        batch = sum(item.status == "batch" for item in candidates)
        self.summary.set(f"Ajouts : {new}  ·  Notes déjà enregistrées : {existing}  ·  Doublons du lot : {batch}")
        self.save_button.configure(state="normal" if new else "disabled")
        self.status.set("Vérifiez les catégories, puis cliquez sur « Enregistrer les nouvelles notes » pour écrire dans le CSV." if new else "Aucune nouvelle note. Le CSV reste inchangé.")

    def set_category(self, category: str) -> None:
        changed = 0
        for selected in self.preview_tree.selection():
            item = self.candidates[int(selected)]
            if item.status == "new":
                item.category = category
                self.preview_tree.item(selected, values=(CATEGORY_LABELS[category], item.french, STATUS_LABELS[item.status]))
                changed += 1
        self.status.set(f"Notes reclassées : {changed}. Catégorie : {CATEGORY_LABELS[category]}." if changed else "Sélectionnez de nouvelles notes dans l’aperçu. Les notes déjà enregistrées et les doublons restent inchangés.")

    def save_new(self) -> None:
        if not self.candidates:
            return
        cleanup_warning = None
        try:
            result = self.store.append(self.candidates)
        except StoreError as error:
            if error.saved_result is None:
                self._error("Échec de l’enregistrement. La saisie est conservée", error)
                return
            result = error.saved_result
            cleanup_warning = str(error)
        except (OSError, ValueError, RuntimeError) as error:
            self._error("Échec de l’enregistrement. La saisie est conservée", error)
            return
        self.input.delete("1.0", "end")
        self.input.edit_modified(False)
        self._invalidate_preview()
        self.refresh_library()
        self.summary.set(f"Notes enregistrées : {len(result.added)}  ·  Doublons ignorés : {result.skipped}")
        self.status.set(f"Enregistrement terminé. Ajouts : {len(result.added)} ; doublons ignorés : {result.skipped}. Fichier : {self.store.path}")
        if cleanup_warning:
            self.status.set(cleanup_warning)
            messagebox.showwarning("Enregistrement terminé. Vérifiez le fichier de verrouillage", cleanup_warning, parent=self.root)

    def refresh_library(self) -> None:
        try:
            self.notes = self.store.load()
        except (StoreError, OSError, ValueError, RuntimeError) as error:
            self.notes = []
            self._render_library()
            self._error("Lecture du CSV actuel impossible", error)
            return
        self._render_library()

    def _render_library(self) -> None:
        self.library_tree.delete(*self.library_tree.get_children())
        query = normalize_key(self.search.get())
        category = CATEGORY_FILTERS[self.category_filter.get()]
        shown = 0
        for index, note in enumerate(self.notes):
            if category is not None and note.category != category:
                continue
            if query and query not in normalize_key(note.french):
                continue
            self.library_tree.insert("", "end", iid=str(index), values=(CATEGORY_LABELS[note.category], note.french, display_time(note.created_at)))
            shown += 1
        words = sum(note.category == "word" for note in self.notes)
        self.library_summary.set(f"Total : {len(self.notes)}  ·  Mots : {words}  ·  Phrases : {len(self.notes) - words}  ·  Notes affichées : {shown}. Double-cliquez pour lire une note en entier.")
        self.export_button.configure(state="normal" if self.notes else "disabled")

    def choose_csv(self) -> None:
        name = filedialog.asksaveasfilename(parent=self.root, title="Choisir un CSV existant ou créer un nouveau fichier", initialdir=str(self.store.path.parent) if self.store.path.parent.exists() else str(Path.home()), initialfile=self.store.path.name, defaultextension=".csv", filetypes=[("Fichiers CSV", "*.csv")], confirmoverwrite=False)
        if not name:
            return
        new_path = Path(name)
        if new_path.suffix.lower() != ".csv":
            messagebox.showerror("Format du fichier", "Choisissez un fichier .csv.", parent=self.root)
            return
        new_store = CSVStore(new_path)
        try:
            notes = new_store.load()
        except (StoreError, OSError, ValueError, RuntimeError) as error:
            self._error("Format CSV non pris en charge", error)
            return
        self.store = new_store
        self.notes = notes
        self.path_label.set(str(new_path))
        self._invalidate_preview()
        self._render_library()
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.config_path.with_suffix(".tmp")
            temp.write_text(json.dumps({"csv_path": str(new_path)}, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, self.config_path)
            self.status.set("Un autre fichier CSV a été sélectionné. La saisie est conservée ; relancez l’analyse.")
        except OSError as error:
            self.status.set(f"Un autre CSV a été sélectionné, mais son chemin n’a pas pu être mémorisé : {error}")

    def open_folder(self) -> None:
        try:
            folder = self.store.path.parent
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as error:
            self._error("Ouverture du dossier impossible", error)

    def export_all(self) -> None:
        try:
            notes = self.store.load()
        except (StoreError, OSError, ValueError, RuntimeError) as error:
            self._error("Lecture du CSV impossible", error)
            return
        if not notes:
            self.status.set("Le CSV actuel ne contient aucune note. Enregistrez des notes avant l’export.")
            return
        name = filedialog.asksaveasfilename(parent=self.root, title="Exporter toutes les notes enregistrées", initialdir=str(self.store.path.parent), initialfile="Notes de français.docx", defaultextension=".docx", filetypes=[("Documents Word", "*.docx")])
        if not name:
            return
        try:
            exported = export_docx(notes, Path(name))
        except ImportError:
            messagebox.showerror("Composant d’export manquant", "Exécutez setup_windows.bat pour installer les dépendances, puis réessayez. L’enregistrement au format CSV reste disponible.", parent=self.root)
            return
        except (OSError, ValueError, RuntimeError) as error:
            self._error("Échec de l’export Word", error)
            return
        self.status.set(f"Notes exportées : {len(notes)}. Fichier : {exported}")
        messagebox.showinfo("Export terminé", f"Notes exportées : {len(notes)}, regroupées en mots et en phrases.\n\n{exported}", parent=self.root)

    def show_preview_text(self, _event: tk.Event | None = None) -> None:
        selected = self.preview_tree.selection()
        if selected:
            item = self.candidates[int(selected[0])]
            messagebox.showinfo(f"{CATEGORY_LABELS[item.category]} · {STATUS_LABELS[item.status]}", item.french, parent=self.root)

    def show_library_text(self, _event: tk.Event | None = None) -> None:
        selected = self.library_tree.selection()
        if selected:
            note = self.notes[int(selected[0])]
            messagebox.showinfo(CATEGORY_LABELS[note.category], note.french, parent=self.root)

    def close(self) -> None:
        if self.input.get("1.0", "end-1c").strip():
            if not messagebox.askyesno("Notes non enregistrées", "La saisie n’a pas encore été enregistrée. Voulez-vous quitter quand même ?", parent=self.root):
                return
        self.root.destroy()

    def _error(self, title: str, error: Exception) -> None:
        self.status.set(f"{title} : {error}")
        messagebox.showerror(title, str(error), parent=self.root)


def main() -> None:
    root = tk.Tk()
    FrenchNotesApp(root)
    root.mainloop()
