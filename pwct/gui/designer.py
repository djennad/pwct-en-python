"""The Component Designer: the Transporter Designer and the Interaction
Designer of PWCT, working on one component (``.pwc``) at a time.

* Interaction Designer (``interd.scx`` / ``ipwriter.scx``): the controls of
  the interaction page - added with the buttons of the PWCT script commands
  (TITLE, SMALLGET, LARGEGET, LISTBOX, CHECKBOX, ENTER ...) - their
  properties and a live preview of the page.
* Transporter Designer (``transd.scx``): the component information
  ("Install Component"), the interaction pages, the code mask, the matching
  of page variables with code mask variables, and a test of the component.
"""

import copy
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from ..engine import Project, ProjectError, TemplateError, generate
from ..engine.components import (INPUT_KINDS, KEY_RE, Component, Field, mask_variables,
                                 matching, page_variables, parse_component, user_dir)
from ..engine.legacy import import_trf, isf_fields
from ..engine.template import DIRECTIVE_RE, PLACEHOLDER_RE, expand
from . import theme
from .interaction import InteractionForm, InteractionPage, split_pages

# toolbox of the Interaction Designer: (button, kind, PWCT script command)
TOOLBOX = [("TITLE", "title"), ("SMALLGET", "small"), ("LARGEGET", "text"), ("MEMO", "memo"),
           ("LISTBOX", "list"), ("LISTINDEX", "listindex"), ("CHECKBOX", "check"),
           ("ENTER", "enter"), ("PAGE", "page"), ("HELP", "help")]
KINDS = [k for _b, k in TOOLBOX]
KIND_NAMES = {"title": "Title", "small": "Small TextBox", "text": "TextBox", "memo": "EditBox",
              "list": "ListBox (item)", "listindex": "ListBox (number)", "check": "CheckBox",
              "enter": "New Row", "page": "New Page", "help": "Help Text"}

DIRECTIVES = [
    ("NEWSTEP", "<PWCT:NEWSTEP> Step title", "Create a new step; the next code lines belong to it"),
    ("INFORMATION", "<PWCT:INFORMATION> text", "An information line for the step"),
    ("PUTMARK", "<PWCT:PUTMARK> 2", "Remember the last created step as mark 2"),
    ("SETMARK", "<PWCT:SETMARK> 2", "The next steps are created inside mark 2 (1 = insertion point)"),
    ("IF", "<PWCT:IF> <var>\n\n<PWCT:ELSE>\n\n<PWCT:ENDIF>", "Keep lines when a condition is true"),
    ("TEST", "<PWCT:VALUE> 1\n<PWCT:POSITIVE>\n<PWCT:TEST> <var>\n\n<PWCT:ENDTEST>",
     "RPWI test block: keep lines when the value is found"),
    ("FOREACH", "<PWCT:FOREACH> item in <var>\n<item>\n<PWCT:ENDFOREACH>",
     "Repeat lines for every comma separated item"),
    ("IMPORT", "<PWCT:IMPORT> module", "The step needs 'import module' at the top of the file"),
    ("NEWVAR", "<PWCT:NEWVAR> name\n<PWCT:SETVARVALUE> value", "A variable computed in the template"),
    ("NOTE", "<PWCT:NOTE> ", "A comment inside the template"),
]

SYNTAX_HELP = """Code Mask (template) syntax

Every line that is not a directive is Python code.
<name> is replaced with the value of the interaction page variable "name".
Filters:  <name|repr>  a Python string        <name|ident>  a valid identifier
          <name|space> add a space at the end  <name|name>   text before = or :
          <name|comment> lines start with #    <name|upper> <name|lower> <name|strip>

Steps
  <PWCT:NEWSTEP> title      create a step, the next code lines belong to it
  <PWCT:PUTMARK> n          remember the last created step as mark n (2..30)
  <PWCT:SETMARK> n          the next steps are created inside mark n
                            (mark 1 is the place where the component is added)
  <PWCT:INFORMATION> text   information shown in Step Details
  <PWCT:IMPORT> module      import written once at the top of the program
  <PWCT:IGNORELAST> c       remove a trailing c from the last code line
  <PWCT:TABPUSH> / <PWCT:TABPOP>   indent / unindent the next lines

Children of a step continue at the indentation where the step code ends,
one level deeper after ':'.  "pass" is added to empty blocks.

Conditions
  <PWCT:IF> <kind> == Text      (also !=, one value, or: not <value>)
  <PWCT:ELSE>
  <PWCT:ENDIF>
  One value is true unless it is empty, 0, false, no or none.

  RPWI form:  <PWCT:VALUE> 1   <PWCT:POSITIVE>   <PWCT:TEST> <check>
              ...              <PWCT:ENDTEST>    (NEGATIVE: keep when not found)

Variables made in the template
  <PWCT:NEWVAR> code           <PWCT:SETVARVALUE> text    <PWCT:SELECTVAR> code

Repetition
  <PWCT:FOREACH> a in <attrs>
  self.<a|name> = <a|name>
  <PWCT:ENDFOREACH>

The <RPWI:...> spelling of the original PWCT works too.
"""

NEW_TEMPLATE = "<PWCT:NEWSTEP> Print <msg>\nprint(<msg|repr>)"


def new_component():
    return Component("user/new_component", "New Component", "My Components", "",
                     [Field("title", label="New Component"),
                      Field("text", "msg", "Message", "Hello")], NEW_TEMPLATE)


