"""The PWCT-Python environment.

Like the main window of the original PWCT (``DoubleS.scx``) it has the
standard toolbar at the top, the "Designers" bar on the left (Goal,
Transporter, Interaction) and a status bar.  The designers are:

* the Goal Designer (``rpwi.scx``): a white header with the goal and the
  "Goal Designer" title, a cyan band with the path of the active step, a
  purple bar to switch between the steps tree and the other views, and the
  buttons at the bottom (New Step, Delete Step, Edit Step, move up / down,
  Interact, Modify, Close);
* the Transporter Designer and the Interaction Designer (``designer.py``)
  to make new components.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from .. import __version__
from ..engine import History, Library, Project, ProjectError, TemplateError, generate
from ..engine.generator import step_at_line
from ..engine.project import Step
from . import theme
from .browser import ComponentBrowser
from .designer import ComponentStudio, InteractionDesigner, TransporterDesigner
from .interaction import InteractionPage
from .runner import Runner

FILE_TYPES = [("PWCT-Python project", "*.pwct"), ("All files", "*.*")]
VIEWS = [("tree", "Steps Tree"), ("details", "Step Details"), ("code", "Source Code"),
         ("output", "Output")]
DESIGNERS = [("goal", "Goal"), ("transporter", "Transporter"), ("interaction", "Interaction")]


class ToolTip:
    def __init__(self, widget, text):
        self.widget, self.text, self.tip = widget, text, None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, event=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.geometry("+%d+%d" % (x, y))
        tk.Label(self.tip, text=self.text, background="#ffffe1", relief="solid", borderwidth=1,
                 font=("Arial", 9), padx=4, pady=2).pack()

    def hide(self, event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


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
        self.source = ""
        self.insert_mode = tk.StringVar(value="auto")
        self.disabled_var = tk.IntVar(value=0)
        self.view = "tree"
        self.panel = "goal"

        self.title("PWCT-Python")
        self.geometry("1060x720")
        self.minsize(820, 560)
        self.configure(background=theme.GRAY)
        self.fonts = theme.Fonts(self)
        self.icons = theme.make_icons(self)
        self._styles()
        self._menu()
        self._toolbar()
        self._statusbar()
        self._designers_bar()
        self.content = tk.Frame(self, background=theme.GRAY)
        self.content.pack(side="left", fill="both", expand=True)
        self.goal_panel = tk.Frame(self.content, background=theme.WHITE)
        self._header()
        self._bottom()
        self._views()
        self.studio = ComponentStudio(self)
        self.transporter_designer = TransporterDesigner(self.content, self, self.studio)
        self.interaction_designer = InteractionDesigner(self.content, self, self.studio)
        self.panels = {"goal": self.goal_panel, "transporter": self.transporter_designer,
                       "interaction": self.interaction_designer}
        self._keys()
        self.show_view("tree")
        self.show_panel("goal")
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self._poll_job = self.after(100, self._poll_runner)

        if path:
            self.open_file(path)
        else:
            self.refresh()

    # ================================================================ layout
    def _styles(self):
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Steps.Treeview", background=theme.WHITE, fieldbackground=theme.WHITE,
                        font=self.fonts.tree, rowheight=24, borderwidth=0)
        style.map("Steps.Treeview", background=[("selected", theme.SELECT)],
                  foreground=[("selected", theme.WHITE)])
        style.configure("Domain.Treeview", background=theme.WHITE, fieldbackground=theme.WHITE,
                        font=self.fonts.normal, rowheight=22)
        style.map("Domain.Treeview", background=[("selected", theme.SELECT)],
                  foreground=[("selected", theme.WHITE)])

    def _menu(self):
        bar = tk.Menu(self)
        m = tk.Menu(bar, tearoff=False)
        m.add_command(label="New Project", accelerator="Ctrl+N", command=self.new_file)
        m.add_command(label="Open...", accelerator="Ctrl+O", command=self.open_dialog)
        m.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
        m.add_command(label="Save As...", command=self.save_as)
        m.add_separator()
        m.add_command(label="Export Python Code...", accelerator="Ctrl+E", command=self.export)
        m.add_command(label="Goal Name...", command=self.rename_project)
        m.add_separator()
        m.add_command(label="Exit", command=self.quit_app)
        bar.add_cascade(label="File", menu=m)

        m = tk.Menu(bar, tearoff=False)
        m.add_command(label="Undo", accelerator="Ctrl+Z", command=self.undo)
        m.add_command(label="Redo", accelerator="Ctrl+Y", command=self.redo)
        m.add_separator()
        m.add_command(label="Interact (Components Browser)", accelerator="Ctrl+Space",
                      command=self.interact)
        m.add_command(label="Modify Step (Interaction)", accelerator="Enter", command=self.edit_step)
        m.add_command(label="New Step...", accelerator="Insert", command=self.new_step)
        m.add_command(label="Edit Step Title...", accelerator="F2", command=self.rename_step)
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
        m.add_command(label="Ignore (Disable) Step", accelerator="Ctrl+D", command=self.toggle_disabled)
        m.add_command(label="Add Comment", accelerator="Ctrl+M", command=self.add_comment)
        bar.add_cascade(label="Edit", menu=m)

        m = tk.Menu(bar, tearoff=False)
        m.add_command(label="RPWI - Goal Designer", command=self.show_goal_designer)
        m.add_command(label="Components Browser (Interact)", accelerator="Ctrl+Space", command=self.interact)
        m.add_separator()
        m.add_command(label="Install Component", command=lambda: self.studio.install())
        m.add_command(label="Uninstall Component", command=lambda: self.studio.uninstall())
        m.add_command(label="Components Folder...", command=self.show_components_folder)
        bar.add_cascade(label="RPWI", menu=m)

        m = tk.Menu(bar, tearoff=False)
        m.add_command(label="Transporter Designer", command=self.show_transporter_designer)
        m.add_command(label="Interaction Designer", command=self.show_interaction_designer)
        m.add_separator()
        m.add_command(label="New Component", command=lambda: (self.studio.new(), self.show_transporter_designer()))
        m.add_command(label="Open Component...", command=lambda: (self.studio.open_library(),
                                                                  self.show_transporter_designer()))
        m.add_command(label="Open Component File...", command=lambda: (self.studio.open_file(),
                                                                       self.show_transporter_designer()))
        m.add_command(label="Save Component", command=lambda: self.studio.save())
        m.add_command(label="Save Component As...", command=lambda: self.studio.save_as())
        m.add_separator()
        m.add_command(label="Import PWCT 1.x Component (TRF)...",
                      command=lambda: (self.studio.import_trf(), self.show_transporter_designer()))
        m.add_command(label="Import Interaction Script (ISF)...",
                      command=lambda: (self.studio.import_isf(), self.show_interaction_designer()))
        m.add_separator()
        m.add_command(label="Test Component", command=self.show_test)
        bar.add_cascade(label="Transporter", menu=m)

        m = tk.Menu(bar, tearoff=False)
        for key, label in VIEWS:
            m.add_command(label=label, command=lambda k=key: (self.show_goal_designer(), self.show_view(k)))
        m.add_separator()
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
        for label, cmd in [("Interact", self.interact), ("Modify", self.edit_step),
                           ("New Step...", self.new_step), ("Edit Step Title...", self.rename_step),
                           ("Delete Step", self.delete_step), (None, None),
                           ("Cut", self.cut), ("Copy", self.copy), ("Paste", self.paste), (None, None),
                           ("Move Up", lambda: self.move(-1)), ("Move Down", lambda: self.move(1)),
                           ("Ignore (Disable) Step", self.toggle_disabled),
                           ("Add Comment", self.add_comment)]:
            if label is None:
                self.step_menu.add_separator()
            else:
                self.step_menu.add_command(label=label, command=cmd)

    def _toolbar(self):
        """The "Standard" toolbar of PWCT (``mytool.vcx``)."""
        bar = tk.Frame(self, background=theme.FACE, relief="raised", borderwidth=1)
        bar.pack(side="top", fill="x")
        items = [("new", "New Goal (Ctrl+N)", self.new_file), ("open", "Open (Ctrl+O)", self.open_dialog),
                 ("save", "Save (Ctrl+S)", self.save), None,
                 ("cut", "Cut", self.cut), ("copy", "Copy", self.copy), ("paste", "Paste", self.paste), None,
                 ("interact", "Interact - Components Browser (Ctrl+Space)", self.interact),
                 ("run", "Run (F5)", self.run_program), ("stop", "Stop", self.stop_program), None,
                 ("help", "Help", self.show_help), ("close", "Quit", self.quit_app)]
        for item in items:
            if item is None:
                tk.Frame(bar, width=2, background=theme.GRAY).pack(side="left", fill="y", padx=6, pady=3)
                continue
            icon, tip, cmd = item
            b = tk.Button(bar, image=self.icons[icon], command=cmd, width=26, height=24,
                          relief="flat", background=theme.FACE, activebackground=theme.WHITE,
                          overrelief="raised")
            b.pack(side="left", padx=1, pady=2)
            ToolTip(b, tip)
        logo = tk.Frame(bar, background=theme.PURPLE, padx=8)
        logo.pack(side="right", padx=4, pady=2, fill="y")
        tk.Label(logo, text="PWCT", font=(self.fonts.title[0], 13), foreground=theme.WHITE,
                 background=theme.PURPLE).pack(side="left")
        tk.Label(logo, text=" Python", font=(self.fonts.normal[0], 9, "bold"), foreground=theme.CYAN,
                 background=theme.PURPLE).pack(side="left")

    def _statusbar(self):
        self.status = tk.Label(self, text="", anchor="w", font=self.fonts.normal,
                               background=theme.FACE, relief="sunken", padx=6)
        self.status.pack(side="bottom", fill="x")

    def _designers_bar(self):
        """The vertical "Designers" bar of PWCT: rotated captions that switch
        between the Goal Designer, the Transporter and the Interaction
        designers."""
        font = (self.fonts.normal[0], 13, "bold")
        self.designers = tk.Canvas(self, width=34, background=theme.FACE, highlightthickness=0,
                                   relief="raised", borderwidth=1)
        self.designers.pack(side="left", fill="y")
        self.designer_items = {}
        y = 6
        for key, text in DESIGNERS:
            length = len(text) * 10 + 30
            rect = self.designers.create_rectangle(3, y, 32, y + length, outline=theme.GRAY,
                                                   fill=theme.FACE, tags=(key,))
            label = self.designers.create_text(17, y + length / 2, text=text, angle=90, font=font,
                                               fill=theme.BLACK, tags=(key,))
            self.designer_items[key] = (rect, label)
            self.designers.tag_bind(key, "<Button-1>", lambda e, k=key: self.show_panel(k))
            self.designers.tag_bind(key, "<Enter>", lambda e, k=key: self._designer_hover(k, True))
            self.designers.tag_bind(key, "<Leave>", lambda e, k=key: self._designer_hover(k, False))
            y += length + 4

    def _designer_hover(self, key, inside):
        rect, label = self.designer_items[key]
        active = inside or key == self.panel
        self.designers.itemconfigure(rect, fill=theme.PURPLE if active else theme.FACE)
        self.designers.itemconfigure(label, fill=theme.WHITE if active else theme.BLACK)
        self.designers.configure(cursor="hand2" if inside else "")

    def show_panel(self, key):
        """Show the Goal Designer, the Transporter Designer or the
        Interaction Designer."""
        self.panel = key
        for name, panel in self.panels.items():
            if name != key:
                panel.pack_forget()
        self.panels[key].pack(fill="both", expand=True)
        for name in self.designer_items:
            self._designer_hover(name, False)
        if key == "goal":
            self.tree.focus_set()
        self.update_title()

    def show_goal_designer(self):
        self.show_panel("goal")

    def show_transporter_designer(self):
        self.show_panel("transporter")

    def show_interaction_designer(self):
        self.show_panel("interaction")

    def show_test(self):
        self.show_panel("transporter")
        tabs = self.transporter_designer.tabs
        tabs.select(len(tabs.tabs()) - 1)

    def library_changed(self):
        """Components were installed or removed."""
        self.update_title()
        self.on_select()

    def _header(self):
        f = self.fonts
        head = tk.Frame(self.goal_panel, background=theme.WHITE, height=54)
        head.pack(side="top", fill="x")
        tk.Label(head, text="Goal :", font=f.header, background=theme.WHITE).pack(
            side="left", padx=(6, 4), pady=8)
        self.goal_var = tk.StringVar()
        self.goal_box = ttk.Combobox(head, textvariable=self.goal_var, state="readonly",
                                     font=f.header, width=24)
        self.goal_box.pack(side="left", pady=8)
        self.goal_box.bind("<<ComboboxSelected>>", lambda e: self._reveal(self.project.root.id))
        tk.Label(head, text="Goal Designer", font=f.title, foreground=theme.OLIVE,
                 background=theme.WHITE).pack(side="right", padx=16)
        tk.Frame(self.goal_panel, height=2, background=theme.GRAY).pack(side="top", fill="x")

        band = tk.Frame(self.goal_panel, background=theme.CYAN)
        band.pack(side="top", fill="x")
        self.path_var = tk.StringVar()
        self.path_box = ttk.Combobox(band, textvariable=self.path_var, state="readonly",
                                     font=f.normal)
        self.path_box.pack(fill="x", padx=5, pady=5)
        self.path_box.bind("<<ComboboxSelected>>", self._path_selected)

        bar = tk.Frame(self.goal_panel, background=theme.PURPLE)
        bar.pack(side="top", fill="x")
        self.view_buttons = {}
        for key, label in VIEWS:
            b = tk.Button(bar, text=label, font=f.button, width=11, relief="raised", borderwidth=2,
                          background=theme.FACE, activebackground=theme.WHITE,
                          command=lambda k=key: self.show_view(k))
            b.pack(side="left", padx=(5 if key == "tree" else 0, 0), pady=5)
            self.view_buttons[key] = b
        tk.Label(bar, text="The Tool of Programming Without Coding", font=f.header,
                 foreground=theme.WHITE, background=theme.PURPLE).pack(side="right", padx=10)

    def make_button(self, parent, text, icon, command, big=False, width=None, tip=None):
        """A button like the ones of PWCT: an icon and a caption."""
        b = tk.Button(parent, text=text, image=self.icons[icon or "blank"],
                      compound="top" if big else "left", command=command, font=self.fonts.button,
                      background=theme.FACE, activebackground=theme.WHITE, padx=6,
                      width=width or (0 if text else 34), anchor="center")
        if tip:
            ToolTip(b, tip)
        return b

    def tooltip(self, widget, text):
        ToolTip(widget, text)

    def _bottom(self):
        panel = tk.Frame(self.goal_panel, background=theme.WHITE, padx=4, pady=6)
        panel.pack(side="bottom", fill="x")
        tk.Frame(self.goal_panel, height=2, background=theme.GRAY).pack(side="bottom", fill="x")

        left = tk.Frame(panel, background=theme.WHITE)
        left.pack(side="left")
        B = self.make_button
        B(left, " New Step", "new", self.new_step, width=96).grid(row=0, column=0, padx=2, pady=2, sticky="w")
        B(left, " Delete Step", "delete", self.delete_step, width=106).grid(
            row=0, column=1, columnspan=2, padx=2, pady=2, sticky="w")
        B(left, " Interact", "interact", self.interact, width=96).grid(row=0, column=3, padx=6, pady=2, sticky="w")
        B(left, " Edit Step", "edit", self.rename_step, width=96).grid(row=1, column=0, padx=2, pady=2, sticky="w")
        up = B(left, "", "up", lambda: self.move(-1))
        up.grid(row=1, column=1, padx=2, pady=2, sticky="w")
        down = B(left, "", "down", lambda: self.move(1))
        down.grid(row=1, column=2, padx=2, pady=2, sticky="w")
        tk.Checkbutton(left, text="Ignore (Disable) Step", variable=self.disabled_var,
                       command=self._disabled_clicked, font=self.fonts.normal,
                       background=theme.WHITE, activebackground=theme.WHITE,
                       highlightthickness=0).grid(row=1, column=3, padx=6, sticky="w")

        right = tk.Frame(panel, background=theme.WHITE)
        right.pack(side="right")
        for text, icon, cmd in [("Close", "close", self.quit_app), ("Stop", "stop", self.stop_program),
                                ("Run", "run", self.run_program), ("Modify", "modify", self.edit_step)]:
            B(right, text, icon, cmd, big=True, width=84).pack(side="right", padx=4, ipady=2)

    def _views(self):
        self.main = tk.Frame(self.goal_panel, background=theme.WHITE)
        self.main.pack(side="top", fill="both", expand=True)
        self.frames = {}

        # steps tree
        frame = tk.Frame(self.main, background=theme.WHITE)
        self.tree = ttk.Treeview(frame, show="tree", selectmode="browse", style="Steps.Treeview")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True, padx=(2, 0), pady=2)
        for tag, color in theme.STEP_COLORS.items():
            self.tree.tag_configure(tag, foreground=color)
        self.tree.tag_configure("root", font=self.fonts.tree_root)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())
        self.tree.bind("<Double-1>", self._tree_double_click)
        self.tree.bind("<Button-3>", self._tree_menu)
        self.tree.bind("<ButtonPress-1>", self._drag_start, add="+")
        self.tree.bind("<ButtonRelease-1>", self._drag_end, add="+")
        self.frames["tree"] = frame

        # step details
        frame = tk.Frame(self.main, background=theme.WHITE, padx=10, pady=8)
        self.step_info = tk.Text(frame, font=self.fonts.normal, wrap="word", relief="solid",
                                 borderwidth=1, padx=8, pady=6)
        self.step_info.pack(fill="both", expand=True)
        self.step_info.tag_configure("head", font=(self.fonts.header[0], 14, "bold"))
        self.step_info.tag_configure("code", font=self.fonts.code, foreground=theme.NAVY)
        self.step_info.configure(state="disabled")
        self.frames["details"] = frame

        # source code
        frame = tk.Frame(self.main, background=theme.WHITE, padx=10, pady=8)
        self.code = tk.Text(frame, font=self.fonts.code, wrap="none", relief="solid", borderwidth=1)
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.code.yview)
        xs = ttk.Scrollbar(frame, orient="horizontal", command=self.code.xview)
        self.code.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.code.pack(fill="both", expand=True)
        self.code.tag_configure("active", background="#fff3b0")
        self.code.tag_configure("comment", foreground="#008000")
        self.code.tag_configure("error", background="#ffc9c9")
        self.code.bind("<Button-1>", self._code_click)
        self.code.configure(state="disabled")
        self.frames["code"] = frame

        # program output
        frame = tk.Frame(self.main, background=theme.WHITE, padx=10, pady=8)
        bottom = tk.Frame(frame, background=theme.WHITE)
        bottom.pack(side="bottom", fill="x", pady=(6, 0))
        tk.Label(bottom, text="Input :", font=self.fonts.normal, background=theme.WHITE).pack(side="left")
        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(bottom, textvariable=self.input_var, font=self.fonts.code,
                                    relief="solid", borderwidth=1)
        self.input_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=2)
        self.input_entry.bind("<Return>", self.send_input)
        tk.Button(bottom, text="Send", width=8, font=self.fonts.button, background=theme.FACE,
                  command=self.send_input).pack(side="left")
        tk.Button(bottom, text="Clear", width=8, font=self.fonts.button, background=theme.FACE,
                  command=lambda: self.output.delete("1.0", "end")).pack(side="left", padx=(4, 0))
        self.output = tk.Text(frame, font=self.fonts.code, wrap="word", background=theme.BLACK,
                              foreground="#c0c0c0", insertbackground=theme.WHITE)
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.output.yview)
        self.output.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        self.output.pack(fill="both", expand=True)
        self.output.tag_configure("info", foreground="#00ff80")
        self.output.tag_configure("input", foreground="#ffff00")
        self.frames["output"] = frame

    def show_view(self, key):
        self.view = key
        for name, frame in self.frames.items():
            frame.pack_forget()
        self.frames[key].pack(fill="both", expand=True)
        for name, button in self.view_buttons.items():
            active = name == key
            button.configure(relief="sunken" if active else "raised",
                             background=theme.WHITE if active else theme.FACE)
        if key == "tree":
            self.tree.focus_set()
        elif key == "output":
            self.input_entry.focus_set()

    def _keys(self):
        keys = {
            "<Control-n>": self.new_file, "<Control-o>": self.open_dialog, "<Control-s>": self.save,
            "<Control-e>": self.export, "<Control-z>": self.undo, "<Control-y>": self.redo,
            "<F5>": self.run_program, "<Shift-F5>": self.stop_program,
            "<Control-space>": self.interact, "<Control-m>": self.add_comment,
        }
        for key, cmd in keys.items():
            self.bind_all(key, lambda e, c=cmd: self._global_key(e, c))
        tree_keys = {
            "<Delete>": self.delete_step, "<Return>": self.edit_step, "<F2>": self.rename_step,
            "<Insert>": self.new_step,
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
        self.goal_box.configure(values=[self.project.name])
        self.goal_var.set(self.project.name)
        self.update_code()
        self.update_title()
        self.on_select()

    def _all_items(self, parent=""):
        for item in self.tree.get_children(parent):
            yield item
            yield from self._all_items(item)

    def _insert_step(self, parent, step, opened, open_all):
        tag = self._tag(step)
        icon = {"root": "goal", "generated": "step", "user": "user", "comment": "comment",
                "disabled": "disabled"}[tag]
        text = " " + (step.title or "(empty)") + "  "
        self.tree.insert(parent, "end", iid=step.id, text=text, tags=(tag,), image=self.icons[icon],
                         open=open_all or step.id in opened or step.parent is None)
        for child in step.children:
            self._insert_step(step.id, child, opened, open_all)

    def _tag(self, step):
        if step.parent is None:
            return "root"
        if self._inside_disabled(step):
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

    def _path_selected(self, event=None):
        index = self.path_box.current()
        step = self.selected()
        chain = []
        while step is not None:
            chain.insert(0, step)
            step = step.parent
        if 0 <= index < len(chain):
            self._reveal(chain[index].id)

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
        if getattr(self, "panel", "goal") != "goal" and hasattr(self, "studio"):
            comp = self.studio.component
            self.title("%s%s - PWCT-Python - %s Designer" % ("*" if self.studio.dirty else "",
                                                               comp.name, self.panel.title()))
            self.status.configure(text="Component : %s     File : %s.pwc     Domain : %s     "
                                  "Components : %d" % (comp.name, comp.key, comp.category,
                                                       len(self.library)))
            return
        name = os.path.basename(self.path) if self.path else "Untitled"
        self.title("%s%s - PWCT-Python - Goal Designer" % ("*" if self.dirty else "", name))
        steps = sum(1 for _ in self.project.root.walk()) - 1
        self.status.configure(text="Goal : %s     Steps : %d     Components : %d"
                              % (self.project.name, steps, len(self.library)))

    def selected(self):
        sel = self.tree.selection()
        return self.project.find(sel[0]) if sel else None

    def on_select(self):
        step = self.selected()
        self.highlight_code()
        chain = []
        node = step
        while node is not None:
            chain.insert(0, node)
            node = node.parent
        titles = [("    " * i) + s.title for i, s in enumerate(chain)]
        self.path_box.configure(values=titles)
        self.path_var.set("  >  ".join(s.title for s in chain))
        self.disabled_var.set(1 if step is not None and step.disabled else 0)

        self.step_info.configure(state="normal")
        self.step_info.delete("1.0", "end")
        if step is not None:
            self.step_info.insert("end", step.title + "\n", "head")
            if step.interaction and step.interaction in self.project.interactions:
                inter = self.project.interactions[step.interaction]
                comp = self.library.components.get(inter.component)
                self.step_info.insert("end", "Component : %s\n" % (comp.name if comp else inter.component))
                for key, value in inter.values.items():
                    self.step_info.insert("end", "   %s = %s\n" % (key, value))
            elif step.parent is not None:
                self.step_info.insert("end", "Step without interaction (written by the user)\n")
            if step.info:
                self.step_info.insert("end", "\n" + "\n".join(step.info) + "\n")
            if step.code:
                self.step_info.insert("end", "\nStep Code :\n")
                self.step_info.insert("end", "\n".join(step.code) + "\n", "code")
            if step.disabled:
                self.step_info.insert("end", "\nThis step is ignored (written as a comment).\n")
        self.step_info.configure(state="disabled")

    def _disabled_clicked(self):
        step = self.selected()
        if step is None or step.parent is None:
            self.disabled_var.set(0)
            return
        if bool(self.disabled_var.get()) != step.disabled:
            self.toggle_disabled()

    def interact(self):
        """Open the components browser, then the interaction page."""
        self.show_goal_designer()
        key = ComponentBrowser(self, self.library, self.insert_mode, self.fonts, self.icons).run()
        if key:
            self.add_component(key)

    def show_components_folder(self):
        from ..engine.components import user_dir
        messagebox.showinfo("Components Folder", "Installed components are saved in:\n%s\n\n"
                            "Other folders can be added with the PWCT_COMPONENTS environment "
                            "variable." % user_dir(), parent=self)

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

    def add_component(self, key):
        """Show the interaction page of a component and add its steps."""
        self.add_component_object(self.library[key])

    def add_component_object(self, comp):
        values = InteractionPage(self, comp, preview=self.preview, fonts=self.fonts).run()
        if values is None:
            return
        mode = self.insert_mode.get()
        if mode == "auto" and comp.position != "auto":
            mode = comp.position
        parent, index = self.project.insert_position(self.selected(), mode)
        step = self.change(self.project.apply, comp, values, parent, index)
        if step is not None:
            self.refresh(select=step.id)
            self.show_view("tree")

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
        values = InteractionPage(self, comp, inter.values, editing=True, preview=self.preview,
                                 fonts=self.fonts).run()
        if values is None:
            return
        first = self.change(self.project.edit, step.interaction, comp, values)
        target = step.id if self.project.find(step.id) else (first.id if first else None)
        self.refresh(select=target)

    def new_step(self):
        """A step written by the user: a title without code that can hold
        other steps (the "New Step" button of PWCT)."""
        title = simpledialog.askstring("New Step", "Step title:", parent=self)
        if not title:
            return
        parent, index = self.project.insert_position(self.selected(), self.insert_mode.get())

        def add():
            return parent.add(Step(self.project.new_id(), title), index)

        step = self.change(add)
        if step is not None:
            self.refresh(select=step.id)

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
        self.add_component("other/comment")

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
        if self.confirm_discard() and self.studio.confirm_discard():
            self.runner.cleanup()
            self.after_cancel(self._poll_job)
            self.interaction_designer.destroy()
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
        self.show_view("output")
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
        self._poll_job = self.after(80, self._poll_runner)

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


HELP_TEXT = """1. Select a step in the steps tree ("Start Here" at the beginning).
2. Press Interact (Ctrl+Space) and choose a component in the
   components browser: a domain on the left, the component on the right.
