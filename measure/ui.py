"""Tk desktop interface. All score and report processing stays on this computer."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .catalog import TESTS, SCORE_TYPES, lookup
from .documents import Template, load_template, render_docx
from .engine import Renderer, missing_mentions, review
from .importers import FIELDS, Table, guess_header, header_mapping, parse_delimited, read_tables, scores_from_table
from .models import Score, number
from .project import load_project, save_project
from .rules import category_for, defaults, validate_rules

BG, PAPER, INK, MUTED = "#f3f5f2", "#ffffff", "#193a3c", "#607779"
TEAL, PALE, LINE, GOLD = "#245f58", "#e4efea", "#dce5df", "#bc8d4a"
FONT = "Helvetica Neue" if sys.platform == "darwin" else "Helvetica"
REPORT_FONT = "Georgia" if sys.platform == "darwin" else "Times"
DEMO_TEXT = """Academic Achievement

Overall performance on Total Achievement was considered {{Total Achievement.category}} (SS = {{Total Achievement.score}}, percentile rank = {{Total Achievement.percentile}}).

The Reading composite and Written Expression composite provide additional information about academic performance.

Word Reading and Reading Comprehension were examined individually. Mathematics was also assessed.

These scores should be considered alongside observations, history, and the other assessment findings.
"""


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Measure — Tests & Measurements")
        self.geometry("1260x820")
        self.minsize(1050, 740)
        self.configure(bg=BG)
        self.test = tk.StringVar(value="WIAT-4")
        self.active_test = "WIAT-4"
        self.scores: list[Score] = []
        self.rules = defaults(self.active_test)
        self.template = Template("")
        self.project_path: str | None = None
        self.import_notes: list[str] = []
        self.auto = tk.BooleanVar(value=True)
        self.pr = tk.BooleanVar(value=True)
        self.ci = tk.BooleanVar(value=False)
        self.first = tk.BooleanVar(value=False)
        self.policy = tk.StringVar(value="Imported labels, then cutoff rules")
        self.dirty = False
        self.updating_editor = False
        self.last_preview = ""
        self.step = "scores"
        self._styles()
        self._build()
        self._menu()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Command-s>" if sys.platform == "darwin" else "<Control-s>", lambda _e: self.save())
        self.bind("<Command-o>" if sys.platform == "darwin" else "<Control-o>", lambda _e: self.open())
        self.show_step("scores")
        self.refresh_scores()

    def _styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=(FONT, 11), background=BG, foreground=INK)
        style.configure("TFrame", background=BG)
        style.configure("Paper.TFrame", background=PAPER)
        style.configure("Side.TFrame", background="#e9eeea")
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Paper.TLabel", background=PAPER)
        style.configure("Title.TLabel", font=(FONT, 23, "bold"))
        style.configure("Heading.TLabel", font=(FONT, 17, "bold"))
        style.configure("Tiny.TLabel", font=(FONT, 9), foreground=MUTED)
        style.configure("TButton", padding=(14, 9), relief="flat", borderwidth=0, background=PAPER)
        style.map("TButton", background=[("active", PALE)], foreground=[("disabled", "#98aaa6")])
        style.configure("Primary.TButton", background=TEAL, foreground="white", font=(FONT, 11, "bold"))
        style.map("Primary.TButton", background=[("active", "#184e48"), ("disabled", "#a4b8b1")], foreground=[("disabled", "#ffffff")])
        style.configure("Nav.TButton", background="#e9eeea", anchor="w", padding=(16, 13))
        style.configure("Selected.Nav.TButton", background=PAPER, foreground=TEAL, font=(FONT, 11, "bold"))
        style.configure("TCombobox", padding=7, fieldbackground=PAPER)
        style.configure("TEntry", padding=6, fieldbackground=PAPER)
        style.configure("Treeview", rowheight=38, background=PAPER, fieldbackground=PAPER, borderwidth=0, font=(FONT, 11))
        style.configure("Treeview.Heading", background=PALE, padding=(10, 11), relief="flat", font=(FONT, 10, "bold"))
        style.map("Treeview", background=[("selected", "#d6e9df")], foreground=[("selected", INK)])
        style.configure("TCheckbutton", background=BG)
        style.configure("TLabelframe", background=BG)
        style.configure("TLabelframe.Label", font=(FONT, 11, "bold"))

    def _build(self):
        sidebar = ttk.Frame(self, style="Side.TFrame", width=220, padding=(20, 28))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="m.", font=(FONT, 40, "bold"), bg="#e9eeea", fg=TEAL, anchor="w").pack(fill="x")
        tk.Label(sidebar, text="MEASURE", font=(FONT, 16, "bold"), bg="#e9eeea", fg=INK, anchor="w").pack(fill="x", pady=(0, 4))
        tk.Label(sidebar, text="Tests & Measurements", font=(FONT, 9), bg="#e9eeea", fg=MUTED, anchor="w").pack(fill="x")
        tk.Label(sidebar, text="ASSESSMENT", font=(FONT, 9, "bold"), bg="#e9eeea", fg=MUTED, anchor="w").pack(fill="x", pady=(38, 8))
        combo = ttk.Combobox(sidebar, textvariable=self.test, values=TESTS, state="readonly", width=16)
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", self.change_test)
        self.nav = {}
        for key, title in (("scores", "01   Score table"), ("template", "02   Your template"), ("preview", "03   Review & export"), ("rules", "       Cutoff rules")):
            button = ttk.Button(sidebar, text=title, style="Nav.TButton", command=lambda k=key: self.show_step(k))
            button.pack(fill="x", pady=(25 if key == "scores" else 5, 0))
            self.nav[key] = button
        bottom = ttk.Frame(sidebar, style="Side.TFrame")
        bottom.pack(side="bottom", fill="x")
        ttk.Button(bottom, text="Try an example", command=self.demo).pack(fill="x", pady=(0, 16))
        tk.Label(bottom, text="LOCAL WORKSPACE\nYour reports stay on your Mac.\nNo account or AI API needed.", justify="left", bg="#e9eeea", fg=MUTED, font=(FONT, 9), anchor="w").pack(fill="x")
        main = ttk.Frame(self, padding=(32, 26, 32, 15))
        main.pack(side="left", fill="both", expand=True)
        header = ttk.Frame(main)
        header.pack(fill="x")
        ttk.Label(header, text="Your report, with less repetition.", style="Title.TLabel").pack(side="left")
        actions = ttk.Frame(header)
        actions.pack(side="right")
        ttk.Button(actions, text="Open", command=self.open).pack(side="left", padx=4)
        ttk.Button(actions, text="Save project", command=self.save).pack(side="left")
        ttk.Label(main, text="Bring in scores. Keep your voice. Build the report.", style="Muted.TLabel").pack(anchor="w", pady=(9, 24))
        ttk.Separator(main).pack(fill="x")
        self.container = ttk.Frame(main)
        self.container.pack(fill="both", expand=True, pady=(24, 14))
        self.container.rowconfigure(0, weight=1)
        self.container.columnconfigure(0, weight=1)
        self.panels = {key: ttk.Frame(self.container) for key in self.nav}
        for frame in self.panels.values():
            frame.grid(row=0, column=0, sticky="nsew")
        self._scores_panel()
        self._template_panel()
        self._preview_panel()
        self._rules_panel()
        self.status = tk.StringVar(value="Ready")
        ttk.Label(main, textvariable=self.status, style="Tiny.TLabel", anchor="w").pack(fill="x")

    def _menu(self):
        menu = tk.Menu(self)
        filemenu = tk.Menu(menu, tearoff=False)
        for title, action in (("Open project…", self.open), ("Save project…", self.save), ("Save project as…", lambda: self.save(True)), ("Import score table…", self.import_scores), ("Import template…", self.import_template), ("Export Word document…", self.export_word)):
            filemenu.add_command(label=title, command=action)
        menu.add_cascade(label="File", menu=filemenu)
        helpmenu = tk.Menu(menu, tearoff=False)
        helpmenu.add_command(label="How to use Measure", command=self.help)
        menu.add_cascade(label="Help", menu=helpmenu)
        self.config(menu=menu)

    def _scores_panel(self):
        frame = self.panels["scores"]
        ttk.Label(frame, text="Bring your scores together.", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Import a table, check the columns, then review each score before using it.", style="Muted.TLabel").pack(anchor="w", pady=(7, 18))
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Import score table…", style="Primary.TButton", command=self.import_scores).pack(side="left")
        ttk.Button(toolbar, text="Paste table", command=self.paste_table).pack(side="left", padx=8)
        ttk.Button(toolbar, text="+ Add a score", command=self.edit_score).pack(side="left")
        self.counts = tk.StringVar()
        ttk.Label(frame, textvariable=self.counts, style="Muted.TLabel").pack(anchor="w", pady=(20, 12))
        table_frame = ttk.Frame(frame, style="Paper.TFrame")
        table_frame.pack(fill="both", expand=True)
        columns = ("name", "type", "score", "pr", "ci", "category")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended", height=4)
        widths = (245, 115, 65, 65, 105, 145)
        for col, title, width in zip(columns, ("MEASURE", "SCORE TYPE", "SCORE", "PR", "CI", "CATEGORY"), widths):
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, minwidth=55, stretch=col in ("name", "category"), anchor="w" if col in ("name", "type", "category") else "center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sy = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        sy.grid(row=0, column=1, sticky="ns")
        sx = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        sx.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.tree.bind("<Double-1>", lambda _e: self.edit_selected())
        self.tree.bind("<<TreeviewSelect>>", self.selected_score)
        self.source = tk.StringVar(value="No scores yet. Import a table or try the example in the sidebar.")
        ttk.Label(frame, textvariable=self.source, style="Tiny.TLabel", wraplength=780).pack(anchor="w", pady=(9, 13))
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Edit selected", command=self.edit_selected).pack(side="left")
        ttk.Button(bottom, text="Remove selected", command=self.remove_scores).pack(side="left", padx=8)
        ttk.Button(bottom, text="Continue to template  →", style="Primary.TButton", command=lambda: self.show_step("template")).pack(side="right")

    def _editor(self, frame, font=(FONT, 12), height=5):
        wrapper = ttk.Frame(frame, style="Paper.TFrame")
        text = tk.Text(wrapper, wrap="word", undo=True, relief="flat", borderwidth=0, bg=PAPER, fg=INK,
                       insertbackground=TEAL, selectbackground="#d6e9df", padx=20, pady=18, font=font,
                       spacing1=4, spacing3=5, height=height, width=20)
        text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(wrapper, command=text.yview)
        scroll.pack(side="right", fill="y")
        text.configure(yscrollcommand=scroll.set)
        return wrapper, text

    def _template_panel(self):
        frame = self.panels["template"]
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text="Write once. Reuse your format.", style="Heading.TLabel").pack(side="left")
        ttk.Button(top, text="Import template…", command=self.import_template).pack(side="right")
        ttk.Label(frame, text="Use your own wording. Scores appear after matching names or inside your placeholders.", style="Muted.TLabel").pack(anchor="w", pady=(9, 14))
        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=(0, 12))
        self.token_measure = tk.StringVar()
        self.token_combo = ttk.Combobox(bar, textvariable=self.token_measure, state="readonly", width=27)
        self.token_combo.pack(side="left")
        self.token_attr = tk.StringVar(value="score")
        ttk.Combobox(bar, textvariable=self.token_attr, values=("score", "category", "percentile", "ci", "summary", "age_eq", "grade_eq", "raw_score"), state="readonly", width=12).pack(side="left", padx=8)
        ttk.Button(bar, text="Insert placeholder", command=self.insert_token).pack(side="left")
        wrapper, self.editor = self._editor(frame, (REPORT_FONT, 13))
        wrapper.pack(fill="both", expand=True)
        self.editor.bind("<<Modified>>", self.editor_changed)
        self.template_note = tk.StringVar(value="Text template · you can type or paste here")
        ttk.Label(frame, textvariable=self.template_note, style="Tiny.TLabel").pack(anchor="w", pady=(8, 12))
        options = ttk.Frame(frame)
        options.pack(fill="x")
        for i, (label, var) in enumerate((("Insert after matching names", self.auto), ("Include percentile", self.pr), ("Include CI", self.ci), ("First mention only", self.first))):
            ttk.Checkbutton(options, text=label, variable=var, command=self.changed).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 24), pady=3)
        footer = ttk.Frame(frame)
        footer.pack(fill="x", pady=(17, 0))
        ttk.Label(footer, text="Example: {{Word Reading.score}}  →  92", style="Tiny.TLabel").pack(side="left")
        ttk.Button(footer, text="Review report  →", style="Primary.TButton", command=lambda: self.show_step("preview")).pack(side="right")

    def _preview_panel(self):
        frame = self.panels["preview"]
        top = ttk.Frame(frame)
        top.pack(fill="x")
        ttk.Label(top, text="Check the details. Make it yours.", style="Heading.TLabel").pack(side="left")
        ttk.Button(top, text="Refresh preview", command=self.preview).pack(side="right")
        ttk.Label(frame, text="Inserted values are highlighted. Export includes the report text without highlighting.", style="Muted.TLabel").pack(anchor="w", pady=(8, 14))
        wrapper, self.preview_text = self._editor(frame, (REPORT_FONT, 12))
        wrapper.pack(fill="both", expand=True)
        self.preview_text.tag_configure("inserted", background="#e3f0e5", foreground="#174c38")
        self.preview_text.configure(state="disabled")
        self.preview_status = tk.StringVar(value="Generate a preview to review your report.")
        ttk.Label(frame, textvariable=self.preview_status, style="Muted.TLabel").pack(anchor="w", pady=(12, 6))
        self.review_box = tk.Text(frame, height=4, wrap="word", relief="flat", bg=BG, fg=MUTED, font=(FONT, 10), padx=0, pady=3)
        self.review_box.pack(fill="x")
        self.review_box.configure(state="disabled")
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Button(bottom, text="Copy report", command=self.copy_report).pack(side="left")
        ttk.Button(bottom, text="Export text…", command=self.export_text).pack(side="left", padx=8)
        ttk.Button(bottom, text="Export Word document…", style="Primary.TButton", command=self.export_word).pack(side="right")

    def _rules_panel(self):
        frame = self.panels["rules"]
        ttk.Label(frame, text="Your scoring conventions.", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Choose the category source and edit inclusive score bands for the selected assessment.", style="Muted.TLabel").pack(anchor="w", pady=(8, 16))
        top = ttk.Frame(frame)
        top.pack(fill="x", pady=(0, 12))
        ttk.Label(top, text="Category source").pack(side="left", padx=(0, 12))
        combo = ttk.Combobox(top, textvariable=self.policy, values=("Imported labels, then cutoff rules", "Cutoff rules only"), state="readonly", width=35)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", lambda _e: self.policy_changed())
        self.rules_note = tk.StringVar()
        ttk.Label(frame, textvariable=self.rules_note, style="Muted.TLabel", wraplength=790).pack(anchor="w", pady=(0, 13))
        scope = ttk.Frame(frame)
        scope.pack(fill="x", pady=(4, 14))
        ttk.Label(scope, text="Apply these cutoffs to").pack(side="left", padx=(0, 10))
        self.rule_group = tk.StringVar(value="Standard scores")
        self.rule_group_combo = ttk.Combobox(scope, textvariable=self.rule_group, state="readonly", values=("Standard scores", "Scaled scores", "Named measure"), width=19)
        self.rule_group_combo.pack(side="left")
        self.rule_group_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_bands())
        self.rule_name = tk.StringVar()
        self.rule_name_combo = ttk.Combobox(scope, textvariable=self.rule_name, width=32)
        self.rule_name_combo.pack(side="left", padx=10)
        self.rule_name_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_bands())
        self.rule_name_combo.bind("<Return>", lambda _e: self.refresh_bands())
        ttk.Button(scope, text="Show", command=self.refresh_bands).pack(side="left")
        band_frame = ttk.Frame(frame, style="Paper.TFrame")
        band_frame.pack(fill="both", expand=True)
        self.band_tree = ttk.Treeview(band_frame, columns=("min", "max", "label"), show="headings", height=4)
        for key, title, width in (("min", "LOWEST SCORE", 170), ("max", "HIGHEST SCORE", 170), ("label", "CATEGORY", 390)):
            self.band_tree.heading(key, text=title)
            self.band_tree.column(key, width=width, anchor="center" if key != "label" else "w")
        self.band_tree.pack(fill="both", expand=True)
        self.band_tree.bind("<Double-1>", lambda _e: self.edit_band(True))
        edits = ttk.Frame(frame)
        edits.pack(fill="x", pady=(10, 0))
        ttk.Button(edits, text="+ Add category", command=self.edit_band).pack(side="left")
        ttk.Button(edits, text="Edit selected", command=lambda: self.edit_band(True)).pack(side="left", padx=8)
        ttk.Button(edits, text="Remove selected", command=self.remove_bands).pack(side="left")
        ttk.Label(frame, text="Both endpoints are included. Leave a score range unclassified by omitting it.", style="Tiny.TLabel").pack(anchor="w", pady=(10, 0))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Reset defaults", command=self.reset_rules).pack(side="left")
        ttk.Button(buttons, text="Import rules…", command=self.import_rules).pack(side="left", padx=8)
        ttk.Button(buttons, text="Export rules…", command=self.export_rules).pack(side="left")
        ttk.Button(buttons, text="Apply cutoff rules", style="Primary.TButton", command=self.apply_rules).pack(side="right")

    def changed(self):
        self.dirty = True
        self.status.set(f"{self.active_test} · Unsaved changes")

    def options(self):
        return {"auto_insert": self.auto.get(), "include_percentile": self.pr.get(), "include_ci": self.ci.get(), "first_only": self.first.get(), "policy": "imported" if self.policy.get().startswith("Imported") else "rules"}

    def current_template(self):
        text = self.editor.get("1.0", "end-1c")
        return Template(text, self.template.docx_bytes if text == self.template.original_text else None, text)

    def renderer(self):
        return Renderer(self.active_test, self.scores, self.rules, **self.options())

    def show_step(self, key):
        if self.step == "rules" and key != "rules":
            if not self.apply_rules(silent=True):
                return
        self.step = key
        self.panels[key].tkraise()
        for name, button in self.nav.items():
            button.configure(style="Selected.Nav.TButton" if name == key else "Nav.TButton")
        if key == "rules":
            self.refresh_rules()
        if key == "preview":
            self.preview()

    def refresh_scores(self):
        self.tree.delete(*self.tree.get_children())
        for index, row in enumerate(self.scores):
            try:
                category = category_for(row, self.rules, self.options()["policy"], self.active_test)[0]
            except ValueError:
                category = "Rule conflict"
            self.tree.insert("", "end", iid=str(index), values=(row.name, SCORE_TYPES.get(row.score_type, row.score_type), number(row.score), row.percentile or "—", row.ci or "—", category or "Unclassified"))
        self.token_combo.configure(values=[row.name for row in self.scores])
        if self.scores and self.token_measure.get() not in [row.name for row in self.scores]:
            self.token_measure.set(self.scores[0].name)
        try:
            errors, warnings = review(self.active_test, self.scores, self.rules, self.options()["policy"])
            classified = sum(bool(category_for(row, self.rules, self.options()["policy"], self.active_test)[0]) for row in self.scores)
            self.counts.set(f"{len(self.scores)} measures    ·    {classified} classified    ·    {len(errors) + len(warnings)} review notes")
        except ValueError as error:
            self.counts.set(str(error))
        self.source.set("Double-click a row to edit its score, category, or matching names." if self.scores else "No scores yet. Import a table or try the example in the sidebar.")

    def selected_score(self, _event=None):
        selected = self.tree.selection()
        if selected:
            row = self.scores[int(selected[0])]
            self.source.set(f"Source: {row.source}")

    def change_test(self, _event=None):
        selected = self.test.get()
        if selected == self.active_test:
            return
        if self.dirty and not messagebox.askyesno("Switch assessment?", "Switching clears the current scores and template. Save this project first if you need it.", parent=self):
            self.test.set(self.active_test)
            return
        self.active_test = selected
        self.scores, self.rules = [], defaults(selected)
        self.template, self.project_path, self.import_notes = Template(""), None, []
        self.set_editor("")
        self.refresh_scores()
        self.refresh_rules()
        self.dirty = False
        self.status.set(f"{selected} · New project")
        self.show_step("scores")

    def import_scores(self):
        path = filedialog.askopenfilename(parent=self, title="Import a score table", filetypes=[("Supported score tables", "*.csv *.tsv *.txt *.xlsx *.docx *.pdf"), ("All files", "*")])
        if not path:
            return
        try:
            tables = read_tables(path)
            self.map_tables(tables, Path(path).name)
        except Exception as error:
            messagebox.showerror("Could not import scores", str(error), parent=self)

    def paste_table(self):
        popup = tk.Toplevel(self)
        popup.title("Paste a score table")
        popup.geometry("760x490")
        popup.transient(self)
        popup.grab_set()
        frame = ttk.Frame(popup, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Paste cells copied from Word or Excel, including column headings.", wraplength=680).pack(anchor="w", pady=(0, 12))
        wrapper, editor = self._editor(frame, (FONT, 11))
        wrapper.pack(fill="both", expand=True)
        try:
            editor.insert("1.0", self.clipboard_get())
        except tk.TclError:
            pass
        def proceed():
            try:
                rows = parse_delimited(editor.get("1.0", "end-1c"))
            except Exception as error:
                messagebox.showerror("Table not recognized", str(error), parent=popup)
                return
            popup.destroy()
            self.map_tables([Table("Pasted table", rows)], "Clipboard")
        ttk.Button(frame, text="Map columns  →", style="Primary.TButton", command=proceed).pack(anchor="e", pady=(12, 0))

    def map_tables(self, tables, source):
        tables = [table for table in tables if table.rows]
        if not tables:
            raise ValueError("No tables were found in this file.")
        popup = tk.Toplevel(self)
        popup.title("Review import columns")
        popup.geometry("960x720")
        popup.transient(self)
        popup.grab_set()
        frame = ttk.Frame(popup, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Tell Measure where your scores are.", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Choose one table and norm group. Importing replaces the current score rows.", style="Muted.TLabel").pack(anchor="w", pady=(8, 15))
        top = ttk.Frame(frame)
        top.pack(fill="x")
        selected = tk.StringVar(value=f"1 · {tables[0].title}")
        popup.table_selection = selected  # Keep the Tcl variable alive for this dialog.
        tablecombo = ttk.Combobox(top, textvariable=selected, state="readonly", values=[f"{i+1} · {table.title}" for i, table in enumerate(tables)], width=38)
        tablecombo.pack(side="left")
        ttk.Label(top, text="Header row").pack(side="left", padx=(14, 6))
        header = tk.StringVar(value=str(guess_header(tables[0].rows) + 1))
        spin = ttk.Spinbox(top, from_=1, to=99, textvariable=header, width=5)
        spin.pack(side="left")
        preview = ttk.Treeview(frame, show="headings", height=3)
        preview.pack(fill="x", pady=14)
        mapping_frame = ttk.Frame(frame)
        mapping_frame.pack(fill="x")
        variables, selectors = {}, {}
        for index, (key, title) in enumerate(FIELDS.items()):
            col, row = index % 3, index // 3
            cell = ttk.Frame(mapping_frame, padding=(0, 3, 12, 5))
            cell.grid(row=row, column=col, sticky="ew")
            ttk.Label(cell, text=title, style="Tiny.TLabel").pack(anchor="w")
            variables[key] = tk.StringVar()
            selectors[key] = ttk.Combobox(cell, textvariable=variables[key], state="readonly", width=28)
            selectors[key].pack(fill="x", pady=(4, 0))
            mapping_frame.columnconfigure(col, weight=1)
        fallback = tk.StringVar(value="Infer from assessment / header")
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(12, 0))
        ttk.Label(bottom, text="Default score type").pack(side="left", padx=(0, 10))
        ttk.Combobox(bottom, textvariable=fallback, state="readonly", values=("Infer from assessment / header", "Standard score", "Scaled score", "T score"), width=31).pack(side="left")
        note = ttk.Label(frame, text="Check confidence intervals and category labels against your source. Blank-score rows are skipped.", style="Tiny.TLabel", wraplength=850)
        note.pack(anchor="w", pady=12)
        choices = []
        def refresh(_event=None):
            nonlocal choices
            table = tables[tablecombo.current() if tablecombo.current() >= 0 else 0]
            try:
                index = int(header.get()) - 1
                if not 0 <= index < len(table.rows):
                    return
            except ValueError:
                return
            headings = table.rows[index]
            choices = [f"{i+1} · {value or '(blank)'}" for i, value in enumerate(headings)]
            guessed = header_mapping(headings)
            for key in variables:
                selectors[key].configure(values=["(not included)", *choices])
                variables[key].set(choices[guessed[key]] if key in guessed else "(not included)")
            preview.delete(*preview.get_children())
            preview.configure(columns=[str(i) for i in range(len(headings))])
            for i, title in enumerate(headings):
                preview.heading(str(i), text=title)
                preview.column(str(i), width=max(70, 850 // max(1, len(headings))), stretch=True)
            for values in table.rows[index + 1:index + 6]:
                preview.insert("", "end", values=values)
        def choose_table(_event=None):
            header.set(str(guess_header(tables[tablecombo.current()].rows) + 1))
            refresh()
        tablecombo.bind("<<ComboboxSelected>>", choose_table)
        spin.configure(command=refresh)
        spin.bind("<Return>", refresh)
        spin.bind("<FocusOut>", refresh)
        refresh()
        def confirm():
            try:
                table = tables[tablecombo.current() if tablecombo.current() >= 0 else 0]
                mapping = {key: choices.index(var.get()) for key, var in variables.items() if var.get() in choices}
                kinds = {"Infer from assessment / header": "auto", **{label: key for key, label in SCORE_TYPES.items()}}
                scores, notes = scores_from_table(table, mapping, self.active_test, int(header.get()) - 1, kinds[fallback.get()], source)
                if self.scores and not messagebox.askyesno("Replace current scores?", f"Replace {len(self.scores)} rows with {len(scores)} imported rows?", parent=popup):
                    return
                self.scores, self.import_notes = scores, notes
                self.refresh_scores()
                self.changed()
                popup.destroy()
                self.show_step("scores")
                if notes:
                    self.show_notes("Import review", notes)
            except Exception as error:
                messagebox.showerror("Check import mapping", str(error), parent=popup)
        ttk.Button(frame, text="Import & review scores", style="Primary.TButton", command=confirm).pack(anchor="e", pady=(5, 0))

    def edit_selected(self):
        selected = self.tree.selection()
        if selected:
            self.edit_score(int(selected[0]))

    def edit_score(self, index=None):
        existing = self.scores[index] if index is not None else Score("", None, "t" if self.active_test == "PAI" else "standard")
        popup = tk.Toplevel(self)
        popup.title("Edit score" if index is not None else "Add score")
        popup.geometry("660x660")
        popup.transient(self)
        popup.grab_set()
        frame = ttk.Frame(popup, padding=25)
        frame.pack(fill="both", expand=True)
        fields = (("name", "Measure name"), ("score", "Score"), ("score_type", "Score type"), ("percentile", "Percentile rank"), ("ci", "Confidence interval (e.g., 87–97)"), ("category", "Entered / imported category"), ("age_eq", "Age equivalent"), ("grade_eq", "Grade equivalent"), ("raw_score", "Raw score (reference only)"), ("aliases", "Other matching names (separate with ;)"))
        variables = {}
        for i, (key, title) in enumerate(fields):
            cell = ttk.Frame(frame, padding=(0, 0, 14, 12))
            cell.grid(row=i // 2, column=i % 2, sticky="ew")
            ttk.Label(cell, text=title, style="Tiny.TLabel").pack(anchor="w", pady=(0, 5))
            value = "; ".join(existing.aliases) if key == "aliases" else number(existing.score) if key == "score" else SCORE_TYPES.get(existing.score_type) if key == "score_type" else getattr(existing, key)
            var = variables[key] = tk.StringVar(value=value)
            if key == "score_type":
                widget = ttk.Combobox(cell, textvariable=var, values=list(SCORE_TYPES.values()), state="readonly", width=23)
            else:
                widget = ttk.Entry(cell, textvariable=var, width=27)
            widget.pack(fill="x")
            frame.columnconfigure(i % 2, weight=1)
        ttk.Label(frame, text="Categories entered here take precedence when “Imported labels, then cutoff rules” is selected. All matching names must be unique.", style="Muted.TLabel", wraplength=590).grid(row=5, column=0, columnspan=2, sticky="w", pady=8)
        def commit():
            try:
                values = {key: var.get().strip() for key, var in variables.items()}
                score = float(values.pop("score"))
                aliases = [name.strip() for name in values.pop("aliases").split(";") if name.strip()]
                kind = {v: k for k, v in SCORE_TYPES.items()}[values.pop("score_type")]
                row = Score(**values, score=score, score_type=kind, aliases=aliases, source=existing.source if index is not None else "Manual entry")
                trial = list(self.scores)
                if index is None:
                    trial.append(row)
                else:
                    trial[index] = row
                renderer = Renderer(self.active_test, trial, self.rules)
                if renderer.errors:
                    raise ValueError("\n".join(renderer.errors))
                self.scores = trial
                self.refresh_scores()
                self.changed()
                popup.destroy()
            except Exception as error:
                messagebox.showerror("Check score", str(error), parent=popup)
        ttk.Button(frame, text="Save score", style="Primary.TButton", command=commit).grid(row=6, column=1, sticky="e", pady=15)

    def remove_scores(self):
        selected = self.tree.selection()
        if selected and messagebox.askyesno("Remove scores?", f"Remove {len(selected)} selected score row(s)?", parent=self):
            indices = {int(value) for value in selected}
            self.scores = [row for i, row in enumerate(self.scores) if i not in indices]
            self.refresh_scores()
            self.changed()

    def set_editor(self, text):
        self.updating_editor = True
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", text)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.updating_editor = False
        self.template_note.set("Word template · original document formatting retained on export" if self.template.docx_bytes else "Text template · you can type or paste here")

    def editor_changed(self, _event=None):
        if self.editor.edit_modified():
            if not self.updating_editor:
                self.changed()
                if self.template.docx_bytes and self.editor.get("1.0", "end-1c") != self.template.original_text:
                    self.template_note.set("Text edited · Word export will use a fresh document with standard formatting")
            self.editor.edit_modified(False)

    def import_template(self):
        path = filedialog.askopenfilename(parent=self, title="Import your report template", filetypes=[("Report templates", "*.docx *.txt *.md")])
        if not path:
            return
        try:
            template = load_template(path)
            if self.editor.get("1.0", "end-1c").strip() and not messagebox.askyesno("Replace template?", "Replace the current template text?", parent=self):
                return
            self.template = template
            self.set_editor(template.text)
            self.changed()
            self.show_step("template")
        except Exception as error:
            messagebox.showerror("Could not import template", str(error), parent=self)

    def insert_token(self):
        if self.token_measure.get():
            self.editor.insert("insert", "{{" + self.token_measure.get() + "." + self.token_attr.get() + "}}")
            self.editor.focus_set()

    def refresh_rules(self):
        self.rules_draft = deepcopy(self.rules)
        self.rule_group_combo.configure(values=("Named measure",) if self.active_test == "PAI" else ("Standard scores", "Scaled scores", "Named measure"))
        self.rule_group.set("Named measure" if self.active_test == "PAI" else "Standard scores")
        names = list(dict.fromkeys([row.name for row in self.scores] + list(self.rules["overrides"])))
        self.rule_name_combo.configure(values=names)
        if names:
            self.rule_name.set(names[0])
        else:
            self.rule_name.set("")
        self.refresh_bands()
        if self.active_test == "PAI":
            self.rules_note.set('PAI uses imported categories or rules for a named scale. Choose a scale below and enter your verified cutoffs. No universal PAI category is applied.')
        else:
            self.rules_note.set('Confirm these reporting labels and boundaries against your edition and norm group. You can change “Low average” to “Below average,” for example. Rules for a named measure take precedence over general score rules.')

    def band_scope(self):
        if self.rule_group.get() == "Named measure":
            name = self.rule_name.get().strip()
            if not name:
                return None, None
            return self.rules_draft["overrides"], name
        return self.rules_draft, "scaled" if self.rule_group.get() == "Scaled scores" else "standard"

    def refresh_bands(self):
        self.rule_name_combo.configure(state="normal" if self.rule_group.get() == "Named measure" else "disabled")
        self.band_tree.delete(*self.band_tree.get_children())
        container, key = self.band_scope()
        if container is not None:
            for i, band in enumerate(container.get(key, [])):
                self.band_tree.insert("", "end", iid=str(i), values=(band["min"], band["max"], band["label"]))

    def edit_band(self, editing=False):
        container, key = self.band_scope()
        if container is None:
            messagebox.showinfo("Choose a measure", "Select or type a scale or subtest name first.", parent=self)
            return
        selected = self.band_tree.selection()
        if editing and not selected:
            return
        index = int(selected[0]) if editing else None
        original = container[key][index] if editing else {"min": "", "max": "", "label": ""}
        popup = tk.Toplevel(self)
        popup.title("Category cutoff")
        popup.geometry("420x320")
        popup.transient(self)
        popup.grab_set()
        frame = ttk.Frame(popup, padding=24)
        frame.pack(fill="both", expand=True)
        variables = {}
        for row, (field, title) in enumerate((("min", "Lowest score (included)"), ("max", "Highest score (included)"), ("label", "Category label"))):
            ttk.Label(frame, text=title).grid(row=row * 2, column=0, sticky="w")
            variables[field] = tk.StringVar(value=str(original[field]))
            ttk.Entry(frame, textvariable=variables[field], width=34).grid(row=row * 2 + 1, column=0, sticky="ew", pady=(5, 10))
        def commit():
            try:
                band = {"min": int(variables["min"].get()), "max": int(variables["max"].get()), "label": variables["label"].get().strip()}
                trial = deepcopy(self.rules_draft)
                target = trial["overrides"] if self.rule_group.get() == "Named measure" else trial
                target.setdefault(key, [])
                if index is None:
                    target[key].append(band)
                else:
                    target[key][index] = band
                target[key].sort(key=lambda item: item["min"])
                errors = validate_rules(trial, self.active_test)
                if errors:
                    raise ValueError("\n".join(errors))
                self.rules_draft = trial
                self.changed()
                self.refresh_bands()
                popup.destroy()
            except Exception as error:
                messagebox.showerror("Check cutoff", str(error), parent=popup)
        ttk.Button(frame, text="Save category", style="Primary.TButton", command=commit).grid(row=6, column=0, sticky="e", pady=(3, 0))

    def remove_bands(self):
        selected = self.band_tree.selection()
        container, key = self.band_scope()
        if selected and container is not None:
            indices = {int(value) for value in selected}
            container[key] = [band for i, band in enumerate(container[key]) if i not in indices]
            # Remove an empty named override so the general bands apply again.
            if not container[key] and container is self.rules_draft["overrides"]:
                del container[key]
            self.refresh_bands()
            self.changed()

    def apply_rules(self, silent=False):
        try:
            config = deepcopy(self.rules_draft)
            errors = validate_rules(config, self.active_test)
            if errors:
                raise ValueError("\n".join(errors))
            # Also resolve per-measure aliases to catch overlapping named overrides.
            for row in self.scores:
                category_for(row, config, self.options()["policy"], self.active_test)
            if config != self.rules:
                self.rules = config
                self.changed()
            self.refresh_scores()
            if not silent:
                self.status.set(f"{self.active_test} · Cutoff rules applied")
            return True
        except Exception as error:
            messagebox.showerror("Check cutoff rules", str(error), parent=self)
            return False

    def policy_changed(self):
        self.changed()
        self.refresh_scores()

    def reset_rules(self):
        if messagebox.askyesno("Reset rules?", "Replace custom cutoffs with the default reporting conventions for this test?", parent=self):
            self.rules = defaults(self.active_test)
            self.refresh_rules()
            self.refresh_scores()
            self.changed()

    def import_rules(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("Cutoff rules", "*.json")])
        if path:
            try:
                config = json.loads(Path(path).read_text(encoding="utf-8"))
                errors = validate_rules(config, self.active_test)
                if errors:
                    raise ValueError("\n".join(errors))
                self.rules_draft = config
                self.apply_rules()
                self.refresh_rules()
            except Exception as error:
                messagebox.showerror("Could not import rules", str(error), parent=self)

    def export_rules(self):
        if not self.apply_rules(silent=True):
            return
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".json", initialfile=f"{self.active_test}_cutoffs.json")
        if path:
            try:
                Path(path).write_text(json.dumps(self.rules, indent=2, ensure_ascii=False), encoding="utf-8")
            except OSError as error:
                messagebox.showerror("Could not export rules", str(error), parent=self)

    def generate(self):
        if not self.scores:
            raise ValueError("Import or enter scores first.")
        template = self.current_template()
        if not template.text.strip():
            raise ValueError("Import or write your report template first.")
        renderer = self.renderer()
        result = renderer.render(template.text)
        errors, warnings = review(self.active_test, self.scores, self.rules, self.options()["policy"])
        result.errors = list(dict.fromkeys(result.errors + errors))
        result.warnings = list(dict.fromkeys(result.warnings + warnings + self.import_notes))
        missing = missing_mentions(self.active_test, template.text, self.scores)
        if missing:
            result.warnings.append("Names without score rows: " + ", ".join(missing) + ". These mentions are unchanged.")
        return result

    def preview(self):
        try:
            result = self.generate()
            self.last_preview = result.text
            self.preview_text.configure(state="normal")
            self.preview_text.delete("1.0", "end")
            self.preview_text.insert("1.0", result.text)
            shift = 0
            for edit in result.edits:
                start = edit.start + shift
                end = start + len(edit.replacement)
                self.preview_text.tag_add("inserted", f"1.0+{start}c", f"1.0+{end}c")
                shift += len(edit.replacement) - (edit.end - edit.start)
            self.preview_text.configure(state="disabled")
            self.preview_status.set(f"{len(result.edits)} insertions    ·    {len(result.errors)} errors    ·    {len(result.warnings)} review notes")
            messages = ["ERROR: " + value for value in result.errors] + result.warnings
            self.review_box.configure(state="normal")
            self.review_box.delete("1.0", "end")
            self.review_box.insert("1.0", "\n".join(messages) or "All requested values are filled. Review the narrative before exporting.")
            self.review_box.configure(state="disabled")
            return result
        except Exception as error:
            self.preview_status.set(str(error))
            self.last_preview = ""
            self.preview_text.configure(state="normal")
            self.preview_text.delete("1.0", "end")
            self.preview_text.configure(state="disabled")
            return None

    def export_ready(self):
        if self.step == "rules" and not self.apply_rules(silent=True):
            return None
        result = self.preview()
        if result is None:
            messagebox.showinfo("Complete the report", self.preview_status.get(), parent=self)
            return None
        if result.errors:
            self.show_notes("Resolve these fields before exporting", result.errors)
            return None
        if result.warnings and not messagebox.askyesno("Review report notes", f"There are {len(result.warnings)} review notes shown in the preview. Have you reviewed them and want to continue?", parent=self):
            return None
        return result

    def copy_report(self):
        result = self.export_ready()
        if result:
            self.clipboard_clear()
            self.clipboard_append(result.text)
            self.status.set("Report copied")

    def export_text(self):
        result = self.export_ready()
        if not result:
            return
        path = filedialog.asksaveasfilename(parent=self, title="Export report text", defaultextension=".txt", initialfile=f"{self.active_test}_report.txt")
        if path:
            try:
                Path(path).write_text(result.text, encoding="utf-8")
                self.status.set(f"Exported {Path(path).name}")
            except OSError as error:
                messagebox.showerror("Could not export report", str(error), parent=self)

    def export_word(self):
        result = self.export_ready()
        if not result:
            return
        try:
            payload, rendered = render_docx(self.current_template(), self.renderer())
            if rendered.errors:
                self.show_notes("Resolve Word template fields", rendered.errors)
                return
            # Includes header/footer edits which are absent from the plain-text preview.
            extra_notes = [note for note in rendered.warnings if note not in result.warnings]
            if extra_notes:
                self.show_notes("Word template review", extra_notes)
                if not messagebox.askyesno("Continue Word export?", "Continue after reviewing the additional Word template notes?", parent=self):
                    return
            path = filedialog.asksaveasfilename(parent=self, title="Export Word document", defaultextension=".docx", initialfile=f"{self.active_test}_report.docx", filetypes=[("Word document", "*.docx")])
            if path:
                Path(path).write_bytes(payload)
                self.status.set(f"Exported {Path(path).name}")
        except Exception as error:
            messagebox.showerror("Could not export Word document", str(error), parent=self)

    def save(self, save_as=False):
        if self.step == "rules" and not self.apply_rules(silent=True):
            return False
        path = self.project_path if self.project_path and not save_as else filedialog.asksaveasfilename(parent=self, title="Save Measure project", defaultextension=".measure.json", initialfile=f"{self.active_test}_project.measure.json", filetypes=[("Measure project", "*.measure.json")])
        if not path:
            return False
        try:
            save_project(path, self.active_test, self.scores, self.current_template(), self.rules, self.options())
            self.project_path, self.dirty = path, False
            self.status.set(f"Saved {Path(path).name}")
            return True
        except Exception as error:
            messagebox.showerror("Could not save project", str(error), parent=self)
            return False

    def open(self):
        if self.dirty and not messagebox.askyesno("Open another project?", "Discard unsaved changes and open a project?", parent=self):
            return
        path = filedialog.askopenfilename(parent=self, title="Open Measure project", filetypes=[("Measure project", "*.measure.json *.json")])
        if path:
            try:
                test, scores, template, rules, options = load_project(path)
                self.active_test = test
                self.test.set(test)
                self.scores, self.template, self.rules = scores, template, rules
                for variable, name in ((self.auto, "auto_insert"), (self.pr, "include_percentile"), (self.ci, "include_ci"), (self.first, "first_only")):
                    variable.set(options.get(name, name in ("auto_insert", "include_percentile")))
                self.policy.set("Imported labels, then cutoff rules" if options.get("policy", "imported") == "imported" else "Cutoff rules only")
                self.import_notes = []
                self.set_editor(template.text)
                self.refresh_scores()
                self.refresh_rules()
                self.project_path, self.dirty = path, False
                self.status.set(f"Opened {Path(path).name}")
                self.show_step("scores")
            except Exception as error:
                messagebox.showerror("Could not open project", str(error), parent=self)

    def demo(self):
        if self.dirty and not messagebox.askyesno("Load example?", "Replace current work with fictional WIAT-4 example data?", parent=self):
            return
        self.active_test = "WIAT-4"
        self.test.set(self.active_test)
        self.rules = defaults(self.active_test)
        self.policy.set("Imported labels, then cutoff rules")
        self.auto.set(True)
        self.pr.set(True)
        self.ci.set(False)
        self.first.set(False)
        self.scores = [Score(name, value, percentile=pr, ci=ci, source="Fictional example data") for name, value, pr, ci in (
            ("Total Achievement", 96, "39", "91–101"), ("Reading", 92, "30", "87–97"),
            ("Written Expression", 84, "14", "78–90"), ("Mathematics", 109, "73", "103–115"),
            ("Word Reading", 92, "30", "87–97"), ("Reading Comprehension", 95, "37", "88–102"),
        )]
        self.template = Template(DEMO_TEXT)
        self.project_path, self.import_notes = None, []
        self.set_editor(DEMO_TEXT)
        self.refresh_rules()
        self.refresh_scores()
        self.changed()
        self.show_step("scores")
        self.status.set("Fictional example · Edit scores or continue to the template")

    def show_notes(self, title, notes):
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.geometry("780x440")
        popup.transient(self)
        frame = ttk.Frame(popup, padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=title, style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
        wrapper, text = self._editor(frame, (FONT, 11))
        wrapper.pack(fill="both", expand=True)
        text.insert("1.0", "\n\n".join(notes))
        text.configure(state="disabled")
        ttk.Button(frame, text="Close", command=popup.destroy).pack(anchor="e", pady=(12, 0))

    def help(self):
        self.show_notes("Getting started", [
            "1. Select WIAT-4, WAIS-5, WAIS-IV, or PAI. Import a score table, paste cells from Word/Excel, or enter scores manually. Map the name and score columns, plus any other fields.",
            "2. Review the imported scores and score types. Double-click a row to edit it. Choose category cutoffs and labels under Cutoff rules.",
            "3. Import a .docx/.txt template or paste your wording. Automatic mode adds a parenthetical score after each matching measure name. Use {{Measure.score}}, {{Measure.category}}, {{Measure.percentile}}, {{Measure.ci}}, or {{Measure.summary}} for exact placement.",
            "4. Review the highlighted insertions and any notes. Copy or export your report to Word or text. Save a project to reuse the template, scores, and rules together.",
            "Word templates retain ordinary paragraph/run formatting and tables when the imported template is not edited in the text editor. Editing its text creates a fresh Word document on export. Text boxes, tracked changes, content controls, and complex fields may require a simpler template.",
            "Measure copies already-scored results. It does not calculate norms, percentile ranks, confidence intervals, diagnoses, or clinical interpretations. PAI category cutoffs must be supplied per scale. No report data is sent to a server. Saved project and report files contain the data you entered.",
        ])

    def close(self):
        rules_changed = self.step == "rules" and self.rules_draft != self.rules
        if self.dirty or rules_changed:
            answer = messagebox.askyesnocancel("Save your project?", "Save changes before closing Measure?", parent=self)
            if answer is None or (answer and not self.save()):
                return
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description="Measure: local test report assembly")
    parser.add_argument("--demo", action="store_true", help="Start with fictional example scores")
    args = parser.parse_args()
    app = App()
    if args.demo:
        app.demo()
    app.mainloop()
