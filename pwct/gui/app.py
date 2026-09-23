"""The PWCT-Python environment (main window).

Left: the Goal Designer - the program as a tree of steps.
Right: the components browser, the generated code, the program output and
the details of the active step.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .. import __version__
from ..engine import History, Library, Project, ProjectError, TemplateError, generate
from ..engine.generator import step_at_line
from .interaction import InteractionPage
from .runner import Runner

FILE_TYPES = [("PWCT-Python project", "*.pwct"), ("All files", "*.*")]
CODE_FONT = ("Courier New", 10)
COLORS = {"root": "#7a0000", "generated": "#00307a", "comment": "#1c7a1c",
          "user": "#000000", "disabled": "#9a9a9a"}
INSERT_MODES = [("Auto", "auto"), ("Inside", "inside"), ("After", "after"), ("Before", "before")]


class App(tk.Tk):
    def __init__(self, path=None):
        super().__init__()
        self.library = Library.default()
        self.runner = Runner()
        self.history = History()
        self.project = Project()
        self.path = None
        self.dirty = False
        self.clipboard = None
        self.owners = []
        self.insert_mode = tk.StringVar(value="auto")

        self.title("PWCT-Python")
        self.geometry("1150x720")
        self.minsize(800, 500)
        self._styles()
        self._menu()
        self._toolbar()
        self._statusbar()
        self._body()
        self._keys()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.after(100, self._poll_runner)

        if path:
            self.open_file(path)
        else:
            self.refresh()

    # ================================================================ layout
    def _styles(self):
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("PageTitle.TLabel", font=("Arial", 14, "bold"))
        style.configure("Section.TLabel", font=("Arial", 10, "bold"), foreground="#00307a")
        style.configure("Treeview", rowheight=24)
        style.configure("Status.TLabel", padding=(6, 2))

    def _menu(self):
        bar = tk.Menu(self)
        m = tk.Menu(bar, tearoff=False)
        m.add_command(label="New", accelerator="Ctrl+N", command=self.new_file)
        m.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_dialog)
        m.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
        m.add_command(label="Save As...", command=self.save_as)
        m.add_separator()
        m.add_command(label="Export Python Code...", accelerator="Ctrl+E", command=self.export)
        m.add_command(label="Project Name...", command=self.rename_project)
        m.add_separator()
        m.add_command(label="Exit", command=self.quit_app)
        bar.add_cascade(label="File", menu=m)

        m = tk.Menu(bar, tearoff=False)
        m.add_command(label="Undo", accelerator="Ctrl+Z", command=self.undo)
        m.add_command(label="Redo", accelerator="Ctrl+Y", command=self.redo)
        m.add_separator()
        m.add_command(label="Edit Step (Interaction)", accelerator="Enter", command=self.edit_step)
        m.add_command(label="Rename Step...", accelerator="F2", command=self.rename_step)
        m.add_command(label="Delete Step", accelerator="Del", command=self.delete_step)
        m.add_separator()
        m.add_command(label="Cut", accelerator="Ctrl+X", command=self.cut)
        m.add_command(label="Copy", accelerator="Ctrl+C", command=self.copy)
        m.add_command(label="Paste", accelerator="Ctrl+V", command=self.paste)
        m.add_separator()
        m.add_command(label="Move Up", accelerator="Ctrl+Up", command=lambda: self.move(-1))
        m.add_command(label="Move Down", accelerator="Ctrl+Down", command=lambda: self.move(1))
        m.add_command(label="Move Inside Previous Step", accelerator="Ctrl+Right", command=self.indent)
        m.add_command(label="Move Out of Parent", accelerator="Ctrl+Left", command=self.outdent)
        m.add_separator()
        m.add_command(label="Enable / Disable Step", accelerator="Ctrl+D", command=self.toggle_disabled)
        m.add_command(label="Add Comment", accelerator="Ctrl+M", command=self.add_comment)
        bar.add_cascade(label="Edit", menu=m)

        m = tk.Menu(bar, tearoff=False)
        m.add_command(label="Components Browser", accelerator="Ctrl+Space", command=self.focus_components)
        m.add_command(label="Expand All", command=lambda: self._expand_all(True))
        m.add_command(label="Collapse All", command=lambda: self._expand_all(False))
        bar.add_cascade(label="View", menu=m)

        m = tk.Menu(bar, tearoff=False)
        m.add_command(label="Run", accelerator="F5", command=self.run_program)
        m.add_command(label="Stop", accelerator="Shift+F5", command=self.stop_program)
        bar.add_cascade(label="Program", menu=m)

        m = tk.Menu(bar, tearoff=False)
        m.add_command(label="How to use", command=self.show_help)
        m.add_command(label="About", command=self.show_about)
        bar.add_cascade(label="Help", menu=m)
        self.config(menu=bar)
        self.step_menu = tk.Menu(self, tearoff=False)
        for label, cmd in [("Edit Step", self.edit_step), ("Rename Step...", self.rename_step),
                           ("Delete Step", self.delete_step), (None, None),
                           ("Cut", self.cut), ("Copy", self.copy), ("Paste", self.paste), (None, None),
                           ("Move Up", lambda: self.move(-1)), ("Move Down", lambda: self.move(1)),
                           ("Enable / Disable", self.toggle_disabled), ("Add Comment", self.add_comment)]:
            if label is None:
                self.step_menu.add_separator()
            else:
                self.step_menu.add_command(label=label, command=cmd)

    def _toolbar(self):
        bar = ttk.Frame(self, padding=(4, 4))
        bar.pack(side="top", fill="x")
        for text, cmd in [("New", self.new_file), ("Open", self.open_dialog), ("Save", self.save), (None, None),
                          ("Undo", self.undo), ("Redo", self.redo), (None, None),
                          ("Edit", self.edit_step), ("Delete", self.delete_step),
                          ("Up", lambda: self.move(-1)), ("Down", lambda: self.move(1)),
                          ("Comment", self.add_comment), (None, None),
                          ("Run  ▶", self.run_program), ("Stop", self.stop_program)]:
            if text is None:
                ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
            else:
                ttk.Button(bar, text=text, command=cmd, width=len(text) + 2).pack(side="left", padx=1)

    def _body(self):
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)

        # Goal designer
        left = ttk.Frame(panes, padding=(4, 0, 0, 0))
        ttk.Label(left, text="Goal Designer", style="Section.TLabel").pack(anchor="w")
        frame = ttk.Frame(left)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, show="tree", selectmode="browse")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        for tag, color in COLORS.items():
            self.tree.tag_configure(tag, foreground=color)
        self.tree.tag_configure("root", font=("Arial", 10, "bold"))
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())
        self.tree.bind("<Double-1>", self._tree_double_click)
        self.tree.bind("<Button-3>", self._tree_menu)
        self.tree.bind("<ButtonPress-1>", self._drag_start, add="+")
        self.tree.bind("<ButtonRelease-1>", self._drag_end, add="+")
        panes.add(left, weight=3)

        # Right side
        self.tabs = ttk.Notebook(panes)
        panes.add(self.tabs, weight=4)
        self.after(150, lambda: panes.sashpos(0, 470))
        self._components_tab()
        self._code_tab()
        self._output_tab()
        self._step_tab()

    def _components_tab(self):
        tab = ttk.Frame(self.tabs, padding=6)
        self.tabs.add(tab, text="Components")
        top = ttk.Frame(tab)
        top.pack(fill="x")
        ttk.Label(top, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.fill_components())
        self.search = ttk.Entry(top, textvariable=self.search_var)
        self.search.pack(side="left", fill="x", expand=True, padx=4)
        self.search.bind("<Return>", lambda e: self.use_component())
        self.search.bind("<Down>", lambda e: self._focus_first_component())
        frame = ttk.Frame(tab)
        frame.pack(fill="both", expand=True, pady=4)
        self.comp_tree = ttk.Treeview(frame, show="tree", selectmode="browse")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.comp_tree.yview)
        self.comp_tree.configure(yscrollcommand=scroll.set)
        self.comp_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.comp_tree.tag_configure("category", font=("Arial", 10, "bold"))
        self.comp_tree.bind("<Double-1>", lambda e: self.use_component())
        self.comp_tree.bind("<Return>", lambda e: self.use_component())
        self.comp_tree.bind("<<TreeviewSelect>>", lambda e: self._describe_component())
        self.comp_desc = ttk.Label(tab, text="", wraplength=420, foreground="#555", justify="left")
        self.comp_desc.pack(fill="x")
        bottom = ttk.Frame(tab)
        bottom.pack(fill="x", pady=4)
        ttk.Label(bottom, text="Insert new steps:").pack(side="left", padx=(0, 4))
        for label, value in INSERT_MODES:
            ttk.Radiobutton(bottom, text=label, value=value, variable=self.insert_mode).pack(side="left")
        ttk.Button(bottom, text="Add to the program", command=self.use_component).pack(side="right")
        self.fill_components()

    def _code_tab(self):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Code")
        self.code = tk.Text(tab, font=CODE_FONT, wrap="none", undo=False)
        ys = ttk.Scrollbar(tab, orient="vertical", command=self.code.yview)
        xs = ttk.Scrollbar(tab, orient="horizontal", command=self.code.xview)
        self.code.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.code.pack(fill="both", expand=True)
        self.code.tag_configure("active", background="#fff3b0")
        self.code.tag_configure("comment", foreground="#1c7a1c")
        self.code.tag_configure("error", background="#ffc9c9")
        self.code.bind("<Button-1>", self._code_click)
        self.code.configure(state="disabled")

    def _output_tab(self):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Output")
        self.output = tk.Text(tab, font=CODE_FONT, wrap="word", background="#101418",
                              foreground="#e8e8e8", insertbackground="white")
        ys = ttk.Scrollbar(tab, orient="vertical", command=self.output.yview)
        self.output.configure(yscrollcommand=ys.set)
        bottom = ttk.Frame(tab, padding=4)
        bottom.pack(side="bottom", fill="x")
        ttk.Label(bottom, text="Input:").pack(side="left")
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(bottom, textvariable=self.input_var)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=4)
        self.input_entry.bind("<Return>", self.send_input)
        ttk.Button(bottom, text="Send", command=self.send_input).pack(side="left")
        ttk.Button(bottom, text="Clear", command=lambda: self.output.delete("1.0", "end")).pack(side="left")
        ys.pack(side="right", fill="y")
        self.output.pack(fill="both", expand=True)
        self.output.tag_configure("info", foreground="#7fc8ff")
        self.output.tag_configure("input", foreground="#ffd479")

    def _step_tab(self):
        tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(tab, text="Step")
        self.step_info = tk.Text(tab, font=("Arial", 10), wrap="word", height=10)
        self.step_info.pack(fill="both", expand=True)
        self.step_info.tag_configure("head", font=("Arial", 11, "bold"))
        self.step_info.tag_configure("code", font=CODE_FONT, foreground="#00307a")
        self.step_info.configure(state="disabled")

    def _statusbar(self):
        self.status = ttk.Label(self, text="", style="Status.TLabel", relief="sunken", anchor="w")
        self.status.pack(side="bottom", fill="x")

    def _keys(self):
        keys = {
            "<Control-n>": self.new_file, "<Control-o>": self.open_dialog, "<Control-s>": self.save,
            "<Control-e>": self.export, "<Control-z>": self.undo, "<Control-y>": self.redo,
            "<F5>": self.run_program, "<Shift-F5>": self.stop_program,
            "<Control-space>": self.focus_components, "<Control-m>": self.add_comment,
        }
        for key, cmd in keys.items():
            self.bind_all(key, lambda e, c=cmd: self._global_key(e, c))
        tree_keys = {
            "<Delete>": self.delete_step, "<Return>": self.edit_step, "<F2>": self.rename_step,
            "<Control-x>": self.cut, "<Control-c>": self.copy, "<Control-v>": self.paste,
            "<Control-Up>": lambda: self.move(-1), "<Control-Down>": lambda: self.move(1),
            "<Control-Right>": self.indent, "<Control-Left>": self.outdent,
            "<Control-d>": self.toggle_disabled,
        }
        for key, cmd in tree_keys.items():
            self.tree.bind(key, lambda e, c=cmd: (c(), "break")[1])

    def _global_key(self, event, command):
        """Shortcuts of the main window (not inside the interaction pages)."""
        try:
            if event.widget.winfo_toplevel() is not self:
                return None
        except (AttributeError, KeyError, tk.TclError):
            return None
        command()
        return "break"

    # ============================================================== display
    def refresh(self, select=None):
        """Redraw the goal designer and the generated code."""
        if select is None:
            select = self.tree.selection()[0] if self.tree.selection() else self.project.root.id
        opened = {i for i in self._all_items() if self.tree.item(i, "open")}
        first_time = not self.tree.get_children()
        self.tree.delete(*self.tree.get_children())
        self._insert_step("", self.project.root, opened, first_time)
        if self.tree.exists(select):
            self._reveal(select)
        else:
            self._reveal(self.project.root.id)
        self.update_code()
        self.update_title()

    def _all_items(self, parent=""):
        for item in self.tree.get_children(parent):
            yield item
            yield from self._all_items(item)

    def _insert_step(self, parent, step, opened, open_all):
        tag = self._tag(step)
        text = "  " + (step.title or "(empty)") + "  "
        if step.disabled:
            text = "  [off] " + step.title + "  "
        self.tree.insert(parent, "end", iid=step.id, text=text, tags=(tag,),
                         open=open_all or step.id in opened or step.parent is None)
        for child in step.children:
            self._insert_step(step.id, child, opened, open_all)

    def _tag(self, step):
        if step.parent is None:
            return "root"
        if step.disabled or (step.parent and self._inside_disabled(step)):
            return "disabled"
        if step.code and all(l.strip().startswith("#") for l in step.code):
            return "comment"
        return "generated" if step.interaction else "user"

    def _inside_disabled(self, step):
        while step is not None:
            if step.disabled:
                return True
            step = step.parent
        return False

    def _reveal(self, iid):
        parent = self.tree.parent(iid)
        while parent:
            self.tree.item(parent, open=True)
            parent = self.tree.parent(parent)
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.tree.see(iid)

    def _expand_all(self, value):
        for item in self._all_items():
            self.tree.item(item, open=value)

    def update_code(self):
        source, self.owners = generate(self.project)
        self.source = source
        self.code.configure(state="normal")
        self.code.delete("1.0", "end")
        self.code.insert("1.0", source)
        for n, line in enumerate(source.splitlines(), 1):
            if line.lstrip().startswith("#"):
                self.code.tag_add("comment", "%d.0" % n, "%d.end" % n)
        self.code.configure(state="disabled")
        self.highlight_code()

    def highlight_code(self):
        self.code.tag_remove("active", "1.0", "end")
        step = self.selected()
        if step is None or step.parent is None:
            return
        ids = {s.id for s in step.walk()}
        first = None
        for n, owner in enumerate(self.owners, 1):
            if owner in ids:
                self.code.tag_add("active", "%d.0" % n, "%d.0" % (n + 1))
                first = first or n
        if first:
            self.code.see("%d.0" % first)

    def update_title(self):
        name = os.path.basename(self.path) if self.path else "Untitled"
        self.title("%s%s - PWCT-Python" % ("*" if self.dirty else "", name))
        steps = sum(1 for _ in self.project.root.walk()) - 1
        self.status.configure(text="Project: %s   |   Steps: %d   |   Components: %d"
                              % (self.project.name, steps, len(self.library)))

    def selected(self):
        sel = self.tree.selection()
        return self.project.find(sel[0]) if sel else None

    def on_select(self):
        step = self.selected()
        self.highlight_code()
        self.step_info.configure(state="normal")
        self.step_info.delete("1.0", "end")
        if step is not None:
            self.step_info.insert("end", step.title + "\n", "head")
            if step.interaction and step.interaction in self.project.interactions:
                inter = self.project.interactions[step.interaction]
                comp = self.library.components.get(inter.component)
                self.step_info.insert("end", "Component: %s\n" % (comp.name if comp else inter.component))
                for key, value in inter.values.items():
                    self.step_info.insert("end", "   %s = %s\n" % (key, value))
            elif step.parent is not None:
                self.step_info.insert("end", "Step without interaction\n")
            if step.info:
                self.step_info.insert("end", "\n" + "\n".join(step.info) + "\n")
            if step.code:
                self.step_info.insert("end", "\nCode:\n")
                self.step_info.insert("end", "\n".join(step.code) + "\n", "code")
            if step.disabled:
                self.step_info.insert("end", "\nThis step is disabled (written as a comment).\n")
        self.step_info.configure(state="disabled")

    def _describe_component(self):
        sel = self.comp_tree.selection()
        comp = self.library.components.get(sel[0]) if sel else None
        self.comp_desc.configure(text=comp.description if comp else "")

    def fill_components(self):
        self.comp_tree.delete(*self.comp_tree.get_children())
        text = self.search_var.get().strip()
        comps = self.library.search(text) if text else list(self.library)
        cats = {}
        for comp in sorted(comps, key=lambda c: (c.category, c.name)):
            cats.setdefault(comp.category, []).append(comp)
        for cat, items in cats.items():
            cid = "cat:" + cat
            self.comp_tree.insert("", "end", iid=cid, text=cat, open=bool(text), tags=("category",))
            for comp in items:
                self.comp_tree.insert(cid, "end", iid=comp.key, text="  " + comp.name)

    def _focus_first_component(self):
        for cat in self.comp_tree.get_children():
            kids = self.comp_tree.get_children(cat)
            if kids:
                self.comp_tree.item(cat, open=True)
                self.comp_tree.selection_set(kids[0])
                self.comp_tree.focus(kids[0])
                self.comp_tree.focus_set()
                return "break"

    def focus_components(self):
        self.tabs.select(0)
        self.search.focus_set()
        self.search.select_range(0, "end")

    # ============================================================ mutations
    def change(self, action, *args):
        """Run a project change with undo support and error reporting."""
        snapshot = self.project.to_json()
        try:
            result = action(*args)
        except (ProjectError, TemplateError) as exc:
            self.project = Project.from_json(snapshot)
            messagebox.showerror("PWCT-Python", str(exc), parent=self)
            return None
        self.history.undo_stack.append(snapshot)
        del self.history.undo_stack[:-self.history.limit]
        self.history.redo_stack.clear()
        self.dirty = True
        return result

    def preview(self, component, values):
        temp = Project(self.project.name)
        temp.apply(component, values)
        return generate(temp, header=False)[0]

    def use_component(self):
        sel = self.comp_tree.selection()
        if not sel or sel[0].startswith("cat:"):
            found = self.library.search(self.search_var.get()) if self.search_var.get().strip() else []
            if len(found) != 1:
                return
            key = found[0].key
        else:
            key = sel[0]
        comp = self.library[key]
        values = InteractionPage(self, comp, preview=self.preview).run()
        if values is None:
            return
        mode = self.insert_mode.get()
        if mode == "auto" and comp.position != "auto":
            mode = comp.position
        parent, index = self.project.insert_position(self.selected(), mode)
        step = self.change(self.project.apply, comp, values, parent, index)
        if step is not None:
            self.refresh(select=step.id)
            self.tree.focus_set()

    def edit_step(self):
        step = self.selected()
        if step is None:
            return
        if step.parent is None or not step.interaction:
            self.rename_step()
            return
        inter = self.project.interactions.get(step.interaction)
        comp = self.library.components.get(inter.component) if inter else None
        if comp is None:
            messagebox.showwarning("Edit", "The component of this step is not available.", parent=self)
            return
        values = InteractionPage(self, comp, inter.values, editing=True, preview=self.preview).run()
        if values is None:
            return
        first = self.change(self.project.edit, step.interaction, comp, values)
        target = step.id if self.project.find(step.id) else (first.id if first else None)
        self.refresh(select=target)

    def rename_step(self):
        step = self.selected()
        if step is None:
            return
        if step.parent is None:
            self.rename_project()
            return
        title = simpledialog.askstring("Rename Step", "Step title:", initialvalue=step.title, parent=self)
        if title:
            self.change(setattr, step, "title", title)
            self.refresh()

    def rename_project(self):
        name = simpledialog.askstring("Project", "Project name:", initialvalue=self.project.name, parent=self)
        if name:
            self.change(setattr, self.project, "name", name)
            self.refresh()

    def delete_step(self):
        step = self.selected()
        if step is None or step.parent is None:
            return
        parent, index = step.parent, step.index()
        self.change(self.project.delete, step)
        siblings = parent.children
        target = siblings[min(index, len(siblings) - 1)].id if siblings else parent.id
        self.refresh(select=target)

    def move(self, delta):
        step = self.selected()
        if step is not None and step.parent is not None:
            self.change(self.project.move, step, delta)
            self.refresh(select=step.id)

    def indent(self):
        step = self.selected()
        if step is not None and step.parent is not None:
            self.change(self.project.indent, step)
            self.refresh(select=step.id)

    def outdent(self):
        step = self.selected()
        if step is not None and step.parent is not None:
            self.change(self.project.outdent, step)
            self.refresh(select=step.id)

    def toggle_disabled(self):
        step = self.selected()
        if step is not None and step.parent is not None:
            self.change(self.project.set_disabled, step, not step.disabled)
            self.refresh(select=step.id)

    def copy(self):
        step = self.selected()
        if step is not None and step.parent is not None:
            self.clipboard = self.project.copy_steps(step)
            self.status.configure(text="Copied: " + step.title)

    def cut(self):
        step = self.selected()
        if step is not None and step.parent is not None:
            self.copy()
            self.delete_step()

    def paste(self):
        if not self.clipboard:
            return
        parent, index = self.project.insert_position(self.selected(), self.insert_mode.get())
        step = self.change(self.project.paste, self.clipboard, parent, index)
        if step is not None:
            self.refresh(select=step.id)

    def add_comment(self):
        if "other/comment" not in self.library:
            return
        self.comp_tree.selection_set("other/comment")
        self.use_component()

    def undo(self):
        project = self.history.undo(self.project)
        if project is not None:
            self.project = project
            self.dirty = True
            self.refresh()

    def redo(self):
        project = self.history.redo(self.project)
        if project is not None:
            self.project = project
            self.dirty = True
            self.refresh()

    # ------------------------------------------------------- drag and drop
    def _drag_start(self, event):
        self._drag_item = self.tree.identify_row(event.y)

    def _drag_end(self, event):
        source = getattr(self, "_drag_item", None)
        self._drag_item = None
        target_id = self.tree.identify_row(event.y)
        if not source or not target_id or source == target_id:
            return
        step, target = self.project.find(source), self.project.find(target_id)
        if step is None or target is None or step.parent is None:
            return
        node = target
        while node is not None:           # can not drop a step inside itself
            if node is step:
                return
            node = node.parent

        def drop():
            step.parent.children.remove(step)
            if target.accepts_children:
                target.add(step)
            else:
                target.parent.add(step, target.index() + 1)

        self.change(drop)
        self.refresh(select=step.id)

    def _tree_double_click(self, event):
        if self.tree.identify_row(event.y):
            self.after(1, self.edit_step)
        return "break"

    def _tree_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.step_menu.tk_popup(event.x_root, event.y_root)

    def _code_click(self, event):
        line = int(self.code.index("@%d,%d" % (event.x, event.y)).split(".")[0])
        owner = step_at_line(self.owners, line)
        if owner and self.tree.exists(owner):
            self._reveal(owner)

    # ================================================================ files
    def confirm_discard(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel("PWCT-Python", "Save changes to the current project?", parent=self)
        if answer is None:
            return False
        if answer:
            return self.save()
        return True

    def new_file(self):
        if not self.confirm_discard():
            return
        self.project = Project()
        self.history = History()
        self.path = None
        self.dirty = False
        self.tree.delete(*self.tree.get_children())
        self.refresh(select=self.project.root.id)

    def open_dialog(self):
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(filetypes=FILE_TYPES, parent=self)
        if path:
            self.open_file(path)

    def open_file(self, path):
        try:
            project = Project.load(path)
        except (OSError, ValueError, KeyError, ProjectError) as exc:
            messagebox.showerror("Open", "Can not open %s\n%s" % (path, exc), parent=self)
            self.refresh()
            return
        missing = {i.component for i in project.interactions.values()} - set(self.library.components)
        self.project = project
        self.history = History()
        self.path = path
        self.dirty = False
        self.tree.delete(*self.tree.get_children())
        self.refresh(select=project.root.id)
        if missing:
            messagebox.showwarning("Open", "Components not found (their steps can not be edited):\n"
                                   + "\n".join(sorted(missing)), parent=self)

    def save(self):
        if not self.path:
            return self.save_as()
        try:
            self.project.save(self.path)
        except OSError as exc:
            messagebox.showerror("Save", str(exc), parent=self)
            return False
        self.dirty = False
        self.update_title()
        return True

    def save_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".pwct", filetypes=FILE_TYPES, parent=self)
        if not path:
            return False
        self.path = path
        return self.save()

    def export(self):
        initial = os.path.splitext(os.path.basename(self.path))[0] + ".py" if self.path else "program.py"
        path = filedialog.asksaveasfilename(defaultextension=".py", initialfile=initial,
                                            filetypes=[("Python", "*.py")], parent=self)
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(generate(self.project)[0])
            self.status.configure(text="Exported to " + path)

    def quit_app(self):
        if self.confirm_discard():
            self.runner.cleanup()
            self.destroy()

    # ================================================================== run
    def run_program(self):
        source = generate(self.project)[0]
        try:
            compile(source, "<program>", "exec")
        except SyntaxError as exc:
            self.show_error_line(exc.lineno)
            messagebox.showerror("Run", "Syntax error in the generated code:\n%s" % exc, parent=self)
            return
        self.tabs.select(2)
        self.output.delete("1.0", "end")
        self.output.insert("end", ">>> Running %s\n" % self.project.name, "info")
        workdir = os.path.dirname(self.path) if self.path else None
        self.runner.start(source, workdir)
        self.input_entry.focus_set()

    def stop_program(self):
        if self.runner.running:
            self.runner.stop()
            self.output.insert("end", "\n>>> Stopped\n", "info")

    def send_input(self, event=None):
        text = self.input_var.get()
        self.input_var.set("")
        if self.runner.running:
            self.output.insert("end", text + "\n", "input")
            self.output.see("end")
            self.runner.send(text)

    def _poll_runner(self):
        for kind, data in self.runner.poll():
            if kind == "out":
                self.output.insert("end", data)
            else:
                self.output.insert("end", "\n>>> Program finished (exit code %s)\n" % data, "info")
                if data and self.runner.last_error_line:
                    self.show_error_line(self.runner.last_error_line)
            self.output.see("end")
        self.after(80, self._poll_runner)

    def show_error_line(self, lineno):
        self.code.tag_remove("error", "1.0", "end")
        if not lineno:
            return
        self.code.tag_add("error", "%d.0" % lineno, "%d.0" % (lineno + 1))
        owner = step_at_line(self.owners, lineno)
        if owner and self.tree.exists(owner):
            self._reveal(owner)
            self.status.configure(text="Error at line %d - step: %s"
                                  % (lineno, self.project.find(owner).title))

    # ================================================================= help
    def show_help(self):
        messagebox.showinfo("How to use", HELP_TEXT, parent=self)

    def show_about(self):
        messagebox.showinfo("About", "PWCT-Python %s\n\nA visual programming environment that "
                            "generates Python code, inspired by PWCT (Programming Without "
                            "Coding Technology) by Mahmoud Fayed." % __version__, parent=self)


HELP_TEXT = """1. Select a step in the Goal Designer (left).
2. Choose a component in the Components tab and double click it
   (Ctrl+Space jumps to the search box).
3. Fill the interaction page and press OK: new steps are created.
4. Double click a step (or press Enter) to change its interaction.
   The steps you added inside it are kept.
5. F5 runs the program. Type input for the program in the Output tab.

Insert mode: Auto puts the new steps inside the active step when it can
hold steps (If, For, Function ...), otherwise after it.

Right click a step for more actions. Steps can be dragged with the mouse.
"""


def main(path=None):
    app = App(path)
    app.mainloop()
