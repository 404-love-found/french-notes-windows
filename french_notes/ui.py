"""Small, multilingual desktop interface backed by a local CSV."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from .core import CSVStore, Candidate, Note, StoreError, normalize_key
from .exporter import export_docx
from .i18n import BRAND, LANGUAGES, translate, validate_language


# Keep the original French constants available for integrations. Business state
# uses category/status codes; translated labels never enter the CSV.
CATEGORY_LABELS = {"word": "Mot", "sentence": "Phrase"}
CATEGORY_FILTERS = {"Tous": None, "Mots": "word", "Phrases": "sentence"}
STATUS_LABELS = {"new": "À ajouter", "existing": "Déjà dans le CSV", "batch": "Doublon du lot"}


def display_time(value: str) -> str:
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
    def __init__(self, root: tk.Tk, csv_path: Path | None = None, *, language: str | None = None) -> None:
        self.root = root
        self.config_path = app_data_dir() / "settings.json"
        self._settings = self._read_settings()
        self.language = validate_language(language if language is not None else self._settings.get("language", "fr"))
        self.store = CSVStore(csv_path or self._configured_path())
        self.candidates: list[Candidate] = []
        self.notes: list[Note] = []
        self._localized_widgets: list[tuple[tk.Widget, str]] = []
        self._changing_language = False
        self._status_message = ("ready", {})
        self._summary_message = ("analyze_first", {})
        self.search = tk.StringVar()
        self.category_filter = tk.StringVar(value=self.t("all"))
        self.language_choice = tk.StringVar(value=LANGUAGES[self.language])
        self.status = tk.StringVar(value=self.t("ready"))
        self.path_label = tk.StringVar(value=str(self.store.path))
        self.summary = tk.StringVar(value=self.t("analyze_first"))
        self.library_summary = tk.StringVar()
        self._setup_style()
        self._build()
        self.refresh_library()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Control-Return>", lambda _event: self.analyze())
        if sys.platform == "darwin":
            self.root.bind("<Command-Return>", lambda _event: self.analyze())

    def t(self, key: str, **params: object) -> str:
        return translate(self.language, key, **params)

    def _read_settings(self) -> dict:
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, TypeError):
            return {}

    def _configured_path(self) -> Path:
        stored = self._settings.get("csv_path")
        if isinstance(stored, str) and Path(stored).is_absolute():
            return Path(stored)
        return app_data_dir() / "notes.csv"

    def _persist_settings(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {**self._settings, "csv_path": str(self.store.path), "language": self.language}
        temp = self.config_path.with_suffix(".tmp")
        try:
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, self.config_path)
            self._settings = data
        finally:
            temp.unlink(missing_ok=True)

    def _setup_style(self) -> None:
        self.root.title(f"{self.t('title')} · FrenchNotes")
        self.root.geometry("1180x760")
        self.root.minsize(1024, 640)
        self.font_family = "Segoe UI" if sys.platform == "win32" else "Helvetica"
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
            tkfont.nametofont(name, root=self.root).configure(family=self.font_family, size=11)
        self.root.configure(bg="#f5f7fa")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f5f7fa")
        style.configure("TLabel", background="#f5f7fa", foreground="#243247", font=(self.font_family, 11))
        style.configure("Title.TLabel", font=(self.font_family, 22, "bold"), foreground="#172b45")
        style.configure("Muted.TLabel", foreground="#687586", font=(self.font_family, 10))
        style.configure("Brand.TLabel", foreground="#687586", font=(self.font_family, 9))
        style.configure("Section.TLabel", font=(self.font_family, 12, "bold"))
        style.configure("TButton", font=(self.font_family, 10), padding=(12, 8))
        style.configure("Primary.TButton", background="#245a93", foreground="white", padding=(16, 9))
        style.map("Primary.TButton", background=[("disabled", "#c2cbd6"), ("active", "#1a4777")], foreground=[("disabled", "#f8fafc")])
        style.configure("Treeview", font=(self.font_family, 11), rowheight=34, background="white", fieldbackground="white", borderwidth=1)
        style.configure("Treeview.Heading", font=(self.font_family, 10, "bold"), padding=(8, 9), background="#eaf0f7")
        style.map("Treeview", background=[("selected", "#245a93")], foreground=[("selected", "white")])
        style.configure("TNotebook", background="#f5f7fa", borderwidth=0)
        style.configure("TNotebook.Tab", font=(self.font_family, 11), padding=(18, 9))
        style.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", "#245a93")])

    def _localized(self, widget: tk.Widget, key: str) -> tk.Widget:
        widget.configure(text=self.t(key))
        self._localized_widgets.append((widget, key))
        return widget

    def _label(self, parent: tk.Widget, key: str, **options: object) -> ttk.Label:
        return self._localized(ttk.Label(parent, **options), key)

    def _button(self, parent: tk.Widget, key: str, **options: object) -> ttk.Button:
        return self._localized(ttk.Button(parent, **options), key)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 18))
        # Reserve the controls before the expanding title, including long labels.
        self.export_button = self._button(header, "export", command=self.export_all)
        self.export_button.pack(side="right")
        self.language_selector = ttk.Combobox(header, values=tuple(LANGUAGES.values()), textvariable=self.language_choice, state="readonly", width=10)
        self.language_selector.pack(side="right", padx=(12, 12))
        self.language_selector.bind("<<ComboboxSelected>>", self._language_selected)
        self._label(header, "title", style="Title.TLabel").pack(side="left", fill="x", expand=True)

        path_row = ttk.Frame(outer)
        path_row.pack(fill="x", pady=(0, 16))
        ttk.Label(path_row, text="CSV", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        self.path_entry = ttk.Entry(path_row, textvariable=self.path_label, state="readonly")
        self.path_entry.pack(side="left", fill="x", expand=True)
        self._button(path_row, "choose_csv", command=self.choose_csv).pack(side="left", padx=(8, 6))
        self._button(path_row, "open_folder", command=self.open_folder).pack(side="left")

        footer = ttk.Frame(outer)
        footer.pack(side="bottom", fill="x", pady=(14, 0))
        self.brand_label = ttk.Label(footer, text=BRAND, style="Brand.TLabel")
        self.brand_label.pack(side="right", padx=(16, 0))
        self.status_label = ttk.Label(footer, textvariable=self.status, style="Muted.TLabel", wraplength=640)
        self.status_label.pack(side="left", fill="x", expand=True)
        self.root.bind("<Configure>", self._resize_status, add=True)

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)
        self.intake_tab = ttk.Frame(self.notebook, padding=16)
        self.library_tab = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(self.intake_tab, text=self.t("intake_tab"))
        self.notebook.add(self.library_tab, text=self.t("library_tab"))
        self._build_intake()
        self._build_library()

    def _resize_status(self, event: tk.Event) -> None:
        if event.widget == self.root:
            self.status_label.configure(wraplength=max(240, event.width - self.brand_label.winfo_reqwidth() - 60))

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
        self._label(left, "input_heading", style="Section.TLabel").pack(anchor="w")
        self._label(left, "input_hint", style="Muted.TLabel").pack(anchor="w", pady=(6, 12))
        input_actions = ttk.Frame(left)
        input_actions.pack(side="bottom", fill="x", pady=(12, 0))
        self.analyze_button = self._button(input_actions, "analyze", style="Primary.TButton", command=self.analyze)
        self.analyze_button.pack(side="left")
        self._button(input_actions, "clear", command=self.clear_input).pack(side="right")
        input_frame = ttk.Frame(left)
        input_frame.pack(fill="both", expand=True)
        self.input = tk.Text(input_frame, wrap="word", undo=True, width=27, height=13, font=(self.font_family, 12), bg="white", fg="#20314b", insertbackground="#20314b", relief="solid", borderwidth=1, padx=12, pady=12)
        input_scroll = ttk.Scrollbar(input_frame, command=self.input.yview)
        self.input.configure(yscrollcommand=input_scroll.set)
        self.input.pack(side="left", fill="both", expand=True)
        input_scroll.pack(side="right", fill="y")
        self.input.bind("<<Modified>>", self._input_changed)

        self._label(right, "preview_heading", style="Section.TLabel").pack(anchor="w", pady=(0, 12))
        preview_actions = ttk.Frame(right)
        preview_actions.pack(side="bottom", fill="x", pady=(12, 0))
        category_buttons = ttk.Frame(preview_actions)
        category_buttons.pack(fill="x", pady=(0, 8))
        self._label(category_buttons, "category_label", style="Muted.TLabel").pack(side="left", padx=(0, 8))
        self._button(category_buttons, "word", command=lambda: self.set_category("word")).pack(side="left", padx=(0, 6))
        self._button(category_buttons, "sentence", command=lambda: self.set_category("sentence")).pack(side="left")
        ttk.Label(preview_actions, textvariable=self.summary, style="Muted.TLabel", wraplength=560).pack(anchor="w", pady=(0, 9))
        self.save_button = self._button(preview_actions, "save", style="Primary.TButton", command=self.save_new, state="disabled")
        self.save_button.pack(fill="x")
        self.preview_tree = self._scroll_tree(right, ("category", "french", "status"))
        for key, width, minimum in (("category", 95, 85), ("french", 285, 170), ("status", 160, 140)):
            self.preview_tree.column(key, width=width, minwidth=minimum, stretch=key == "french", anchor="w")
        self.preview_tree.tag_configure("duplicate", foreground="#7a8491")
        self.preview_tree.bind("<Double-1>", self.show_preview_text)
        self._update_headings()

    def _build_library(self) -> None:
        controls = ttk.Frame(self.library_tab)
        controls.pack(fill="x", pady=(0, 12))
        self._label(controls, "search", style="Muted.TLabel").pack(side="left")
        ttk.Entry(controls, textvariable=self.search).pack(side="left", fill="x", expand=True, padx=(8, 12))
        self.filter_selector = ttk.Combobox(controls, values=tuple(self._filters()), textvariable=self.category_filter, state="readonly", width=10)
        self.filter_selector.pack(side="left", padx=(0, 10))
        self._button(controls, "refresh", command=self.refresh_library).pack(side="left")
        ttk.Label(self.library_tab, textvariable=self.library_summary, style="Muted.TLabel", wraplength=950).pack(side="bottom", anchor="w", pady=(12, 0))
        self.library_tree = self._scroll_tree(self.library_tab, ("category", "french", "created"))
        for key, width, minimum in (("category", 110, 85), ("french", 620, 200), ("created", 180, 170)):
            self.library_tree.column(key, width=width, minwidth=minimum, stretch=key == "french", anchor="w")
        self.library_tree.bind("<Double-1>", self.show_library_text)
        self._update_headings()
        self.search.trace_add("write", lambda *_args: self._render_library())
        self.category_filter.trace_add("write", lambda *_args: self._render_library())

    def _filters(self) -> dict[str, str | None]:
        return {self.t("all"): None, self.t("words"): "word", self.t("sentences"): "sentence"}

    def _update_headings(self) -> None:
        for tree, headings in ((getattr(self, "preview_tree", None), {"category": "category_label", "french": "content", "status": "result"}), (getattr(self, "library_tree", None), {"category": "category_label", "french": "content", "created": "created"})):
            if tree is not None:
                for column, key in headings.items():
                    tree.heading(column, text=self.t(key))

    def _language_selected(self, _event: tk.Event | None = None) -> None:
        code = next((code for code, label in LANGUAGES.items() if label == self.language_choice.get()), "fr")
        self.set_language(code)

    def set_language(self, language: str, *, persist: bool = True) -> None:
        language = validate_language(language)
        if language == self.language:
            return
        category = self._filters().get(self.category_filter.get())
        self._changing_language = True
        try:
            self.language = language
            self.language_choice.set(LANGUAGES[language])
            self.root.title(f"{self.t('title')} · FrenchNotes")
            for widget, key in self._localized_widgets:
                widget.configure(text=self.t(key))
            self.notebook.tab(self.intake_tab, text=self.t("intake_tab"))
            self.notebook.tab(self.library_tab, text=self.t("library_tab"))
            self.filter_selector.configure(values=tuple(self._filters()))
            self.category_filter.set(self.t("words" if category == "word" else "sentences" if category == "sentence" else "all"))
            self._update_headings()
            self._set_status(*self._status_message)
            self._set_summary(*self._summary_message)
            self._render_preview()
        finally:
            self._changing_language = False
        self._render_library()
        if persist:
            try:
                self._persist_settings()
            except OSError:
                self._set_status("settings_error")

    def _set_status(self, key: str, params: dict | None = None, **values: object) -> None:
        params = params if params is not None else values
        self._status_message = (key, params)
        display_params = dict(params)
        if key == "reclassified" and display_params.get("category") in ("word", "sentence"):
            display_params["category"] = self.t(display_params["category"])
        self.status.set(self.t(key, **display_params))

    def _set_summary(self, key: str, params: dict | None = None, **values: object) -> None:
        params = params if params is not None else values
        self._summary_message = (key, params)
        self.summary.set(self.t(key, **params))

    def _render_preview(self) -> None:
        selected = self.preview_tree.selection()
        position = self.preview_tree.yview()
        self.preview_tree.delete(*self.preview_tree.get_children())
        for index, item in enumerate(self.candidates):
            self.preview_tree.insert("", "end", iid=str(index), values=(self.t(item.category), item.french, self.t(f"status_{item.status}")), tags=() if item.status == "new" else ("duplicate",))
        self.preview_tree.selection_set([item for item in selected if self.preview_tree.exists(item)])
        if position:
            self.preview_tree.yview_moveto(position[0])
        self.save_button.configure(state="normal" if any(item.status == "new" for item in self.candidates) else "disabled")

    def _input_changed(self, _event: tk.Event | None = None) -> None:
        if self.input.edit_modified():
            self.input.edit_modified(False)
            self._invalidate_preview()

    def _invalidate_preview(self) -> None:
        self.candidates = []
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.save_button.configure(state="disabled")
        self._set_summary("input_changed")

    def clear_input(self) -> None:
        self.input.delete("1.0", "end")
        self.input.edit_modified(False)
        self._invalidate_preview()
        self._set_status("input_cleared")

    def analyze(self) -> None:
        text = self.input.get("1.0", "end-1c")
        if not text.strip():
            self._set_status("ready")
            self.input.focus_set()
            return
        # Consume queued Modified events before installing the new preview.
        self.input.edit_modified(False)
        try:
            candidates = self.store.preview(text)
        except (StoreError, OSError, ValueError, RuntimeError) as error:
            self._invalidate_preview()
            self._error(self.t("error_analyze"), error)
            return
        self.candidates = candidates
        self._render_preview()
        new = sum(item.status == "new" for item in candidates)
        self._set_summary("preview_summary", new=new, existing=sum(item.status == "existing" for item in candidates), batch=sum(item.status == "batch" for item in candidates))
        self._set_status("review_ready" if new else "no_new")

    def set_category(self, category: str) -> None:
        if category not in ("word", "sentence"):
            raise ValueError("Unknown category")
        changed = 0
        for selected in self.preview_tree.selection():
            item = self.candidates[int(selected)]
            if item.status == "new":
                item.category = category
                self.preview_tree.item(selected, values=(self.t(category), item.french, self.t(f"status_{item.status}")))
                changed += 1
        self._set_status("reclassified", changed=changed, category=category) if changed else self._set_status("select_new")

    def save_new(self) -> None:
        if not self.candidates:
            return
        cleanup_warning = None
        try:
            result = self.store.append(self.candidates)
        except StoreError as error:
            if error.saved_result is None:
                self._error(self.t("error_save"), error)
                return
            result = error.saved_result
            cleanup_warning = error
        except (OSError, ValueError, RuntimeError) as error:
            self._error(self.t("error_save"), error)
            return
        self.input.delete("1.0", "end")
        self.input.edit_modified(False)
        self._invalidate_preview()
        self.refresh_library()
        self._set_summary("save_summary", added=len(result.added), skipped=result.skipped)
        self._set_status("save_summary", added=len(result.added), skipped=result.skipped)
        if cleanup_warning:
            self._set_status("cleanup_warning")
            messagebox.showwarning(self.t("cleanup_warning"), f"{self.t('error_cleanup_detail')}\n\n{self._error_message(cleanup_warning)}", parent=self.root)

    def refresh_library(self) -> None:
        try:
            self.notes = self.store.load()
        except (StoreError, OSError, ValueError, RuntimeError) as error:
            self.notes = []
            self._render_library()
            self._error(self.t("error_read"), error)
            return
        self._render_library()

    def _render_library(self) -> None:
        if self._changing_language:
            return
        selected = self.library_tree.selection()
        position = self.library_tree.yview()
        self.library_tree.delete(*self.library_tree.get_children())
        query = normalize_key(self.search.get())
        category = self._filters().get(self.category_filter.get())
        shown = 0
        for index, note in enumerate(self.notes):
            if category is not None and note.category != category:
                continue
            if query and query not in normalize_key(note.french):
                continue
            self.library_tree.insert("", "end", iid=str(index), values=(self.t(note.category), note.french, display_time(note.created_at)))
            shown += 1
        self.library_tree.selection_set([item for item in selected if self.library_tree.exists(item)])
        if position:
            self.library_tree.yview_moveto(position[0])
        words = sum(note.category == "word" for note in self.notes)
        self.library_summary.set(self.t("library_summary", total=len(self.notes), words=words, sentences=len(self.notes) - words, shown=shown))
        self.export_button.configure(state="normal" if self.notes else "disabled")

    def choose_csv(self) -> None:
        name = filedialog.asksaveasfilename(parent=self.root, title=self.t("select_csv_title"), initialdir=str(self.store.path.parent) if self.store.path.parent.exists() else str(Path.home()), initialfile=self.store.path.name, defaultextension=".csv", filetypes=[(self.t("csv_files"), "*.csv")], confirmoverwrite=False)
        if not name:
            return
        new_path = Path(name)
        if new_path.suffix.lower() != ".csv":
            messagebox.showerror(self.t("file_format"), self.t("csv_extension"), parent=self.root)
            return
        new_store = CSVStore(new_path)
        try:
            notes = new_store.load()
        except (StoreError, OSError, ValueError, RuntimeError) as error:
            self._error(self.t("unsupported_csv"), error)
            return
        self.store = new_store
        self.notes = notes
        self.path_label.set(str(new_path))
        self._invalidate_preview()
        self._render_library()
        self._set_status("csv_changed")
        try:
            self._persist_settings()
        except OSError:
            self._set_status("settings_error")

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
            self._error(self.t("error_folder"), error)

    def export_all(self) -> None:
        try:
            notes = self.store.load()
        except (StoreError, OSError, ValueError, RuntimeError) as error:
            self._error(self.t("error_read"), error)
            return
        if not notes:
            self._set_status("empty_export")
            return
        name = filedialog.asksaveasfilename(parent=self.root, title=self.t("export_title"), initialdir=str(self.store.path.parent), initialfile=self.t("export_filename"), defaultextension=".docx", filetypes=[(self.t("word_files"), "*.docx")])
        if not name:
            return
        try:
            exported = export_docx(notes, Path(name), language=self.language)
        except ImportError:
            messagebox.showerror(self.t("export_missing_title"), self.t("export_missing_message"), parent=self.root)
            return
        except (OSError, ValueError, RuntimeError) as error:
            self._error(self.t("error_export"), error)
            return
        self._set_status("export_summary", count=len(notes))
        messagebox.showinfo(self.t("export_done"), f"{self.t('export_summary', count=len(notes))}\n\n{exported}", parent=self.root)

    def show_preview_text(self, _event: tk.Event | None = None) -> None:
        selected = self.preview_tree.selection()
        if selected:
            item = self.candidates[int(selected[0])]
            messagebox.showinfo(f"{self.t(item.category)} · {self.t(f'status_{item.status}')}", item.french, parent=self.root)

    def show_library_text(self, _event: tk.Event | None = None) -> None:
        selected = self.library_tree.selection()
        if selected:
            note = self.notes[int(selected[0])]
            messagebox.showinfo(self.t(note.category), note.french, parent=self.root)

    def close(self) -> None:
        if self.input.get("1.0", "end-1c").strip():
            if not messagebox.askyesno(self.t("unsaved_title"), self.t("unsaved_message"), parent=self.root):
                return
        self.root.destroy()

    def _error(self, title: str, error: Exception) -> None:
        self._set_status("error_generic")
        messagebox.showerror(title, f"{self.t('error_details')}\n{self._error_message(error)}", parent=self.root)

    def _error_message(self, error: Exception) -> str:
        localize = getattr(error, "localized_message", None)
        return localize(self.language) if callable(localize) else str(error)


def main() -> None:
    root = tk.Tk()
    FrenchNotesApp(root)
    root.mainloop()