class ComponentStudio:
    """The component being designed and the actions shared by the two
    designers (New, Open, Save, Install ...)."""

    def __init__(self, app):
        self.app = app
        self.component = new_component()
        self.file = None          # a .pwc file outside the library (Save As)
        self.dirty = False
        self.views = []

    # ------------------------------------------------------------ changes
    def changed(self, source=None):
        self.dirty = True
        for view in self.views:
            if view is not source:
                view.load()
        self.app.update_title()

    def set_component(self, component, file=None):
        self.component = component
        self.file = file
        self.dirty = False
        for view in self.views:
            view.load()
        self.app.update_title()

    def origin(self):
        comp = self.component
        if self.file:
            return "File : " + self.file
        if comp.path and comp.builtin:
            return "Built-in component : %s.pwc" % comp.key
        if comp.path:
            return "Installed component : " + comp.path
        return "File : (NO NAME)"

    def confirm_discard(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel("Component Designer",
                                           "Save the changes of the component \"%s\"?"
                                           % self.component.name, parent=self.app)
        if answer is None:
            return False
        return self.save() if answer else True

    # ------------------------------------------------------------ actions
    def new(self):
        if self.confirm_discard():
            self.set_component(new_component())

    def open_library(self, key=None):
        """Open a component of the library (a copy)."""
        if not self.confirm_discard():
            return
        if key is None:
            from .browser import ComponentBrowser
            key = ComponentBrowser(self.app, self.app.library, self.app.insert_mode, self.app.fonts,
                                   self.app.icons, title="Open Component").run()
        if key:
            self.set_component(copy.deepcopy(self.app.library[key]))

    def open_file(self, path=None):
        if not self.confirm_discard():
            return
        path = path or filedialog.askopenfilename(
            parent=self.app, filetypes=[("PWCT-Python component", "*.pwc"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                comp = parse_component(fh.read(), "user/" + re.sub(r"\W", "_", os.path.splitext(
                    os.path.basename(path))[0].lower()), None)
        except (OSError, TemplateError, UnicodeDecodeError) as exc:
            messagebox.showerror("Open Component", str(exc), parent=self.app)
            return
        self.set_component(comp, file=path)

    def import_trf(self, path=None):
        if not self.confirm_discard():
            return
        path = path or filedialog.askopenfilename(
            parent=self.app, title="Import PWCT 1.x Component",
            filetypes=[("PWCT 1.x transporter", "*.trf *.TRF"), ("All files", "*.*")])
        if not path:
            return
        try:
            comp = import_trf(path)
        except Exception as exc:          # a damaged or unknown file
            messagebox.showerror("Import PWCT 1.x Component", "%s\n%s" % (path, exc), parent=self.app)
            return
        self.set_component(comp)
        self.dirty = True

    def import_isf(self, path=None):
        path = path or filedialog.askopenfilename(
            parent=self.app, title="Import Interaction Script",
            filetypes=[("PWCT interaction script", "*.isf *.ISF"), ("All files", "*.*")])
        if not path:
            return
        with open(path, encoding="cp1256", errors="replace") as fh:
            fields = isf_fields(fh.read())
        self.component.fields = fields
        self.component.layout = "flow"
        self.changed()

    def check(self):
        """Errors that prevent saving, or an empty list."""
        comp = self.component
        errors = []
        if not comp.name.strip():
            errors.append("The component needs a name.")
        if not KEY_RE.match(comp.key or ""):
            errors.append("Invalid file name %r: use letters, digits, _ and / only." % comp.key)
        names = [f.name.lower() for f in comp.fields if f.is_input]
        for f in comp.fields:
            if f.is_input and not f.name.isidentifier():
                errors.append("Invalid variable name %r." % f.name)
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            errors.append("Variables used twice: " + ", ".join(dup))
        for f in comp.fields:
            if "|" in f.label or "|" in f.default:
                errors.append("'|' can not be used in %r." % f.caption)
        try:
            parse_component(comp.to_text(), comp.key)
            expand(comp.template, comp.default_values())
        except TemplateError as exc:
            errors.append(str(exc))
        return errors

    def _report(self, title):
        errors = self.check()
        if errors:
            messagebox.showerror(title, "\n".join(errors), parent=self.app)
        return not errors

    def save(self):
        comp = self.component
        if self.file:
            if not self._report("Save"):
                return False
            with open(self.file, "w", encoding="utf-8") as fh:
                fh.write(comp.to_text())
            self.dirty = False
            self.app.update_title()
            return True
        if comp.path and not comp.builtin:
            return self.install()
        return self.save_as()

    def save_as(self):
        if not self._report("Save As"):
            return False
        path = filedialog.asksaveasfilename(
            parent=self.app, defaultextension=".pwc",
            initialfile=self.component.key.rsplit("/", 1)[-1] + ".pwc",
            filetypes=[("PWCT-Python component", "*.pwc")])
        if not path:
            return False
        self.file = path
        return self.save()

    def install(self):
        """Save the component in the user folder and add it to the library
        ("Install Component" / "Reinstall Component")."""
        if not self._report("Install Component"):
            return False
        comp = self.component
        old = self.app.library.components.get(comp.key)
        if old is not None and old.builtin and not messagebox.askyesno(
                "Install Component", "\"%s\" is a built-in component.\nYour version will replace it "
                "(Uninstall gives the built-in one back).\nContinue?" % comp.key, parent=self.app):
            return False
        try:
            # the library gets its own copy: later edits need a new Install
            path = self.app.library.install(copy.deepcopy(comp))
            comp.path = path
        except (OSError, ValueError) as exc:
            messagebox.showerror("Install Component", str(exc), parent=self.app)
            return False
        self.file = None
        self.dirty = False
        for view in self.views:
            view.load()
        self.app.library_changed()
        self.app.status.configure(text="Installed %s  ->  %s" % (comp.key, path))
        return True

    def uninstall(self):
        comp = self.component
        installed = self.app.library.components.get(comp.key)
        if installed is None or installed.builtin or not installed.path:
            messagebox.showinfo("Uninstall Component", "\"%s\" is not an installed component."
                                % comp.key, parent=self.app)
            return
        if not messagebox.askyesno("Uninstall Component", "Remove the component \"%s\"?\n%s"
                                   % (comp.name, installed.path), parent=self.app):
            return
        self.app.library.uninstall(comp.key)
        comp.path = None
        self.dirty = True
        for view in self.views:
            view.load()
        self.app.library_changed()

    def test_values(self, values=None):
        """Apply the component to an empty goal: ``(project, first step)``."""
        project = Project("Test")
        comp = copy.deepcopy(self.component)
        comp.key = comp.key or "user/test"
        step = project.apply(comp, values or {})
        return project, step


# ======================================================================
class DesignerBase(tk.Frame):
    """Common look: white header with the olive title, a cyan band with the
    green file label, and the file buttons at the bottom."""

    TITLE = ""

    def __init__(self, master, app, studio):
        super().__init__(master, background=theme.WHITE)
        self.app = app
        self.studio = studio
        self.fonts = app.fonts
        studio.views.append(self)
        head = tk.Frame(self, background=theme.WHITE)
        head.pack(side="top", fill="x")
        self.comp_label = tk.Label(head, text="", font=self.fonts.header, background=theme.WHITE,
                                   anchor="w")
        self.comp_label.pack(side="left", padx=8, pady=8)
        tk.Label(head, text=self.TITLE, font=self.fonts.title, foreground=theme.OLIVE,
                 background=theme.WHITE).pack(side="right", padx=16)
        tk.Frame(self, height=2, background=theme.GRAY).pack(side="top", fill="x")
        self.band = tk.Frame(self, background=theme.CYAN)
        self.band.pack(side="top", fill="x")
        self.file_label = tk.Label(self.band, text="", font=self.fonts.normal, background=theme.GREEN,
                                   anchor="w", padx=6)
        self.file_label.pack(side="left", padx=5, pady=5)
        self._bottom()

    def _bottom(self):
        panel = tk.Frame(self, background=theme.WHITE, padx=4, pady=6)
        panel.pack(side="bottom", fill="x")
        tk.Frame(self, height=2, background=theme.GRAY).pack(side="bottom", fill="x")
        s = self.studio
        B = self.app.make_button
        for text, icon, cmd in [(" New", "new", s.new), (" Open", "open", s.open_library),
                                (" Save", "save", s.save), (" Save As", None, s.save_as),
                                (" Install", "install", s.install), (" Uninstall", "delete", s.uninstall)]:
            B(panel, text, icon, cmd, width=92 if icon else 80).pack(side="left", padx=2)
        B(panel, "Close", "close", self.app.show_goal_designer, big=False, width=80).pack(side="right", padx=2)
        B(panel, " Test", "run", self.app.show_test, width=80).pack(side="right", padx=2)

    def load(self):
        comp = self.studio.component
        self.comp_label.configure(text="Component :  %s%s" % (comp.name, "  *" if self.studio.dirty else ""))
        self.file_label.configure(text=self.studio.origin())


# ======================================================================
class InteractionDesigner(DesignerBase):
    TITLE = "Interaction Designer"

    def __init__(self, master, app, studio):
        super().__init__(master, app, studio)
        self._loading = False
        self._preview_job = None
        f = self.fonts
        toolbox = tk.Frame(self, background=theme.FACE, relief="raised", borderwidth=1)
        toolbox.pack(side="top", fill="x")
        tk.Label(toolbox, text="Toolbox :", background=theme.FACE, font=f.bold).pack(side="left", padx=(6, 4))
        tips = {"title": "TITLE - a title bar", "small": "SMALLGET - a small text box",
                "text": "LARGEGET - a text box", "memo": "a text box with many lines",
                "list": "LISTBOX - the value is the chosen item",
                "listindex": "LISTBOX - the value is the number of the chosen item",
                "check": "CHECKBOX - the value is 1 or 0", "enter": "ENTER - start a new row",
                "page": "a new interaction page", "help": "a line of help text"}
        for text, kind in TOOLBOX:
            b = tk.Button(toolbox, text=text, font=(f.normal[0], 8, "bold"), background=theme.WHITE,
                          padx=4, command=lambda k=kind: self.add_field(k))
            b.pack(side="left", padx=1, pady=3)
            app.tooltip(b, tips[kind])
        self.layout_var = tk.StringVar(value="rows")
        for text, value in [("Flow", "flow"), ("Rows", "rows")]:
            tk.Radiobutton(toolbox, text=text, value=value, variable=self.layout_var,
                           background=theme.FACE, activebackground=theme.FACE, highlightthickness=0,
                           command=self.layout_changed, font=f.normal).pack(side="right")
        tk.Label(toolbox, text="Layout :", background=theme.FACE, font=f.normal).pack(side="right", padx=(8, 2))

        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(side="top", fill="both", expand=True, padx=4, pady=4)

        # controls list
        left = tk.Frame(panes, background=theme.WHITE)
        tk.Label(left, text="Controls", font=f.bold, background=theme.WHITE, anchor="w").pack(fill="x")
        self.list = ttk.Treeview(left, columns=("kind", "var", "caption"), show="headings",
                                 selectmode="browse", height=12, style="Domain.Treeview")
        for col, text, width in [("kind", "Control", 110), ("var", "Variable", 110), ("caption", "Caption", 150)]:
            self.list.heading(col, text=text)
            self.list.column(col, width=width, stretch=col == "caption")
        self.list.pack(fill="both", expand=True)
        self.list.bind("<<TreeviewSelect>>", lambda e: self.show_properties())
        row = tk.Frame(left, background=theme.WHITE)
        row.pack(fill="x", pady=3)
        B = app.make_button
        B(row, "", "up", lambda: self.move(-1)).pack(side="left", padx=1)
        B(row, "", "down", lambda: self.move(1)).pack(side="left", padx=1)
        B(row, " Delete", "delete", self.delete_field, width=80).pack(side="left", padx=4)
        B(row, " Copy", "new", self.duplicate_field, width=70).pack(side="left")
        panes.add(left, weight=3)

        # properties
        props = tk.Frame(panes, background=theme.WHITE, padx=8)
        tk.Label(props, text="Properties", font=f.bold, background=theme.WHITE, anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="ew")
        self.kind_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.label_var = tk.StringVar()
        self.default_var = tk.StringVar()
        self.required_var = tk.IntVar()
        grid = [("Control", ttk.Combobox(props, textvariable=self.kind_var, state="readonly",
                                         values=[KIND_NAMES[k] for k in KINDS], width=22)),
                ("Variable", tk.Entry(props, textvariable=self.name_var, width=24)),
                ("Caption", tk.Entry(props, textvariable=self.label_var, width=24)),
                ("Default", tk.Entry(props, textvariable=self.default_var, width=24))]
        for n, (text, widget) in enumerate(grid, 1):
            tk.Label(props, text=text, background=theme.FACE, anchor="w", padx=4, width=10,
                     font=f.normal).grid(row=n, column=0, sticky="ew", pady=2)
            widget.grid(row=n, column=1, sticky="ew", pady=2, padx=(4, 0))
        self.kind_box, self.name_entry, self.label_entry, self.default_entry = [w for _t, w in grid]
        self.required_check = tk.Checkbutton(props, text="Required (can not be empty)",
                                             variable=self.required_var, background=theme.WHITE,
                                             activebackground=theme.WHITE, highlightthickness=0,
                                             font=f.normal, command=self.apply_properties)
        self.required_check.grid(row=5, column=0, columnspan=2, sticky="w", pady=2)
        tk.Label(props, text="List items (one per line)", background=theme.WHITE, anchor="w",
                 font=f.normal).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.items = tk.Text(props, width=30, height=6, font=f.normal, relief="solid", borderwidth=1)
        self.items.grid(row=7, column=0, columnspan=2, sticky="nsew")
        self.items.bind("<KeyRelease>", lambda e: self.apply_properties())
        props.columnconfigure(1, weight=1)
        props.rowconfigure(7, weight=1)
        for var in (self.name_var, self.label_var, self.default_var):
            var.trace_add("write", lambda *a: self.apply_properties())
        self.kind_box.bind("<<ComboboxSelected>>", lambda e: self.apply_properties())
        panes.add(props, weight=2)

        # preview
        right = tk.Frame(panes, background=theme.WHITE)
        tk.Label(right, text="Preview", font=f.bold, background=theme.WHITE, anchor="w").pack(fill="x")
        holder = tk.Frame(right, background=theme.GRAY, padx=1, pady=1)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, background=theme.PAGE_BG, highlightthickness=0, width=380)
        ys = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        xs = ttk.Scrollbar(holder, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True)
        self.preview_page = tk.StringVar()
        self.page_box = ttk.Combobox(right, textvariable=self.preview_page, state="readonly", width=20)
        self.page_box.pack(anchor="w", pady=3)
        self.page_box.bind("<<ComboboxSelected>>", lambda e: self._show_preview_page())
        panes.add(right, weight=4)
        self.form = None
        self.load()

    # --------------------------------------------------------------- view
    def fields(self):
        return self.studio.component.fields

    def load(self):
        super().load()
        self._loading = True
        comp = self.studio.component
        self.layout_var.set(comp.layout)
        selected = self.list.selection()
        self.list.delete(*self.list.get_children())
        for n, field in enumerate(comp.fields):
            caption = field.label
            self.list.insert("", "end", iid=str(n), values=(KIND_NAMES[field.kind], field.name,
                                                             caption + (" *" if field.required else "")))
        if selected and self.list.exists(selected[0]):
            self.list.selection_set(selected[0])
        self._loading = False
        self.show_properties()
        self.schedule_preview()

    def selected_index(self):
        sel = self.list.selection()
        return int(sel[0]) if sel else None

    def show_properties(self):
        index = self.selected_index()
        self._loading = True
        field = self.fields()[index] if index is not None and index < len(self.fields()) else None
        state = "normal" if field is not None else "disabled"
        for widget in (self.name_entry, self.label_entry, self.default_entry, self.items):
            widget.configure(state="normal")
        self.kind_var.set(KIND_NAMES[field.kind] if field else "")
        self.name_var.set(field.name if field else "")
        self.label_var.set(field.label if field else "")
        self.default_var.set(field.default.replace("\n", "\\n") if field else "")
        self.required_var.set(1 if field and field.required else 0)
        self.items.delete("1.0", "end")
        if field:
            self.items.insert("1.0", "\n".join(field.options))
        is_input = field is not None and field.is_input
        self.name_entry.configure(state="normal" if is_input else "disabled")
        self.default_entry.configure(state="normal" if is_input else "disabled")
        self.items.configure(state="normal" if field and field.kind in ("list", "listindex") else "disabled")
        self.required_check.configure(state="normal" if is_input else "disabled")
        self.label_entry.configure(state="normal" if field and field.kind != "enter" else "disabled")
        self.kind_box.configure(state="readonly" if field else "disabled")
        self._loading = False

    def apply_properties(self):
        if self._loading:
            return
        index = self.selected_index()
        if index is None:
            return
        field = self.fields()[index]
        kinds = {v: k for k, v in KIND_NAMES.items()}
        old_kind = field.kind
        field.kind = kinds.get(self.kind_var.get(), field.kind)
        if field.is_input:
            field.name = self.name_var.get().strip()
            field.default = self.default_var.get().replace("\\n", "\n") if field.kind == "memo" \
                else self.default_var.get()
            field.required = bool(self.required_var.get())
            if not field.name:
                field.name = self._new_name(field.kind)
        else:
            field.name, field.default, field.required = "", "", False
        field.label = self.label_var.get() if field.kind != "enter" else ""
        field.options = [l.strip().replace(",", ";") for l in self.items.get("1.0", "end").splitlines()
                         if l.strip()] if field.kind in ("list", "listindex") else []
        caption = field.label
        self.list.item(str(index), values=(KIND_NAMES[field.kind], field.name,
                                           caption + (" *" if field.required else "")))
        if field.kind != old_kind:
            self.show_properties()
        self.studio.changed(source=self)
        self.schedule_preview()

    def layout_changed(self):
        self.studio.component.layout = self.layout_var.get()
        self.studio.changed(source=self)
        self.schedule_preview()

    # ------------------------------------------------------------ editing
    def _new_name(self, kind):
        prefix = {"small": "D_TB_", "text": "D_TB_", "memo": "D_EB_", "list": "D_LB_",
                  "listindex": "D_LB_", "check": "D_CB_"}.get(kind, "v")
        used = {f.name.lower() for f in self.fields() if f.is_input}
        n = 1
        while (prefix + str(n)).lower() in used:
            n += 1
        return prefix + str(n)

    def add_field(self, kind):
        index = self.selected_index()
        index = len(self.fields()) if index is None else index + 1
        labels = {"title": "Title", "help": "Help text", "page": "Page %d" % (
            sum(1 for f in self.fields() if f.kind == "page") + 2)}
        if kind in INPUT_KINDS:
            name = self._new_name(kind)
            field = Field(kind, name, name.split("_")[-1] if kind != "check" else "Option",
                          "0" if kind == "check" else "",
                          ["Item 1", "Item 2"] if kind in ("list", "listindex") else None)
            field.label = {"check": "Option", "list": "List", "listindex": "List"}.get(kind, "Value")
        else:
            field = Field(kind, label=labels.get(kind, ""))
        self.fields().insert(index, field)
        self.studio.changed(source=self)
        self.load()
        self.list.selection_set(str(index))
        self.list.see(str(index))

    def delete_field(self):
        index = self.selected_index()
        if index is None:
            return
        del self.fields()[index]
        self.studio.changed(source=self)
        self.load()
        if self.fields():
            self.list.selection_set(str(min(index, len(self.fields()) - 1)))

    def duplicate_field(self):
        index = self.selected_index()
        if index is None:
            return
        field = copy.deepcopy(self.fields()[index])
        if field.is_input:
            field.name = self._new_name(field.kind)
        self.fields().insert(index + 1, field)
        self.studio.changed(source=self)
        self.load()
        self.list.selection_set(str(index + 1))

    def move(self, delta):
        index = self.selected_index()
        if index is None:
            return
        new = index + delta
        fields = self.fields()
        if 0 <= new < len(fields):
            fields.insert(new, fields.pop(index))
            self.studio.changed(source=self)
            self.load()
            self.list.selection_set(str(new))

    def select_page(self, index):
        """Select the first control of page ``index`` (0 based)."""
        starts, content = [0], False
        for n, field in enumerate(self.fields()):
            if field.kind == "page":
                if content:
                    starts.append(n)
                content = True
            else:
                content = True
        target = starts[min(index, len(starts) - 1)]
        if self.list.exists(str(target)):
            self.list.selection_set(str(target))
            self.list.see(str(target))

    # ------------------------------------------------------------ preview
    def destroy(self):
        self._destroyed = True
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
            self._preview_job = None
        super().destroy()

    def schedule_preview(self):
        if getattr(self, "_destroyed", False):
            return
        if self._preview_job is not None:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(120, self.render_preview)

    def render_preview(self):
        self._preview_job = None
        current = self.form.current if self.form is not None else 0
        self.canvas.delete("all")
        if self.form is not None:
            self.form.destroy()
        comp = copy.deepcopy(self.studio.component)
        for f in comp.fields:
            if f.is_input and not f.name:
                f.name = "_"
        self.form = InteractionForm(self.canvas, comp, fonts=self.fonts, width=420)
        titles = [t for t, _f in self.form.pages]
        self.page_box.configure(values=titles)
        self.form.show_page(current)
        self.preview_page.set(titles[self.form.current] if titles else "")
        self.canvas.create_window(0, 0, window=self.form, anchor="nw")
        self.form.update_idletasks()
        self.canvas.configure(scrollregion=(0, 0, self.form.winfo_reqwidth(), self.form.winfo_reqheight()))

    def _show_preview_page(self):
        if self.form is not None:
            self.form.show_page(self.page_box.current())
            self.form.update_idletasks()
            self.canvas.configure(scrollregion=(0, 0, self.form.winfo_reqwidth(),
                                                self.form.winfo_reqheight()))


# ======================================================================
class TransporterDesigner(DesignerBase):
    TITLE = "Transporter Designer"

    def __init__(self, master, app, studio):
        super().__init__(master, app, studio)
        self._loading = False
        f = self.fonts
        B = app.make_button
        B(self.band, " Import PWCT 1.x (TRF)", "open", studio.import_trf, width=170).pack(side="right", padx=5)
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(side="top", fill="both", expand=True, padx=4, pady=4)
        self._component_tab()
        self._pages_tab()
        self._mask_tab()
        self._matching_tab()
        self._test_tab()
        self.tabs.bind("<<NotebookTabChanged>>", lambda e: self.tab_changed())
        self.load()

    # ---------------------------------------------------- Component tab
    def _component_tab(self):
        f = self.fonts
        tab = tk.Frame(self.tabs, background=theme.WHITE, padx=16, pady=12)
        self.tabs.add(tab, text="  Component  ")
        tk.Label(tab, text="Install Component", font=f.big, background=theme.WHITE).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self.meta = {}
        rows = [("name", "Name :"), ("key", "File :"), ("category", "Domain :"),
                ("description", "Description :"), ("position", "Insert :"), ("layout", "Layout :")]
        for n, (key, text) in enumerate(rows, 1):
            tk.Label(tab, text=text, background=theme.WHITE, font=f.normal, anchor="e", width=12).grid(
                row=n, column=0, sticky="e", pady=4)
            var = tk.StringVar()
            if key == "category":
                widget = ttk.Combobox(tab, textvariable=var, width=50)
            elif key == "position":
                widget = ttk.Combobox(tab, textvariable=var, state="readonly", width=20,
                                      values=["auto", "inside", "after", "before"])
            elif key == "layout":
                widget = ttk.Combobox(tab, textvariable=var, state="readonly", width=20,
                                      values=["rows", "flow"])
            else:
                widget = tk.Entry(tab, textvariable=var, width=54, font=f.normal)
            widget.grid(row=n, column=1, sticky="w", pady=4)
            var.trace_add("write", lambda *a, k=key: self.meta_changed(k))
            self.meta[key] = (var, widget)
        notes = {"key": "saved as <file>.pwc in the components folder; use / for sub folders",
                 "category": "use / for sub domains, like  GUI/Controls",
                 "position": "where the steps go: inside the active step or after it",
                 "layout": "flow: fields share a row until ENTER (like PWCT pages)"}
        for n, (key, _text) in enumerate(rows, 1):
            if key in notes:
                tk.Label(tab, text=notes[key], background=theme.WHITE, foreground="#707070",
                         font=(f.normal[0], 8)).grid(row=n, column=2, sticky="w", padx=6)
        self.state_label = tk.Label(tab, text="", background=theme.WHITE, font=f.normal,
                                    foreground=theme.NAVY, anchor="w", justify="left")
        self.state_label.grid(row=len(rows) + 1, column=0, columnspan=3, sticky="w", pady=(16, 4))
        tk.Label(tab, text="Components folder :  " + user_dir(), background=theme.WHITE,
                 foreground="#707070", font=(f.normal[0], 8)).grid(
            row=len(rows) + 2, column=0, columnspan=3, sticky="w")

    def meta_changed(self, key):
        if self._loading:
            return
        var, _w = self.meta[key]
        setattr(self.studio.component, key, var.get().strip() if key != "description" else var.get())
        self.studio.changed(source=self)
        DesignerBase.load(self)

    # ------------------------------------------------ Interaction pages
    def _pages_tab(self):
        f = self.fonts
        tab = tk.Frame(self.tabs, background=theme.WHITE, padx=12, pady=10)
        self.tabs.add(tab, text="  Interaction Pages  ")
        tk.Label(tab, text="Pages List :", background=theme.WHITE, font=f.normal).pack(anchor="w")
        body = tk.Frame(tab, background=theme.WHITE)
        body.pack(fill="both", expand=True)
        self.pages = ttk.Treeview(body, columns=("page", "controls", "vars"), show="headings",
                                  selectmode="browse", height=8, style="Domain.Treeview")
        for col, text, width in [("page", "Page", 200), ("controls", "Controls", 80),
                                 ("vars", "Variables", 380)]:
            self.pages.heading(col, text=text)
            self.pages.column(col, width=width, stretch=col == "vars")
        self.pages.pack(side="left", fill="both", expand=True)
        self.pages.bind("<Double-1>", lambda e: self.edit_page())
        buttons = tk.Frame(body, background=theme.WHITE, padx=8)
        buttons.pack(side="left", fill="y")
        B = self.app.make_button
        B(buttons, " Add", "new", self.add_page, width=110).pack(fill="x", pady=2)
        B(buttons, " Delete", "delete", self.delete_page, width=110).pack(fill="x", pady=2)
        B(buttons, " Edit", "edit", self.edit_page, width=110).pack(fill="x", pady=2)
        B(buttons, " Import ISF", "open", self.studio.import_isf, width=110).pack(fill="x", pady=(14, 2))
        tk.Label(tab, text="The pages are designed in the Interaction Designer (Edit). "
                           "Import ISF reads an interaction script of PWCT 1.x "
                           "(TITLE, SMALLGET, LARGEGET, LISTBOX, CHECKBOX, ENTER ...).",
                 background=theme.WHITE, foreground="#707070", font=(f.normal[0], 8),
                 wraplength=700, justify="left").pack(anchor="w", pady=(6, 0))

    def load_pages(self):
        self.pages.delete(*self.pages.get_children())
        for n, (title, fields) in enumerate(split_pages(self.studio.component.fields)):
            names = [x.name for x in fields if x.is_input]
            self.pages.insert("", "end", iid=str(n), values=(title, len(fields), ", ".join(names)))

    def add_page(self):
        title = simpledialog.askstring("Add Page", "Page title:", parent=self.app)
        if not title:
            return
        comp = self.studio.component
        if not any(x.kind == "page" for x in comp.fields) and comp.fields:
            comp.fields.insert(0, Field("page", label="Page 1"))
        comp.fields.append(Field("page", label=title))
        comp.fields.append(Field("title", label=title))
        self.studio.changed()

    def delete_page(self):
        sel = self.pages.selection()
        if not sel:
            return
        index = int(sel[0])
        comp = self.studio.component
        pages = split_pages(comp.fields)
        if not messagebox.askyesno("Delete Page", "Delete the page \"%s\" and its controls?"
                                   % pages[index][0], parent=self.app):
            return
        keep = []
        for n, (title, fields) in enumerate(pages):
            if n != index:
                if len(pages) > 2 or any(x.kind == "page" for x in comp.fields[:1]):
                    keep.append(Field("page", label=title))
                keep.extend(fields)
        if len(pages) - 1 <= 1:
            keep = [x for x in keep if x.kind != "page"]
        comp.fields = keep
        self.studio.changed()

    def edit_page(self):
        sel = self.pages.selection()
        self.app.show_interaction_designer()
        if sel:
            self.app.interaction_designer.select_page(int(sel[0]))

    # --------------------------------------------------------- Code mask
    def _mask_tab(self):
        f = self.fonts
        tab = tk.Frame(self.tabs, background=theme.WHITE, padx=8, pady=6)
        self.tabs.add(tab, text="  Code Mask  ")
        tools = tk.Frame(tab, background=theme.WHITE)
        tools.pack(fill="x")
        tk.Label(tools, text="Code :", background=theme.WHITE, font=f.normal).pack(side="left")
        for name, text, tip in DIRECTIVES:
            b = tk.Button(tools, text=name, font=(f.normal[0], 8, "bold"), background=theme.FACE,
                          padx=3, command=lambda t=text: self.insert_directive(t))
            b.pack(side="left", padx=1)
            self.app.tooltip(b, tip)
        tk.Button(tools, text="Syntax Window", font=f.button, background=theme.FACE,
                  command=self.syntax_window).pack(side="right")

        body = tk.Frame(tab, background=theme.WHITE)
        body.pack(fill="both", expand=True, pady=(4, 0))
        side = tk.Frame(body, background=theme.WHITE)
        side.pack(side="right", fill="y", padx=(6, 0))
        tk.Label(side, text="Page variables\n(double click to insert)", background=theme.WHITE,
                 font=(f.normal[0], 8), justify="left").pack(anchor="w")
        self.var_list = tk.Listbox(side, width=24, font=f.normal, exportselection=False)
        self.var_list.pack(fill="y", expand=True)
        self.var_list.bind("<Double-1>", lambda e: self.insert_variable())
        self.filter_var = tk.StringVar(value="(no filter)")
        ttk.Combobox(side, textvariable=self.filter_var, state="readonly", width=20,
                     values=["(no filter)", "repr", "ident", "space", "name", "comment", "upper",
                             "lower", "strip"]).pack(fill="x", pady=(4, 0))

        editor = tk.Frame(body, background=theme.GRAY, padx=1, pady=1)
        editor.pack(side="left", fill="both", expand=True)
        self.mask = tk.Text(editor, font=f.code, wrap="none", undo=True, relief="flat")
        ys = ttk.Scrollbar(editor, orient="vertical", command=self.mask.yview)
        xs = ttk.Scrollbar(editor, orient="horizontal", command=self.mask.xview)
        self.mask.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.mask.pack(fill="both", expand=True)
        self.mask.tag_configure("directive", foreground="#800080", font=(f.code[0], f.code[1], "bold"))
        self.mask.tag_configure("variable", foreground="#0000c0")
        self.mask.tag_configure("comment", foreground="#008000")
        self.mask.bind("<<Modified>>", self._mask_modified)
        self.mask.bind("<Tab>", lambda e: (self.mask.insert("insert", "    "), "break")[1])
        self.mask_error = tk.Label(tab, text="", background=theme.WHITE, foreground="#c00000",
                                   anchor="w", font=f.normal)
        self.mask_error.pack(fill="x")

    def _mask_modified(self, event=None):
        if not self.mask.edit_modified():
            return
        self.mask.edit_modified(False)
        self.highlight_mask()
        text = self.mask.get("1.0", "end-1c")
        if self._loading or text == self.studio.component.template:
            return
        self.studio.component.template = text
        self.studio.changed(source=self)
        DesignerBase.load(self)
        self.check_mask()

    def highlight_mask(self):
        for tag in ("directive", "variable", "comment"):
            self.mask.tag_remove(tag, "1.0", "end")
        for n, line in enumerate(self.mask.get("1.0", "end-1c").splitlines(), 1):
            stripped = line.lstrip()
            start = len(line) - len(stripped)
            if DIRECTIVE_RE.match(line):
                end = line.index(">", start) + 1
                self.mask.tag_add("directive", "%d.%d" % (n, start), "%d.%d" % (n, end))
            elif stripped.startswith("#"):
                self.mask.tag_add("comment", "%d.%d" % (n, start), "%d.end" % n)
            for m in PLACEHOLDER_RE.finditer(line):
                self.mask.tag_add("variable", "%d.%d" % (n, m.start()), "%d.%d" % (n, m.end()))

    def check_mask(self):
        try:
            expand(self.studio.component.template, self.studio.component.default_values())
            self.mask_error.configure(text="")
        except TemplateError as exc:
            self.mask_error.configure(text="Error: %s" % exc)

    def insert_directive(self, text):
        line_start = self.mask.index("insert linestart")
        if self.mask.get(line_start, "insert").strip():
            self.mask.insert("insert lineend", "\n")
            self.mask.mark_set("insert", "insert +1 line linestart")
        self.mask.insert("insert", text)
        self.mask.focus_set()

    def insert_variable(self):
        sel = self.var_list.curselection()
        if not sel:
            return
        name = self.var_list.get(sel[0])
        filt = self.filter_var.get()
        self.mask.insert("insert", "<%s%s>" % (name, "" if filt.startswith("(") else "|" + filt))
        self.mask.focus_set()

    def syntax_window(self):
        win = tk.Toplevel(self)
        win.title("Code Mask Syntax")
        text = tk.Text(win, width=84, height=40, font=self.fonts.code)
        text.insert("1.0", SYNTAX_HELP)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)

    # ---------------------------------------------------------- Matching
    def _matching_tab(self):
        f = self.fonts
        tab = tk.Frame(self.tabs, background=theme.WHITE, padx=12, pady=8)
        self.tabs.add(tab, text="  Matching  ")
        top = tk.Frame(tab, background=theme.WHITE)
        top.pack(fill="x")
        left = tk.Frame(top, background=theme.WHITE)
        left.pack(side="left", fill="both", expand=True)
        tk.Label(left, text="Variables From Interaction Pages", background=theme.WHITE,
                 font=f.normal).pack(anchor="w")
        self.page_vars = tk.Listbox(left, height=7, exportselection=False, font=f.normal)
        self.page_vars.pack(fill="both", expand=True)
        right = tk.Frame(top, background=theme.WHITE)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))
        tk.Label(right, text="Variables From Code Mask", background=theme.WHITE,
                 font=f.normal).pack(anchor="w")
        self.mask_vars = tk.Listbox(right, height=7, exportselection=False, font=f.normal)
        self.mask_vars.pack(fill="both", expand=True)
        mid = tk.Frame(tab, background=theme.WHITE)
        mid.pack(fill="x", pady=4)
        btn = self.app.make_button(mid, " Match", "down", self.match_selected, width=100)
        btn.pack(side="left")
        tk.Label(mid, text="select a page variable and a code mask variable: the code mask "
                           "variable is renamed to the page variable",
                 background=theme.WHITE, foreground="#707070", font=(f.normal[0], 8)).pack(side="left", padx=8)
        self.match_grid = ttk.Treeview(tab, columns=("page", "mask", "status"), show="headings",
                                       height=8, style="Domain.Treeview")
        for col, text, width in [("page", "Interaction Page Variable", 220),
                                 ("mask", "Code Mask Variable", 220), ("status", "Status", 260)]:
            self.match_grid.heading(col, text=text)
            self.match_grid.column(col, width=width)
        self.match_grid.tag_configure("bad", foreground="#c00000")
        self.match_grid.tag_configure("warn", foreground="#a06000")
        self.match_grid.pack(fill="both", expand=True)

    def load_matching(self):
        comp = self.studio.component
        self.page_vars.delete(0, "end")
        for name in page_variables(comp):
            self.page_vars.insert("end", name)
        used, _created = mask_variables(comp.template)
        self.mask_vars.delete(0, "end")
        for name in used:
            self.mask_vars.insert("end", name)
        self.match_grid.delete(*self.match_grid.get_children())
        for page, mask, status in matching(comp):
            tag = () if status in ("OK", "template variable") else (
                ("bad",) if status == "no page variable" else ("warn",))
            self.match_grid.insert("", "end", values=(page, mask, status), tags=tag)

    def match_selected(self):
        a, b = self.page_vars.curselection(), self.mask_vars.curselection()
        if not a or not b:
            return
        page, mask = self.page_vars.get(a[0]), self.mask_vars.get(b[0])
        comp = self.studio.component
        comp.template = re.sub(r"<%s((?:\|[A-Za-z_]+)*)>" % re.escape(mask),
                               lambda m: "<%s%s>" % (page, m.group(1)), comp.template, flags=re.I)
        self.studio.changed()

    # -------------------------------------------------------------- Test
    def _test_tab(self):
        f = self.fonts
        tab = tk.Frame(self.tabs, background=theme.WHITE, padx=8, pady=6)
        self.tabs.add(tab, text="  Test  ")
        tools = tk.Frame(tab, background=theme.WHITE)
        tools.pack(fill="x")
        B = self.app.make_button
        B(tools, " Default Values", "run", lambda: self.run_test(None), width=130).pack(side="left", padx=2)
        B(tools, " Interact...", "interact", self.test_interaction, width=110).pack(side="left", padx=2)
        B(tools, " Add to Goal Designer", "new", self.add_to_goal, width=170).pack(side="left", padx=12)
        self.test_status = tk.Label(tools, text="", background=theme.WHITE, font=f.normal, anchor="w")
        self.test_status.pack(side="left", padx=8)
        panes = ttk.PanedWindow(tab, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=4)
        left = tk.Frame(panes, background=theme.WHITE)
        tk.Label(left, text="Steps", background=theme.WHITE, font=f.bold).pack(anchor="w")
        self.test_tree = ttk.Treeview(left, show="tree", style="Steps.Treeview")
        self.test_tree.pack(fill="both", expand=True)
        self.test_tree.tag_configure("root", foreground=theme.STEP_COLORS["root"], font=f.tree_root)
        self.test_tree.tag_configure("step", foreground=theme.STEP_COLORS["generated"])
        panes.add(left, weight=2)
        right = tk.Frame(panes, background=theme.WHITE)
        tk.Label(right, text="Generated Code", background=theme.WHITE, font=f.bold).pack(anchor="w")
        self.test_code = tk.Text(right, font=f.code, wrap="none", relief="solid", borderwidth=1)
        self.test_code.pack(fill="both", expand=True)
        panes.add(right, weight=3)
        self.test_values_used = None

    def run_test(self, values):
        self.test_values_used = values
        self.test_tree.delete(*self.test_tree.get_children())
        self.test_code.delete("1.0", "end")
        try:
            project, _step = self.studio.test_values(values)
        except (ProjectError, TemplateError) as exc:
            self.test_status.configure(text="Error: %s" % exc, foreground="#c00000")
            return None
        icons = self.app.icons

        def add(parent, step):
            self.test_tree.insert(parent, "end", iid=step.id, text=" " + step.title, open=True,
                                  image=icons["goal" if step.parent is None else "step"],
                                  tags=("root" if step.parent is None else "step",))
            for child in step.children:
                add(step.id, child)

        add("", project.root)
        source = generate(project, header=False)[0]
        self.test_code.insert("1.0", source)
        try:
            compile(source, "<test>", "exec")
            self.test_status.configure(text="OK - %d step(s)" % (sum(1 for _ in project.root.walk()) - 1),
                                       foreground="#008000")
        except SyntaxError as exc:
            self.test_status.configure(text="Not valid Python: %s (line %s)" % (exc.msg, exc.lineno),
                                       foreground="#a06000")
        return project

    def test_interaction(self):
        values = InteractionPage(self.app, copy.deepcopy(self.studio.component), fonts=self.fonts).run()
        if values is not None:
            self.run_test(values)

    def add_to_goal(self):
        comp = copy.deepcopy(self.studio.component)
        errors = self.studio.check()
        if errors:
            messagebox.showerror("Add to Goal Designer", "\n".join(errors), parent=self.app)
            return
        installed = self.app.library.components.get(comp.key)
        self.app.show_goal_designer()
        self.app.add_component_object(comp)
        if installed is None or installed.to_text() != comp.to_text():
            self.app.status.configure(text="Install the component to Modify these steps later "
                                           "with this version of the component.")

    # -------------------------------------------------------------- load
    def load(self):
        super().load()
        comp = self.studio.component
        self._loading = True
        for key, (var, widget) in self.meta.items():
            var.set(getattr(comp, key))
        self.meta["category"][1].configure(values=self.app.library.domains())
        self.state_label.configure(text=self._state_text())
        if self.mask.get("1.0", "end-1c") != comp.template:
            self.mask.delete("1.0", "end")
            self.mask.insert("1.0", comp.template)
            self.mask.edit_modified(False)
            self.mask.edit_reset()
            self.highlight_mask()
        self.var_list.delete(0, "end")
        for name in page_variables(comp):
            self.var_list.insert("end", name)
        self._loading = False
        self.check_mask()
        self.load_pages()
        self.load_matching()

    def _state_text(self):
        comp = self.studio.component
        lib = self.app.library.components.get(comp.key)
        if lib is None:
            return "Not installed.  Press Install to add it to the components of the Goal Designer."
        if lib.builtin:
            return "A built-in component has this file name: Install replaces it with your version."
        return "Installed: %s" % lib.path

    def tab_changed(self):
        name = self.tabs.tab(self.tabs.select(), "text").strip()
        if name == "Matching":
            self.load_matching()
        elif name == "Test":
            self.run_test(self.test_values_used)