3. Fill the interaction page and press Ok: new steps are created.
4. Select a step and press Modify (or double click it) to change its
   interaction. The steps you added inside it are kept.
5. Run (F5) runs the program; type the program input in the Output view.

Insert mode: Auto puts the new steps inside the active step when it can
hold steps (If, For, Function ...), otherwise after it.

Right click a step for more actions. Steps can be dragged with the mouse.
"""


class Splash(tk.Toplevel):
    """The welcome window of PWCT (``welcome.scx``)."""

    LINES = [("Welcome", 60, 30), ("To the Real World", 100, 60), ("You are in", 130, 90),
             ("The world of", 110, 120), ("Programming Without", 130, 150), ("Coding", 150, 180)]

    def __init__(self, master):
        super().__init__(master, background=theme.BLACK)
        self.overrideredirect(True)
        fonts = theme.Fonts(self)
        width, height = 420, 330
        canvas = tk.Canvas(self, width=width, height=height, background=theme.BLACK, highlightthickness=0)
        canvas.pack()
        for x in range(0, width, 6):          # the sun of the PWCT icon
            canvas.create_line(width - 70, 70, x, height, fill="#1a1a1a")
        canvas.create_oval(width - 110, 30, width - 30, 110, fill="#f0c000", outline="#fff27a", width=3)
        for text, x, y in self.LINES:
            canvas.create_text(x, y + 20, text=text, anchor="w", fill=theme.WHITE,
                               font=(fonts.normal[0], 12, "bold"))
        canvas.create_text(width - 20, height - 60, text="PWCT - Python", anchor="e",
                           fill=theme.WHITE, font=(fonts.title[0], 20))
        canvas.create_text(width - 20, height - 30, text="Version %s" % __version__, anchor="e",
                           fill=theme.CYAN, font=(fonts.normal[0], 10))
        self.bar = canvas.create_rectangle(0, height - 6, 0, height, fill=theme.GREEN, outline="")
        self.canvas, self.width, self.height = canvas, width, height
        self.update_idletasks()
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 3
        self.geometry("+%d+%d" % (x, y))
        self.bind("<Button-1>", lambda e: self.destroy())
        self.step = 0
        self.after(30, self.grow)

    def grow(self):
        if not self.winfo_exists():
            return
        self.step += 1
        self.canvas.coords(self.bar, 0, self.height - 6, self.width * self.step / 50, self.height)
        if self.step < 50:
            self.after(30, self.grow)
        else:
            self.destroy()


def main(path=None, splash=True):
    app = App(path)
    if splash:
        app.withdraw()
        welcome = Splash(app)
        app.wait_window(welcome)
        app.deiconify()
    app.mainloop()
