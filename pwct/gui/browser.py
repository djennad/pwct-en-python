"""The components browser ("Select Component" window of PWCT): the domains
tree on the left, the components of the selected domain on the right and a
search box under them."""

import tkinter as tk
from tkinter import ttk

from . import theme

INSERT_MODES = [("Auto", "auto"), ("Inside", "inside"), ("After", "after"), ("Before", "before")]


class ComponentBrowser(tk.Toplevel):
    """Modal window; ``result`` is the chosen component key or ``None``."""

    def __init__(self, master, library, insert_mode, fonts, icons):
        super().__init__(master, background=theme.WHITE)
        self.library = library
        self.result = None
        self.title("Select Component")
        self.transient(master)
        self.geometry("760x470")
        self.minsize(600, 380)

        tk.Label(self, text="Select Component", font=fonts.big, background=theme.WHITE,
                 foreground=theme.BLACK).pack(fill="x", pady=(6, 4))
        tk.Frame(self, height=2, background=theme.GRAY).pack(fill="x")

        body = tk.Frame(self, background=theme.WHITE, padx=10, pady=6)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=4)
        body.rowconfigure(1, weight=1)

        tk.Label(body, text="Select Domain :", font=fonts.normal, background=theme.WHITE).grid(
            row=0, column=0, sticky="w")
        tk.Label(body, text="Components in Domain", font=fonts.normal, background=theme.WHITE).grid(
            row=0, column=1, sticky="w", padx=(10, 0))

        left = tk.Frame(body, background=theme.GRAY, padx=1, pady=1)
        left.grid(row=1, column=0, sticky="nsew")
        self.domains = ttk.Treeview(left, show="tree", selectmode="browse", style="Domain.Treeview")
        self.domains.pack(fill="both", expand=True)
        self.domains.bind("<<TreeviewSelect>>", lambda e: self.fill_components())

        right = tk.Frame(body, background=theme.GRAY, padx=1, pady=1)
        right.grid(row=1, column=1, sticky="nsew", padx=(10, 0))
        self.components = ttk.Treeview(right, show="tree", selectmode="browse", style="Domain.Treeview")
        scroll = ttk.Scrollbar(right, orient="vertical", command=self.components.yview)
        self.components.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.components.pack(fill="both", expand=True)
        self.components.bind("<Double-1>", lambda e: self.ok())
        self.components.bind("<Return>", lambda e: self.ok())
        self.components.bind("<<TreeviewSelect>>", lambda e: self.describe())

        self.description = tk.Label(body, text="", font=fonts.normal, background=theme.WHITE,
                                    foreground="#555555", anchor="w", justify="left", wraplength=700)
        self.description.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))

        search = tk.Frame(body, background=theme.WHITE)
        search.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        tk.Label(search, text="Search", font=fonts.normal, background=theme.WHITE).pack(side="left")
        self.search_var = tk.StringVar()
        self.search = ttk.Entry(search, textvariable=self.search_var)
        self.search.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.search_var.trace_add("write", lambda *a: self.fill_domains())
        self.search.bind("<Return>", lambda e: self.ok())
        self.search.bind("<Down>", lambda e: self._first_component())

        bottom = tk.Frame(self, background=theme.WHITE, padx=10, pady=8)
        bottom.pack(fill="x")
        tk.Label(bottom, text="Insert :", font=fonts.normal, background=theme.WHITE).pack(side="left")
        for label, value in INSERT_MODES:
            tk.Radiobutton(bottom, text=label, value=value, variable=insert_mode, font=fonts.normal,
                           background=theme.WHITE, activebackground=theme.WHITE,
                           highlightthickness=0).pack(side="left")
        tk.Button(bottom, text="Close", width=12, command=self.destroy, font=fonts.button).pack(
            side="right")
        tk.Button(bottom, text="Ok", width=12, command=self.ok, font=fonts.button).pack(
            side="right", padx=8)

        self.bind("<Escape>", lambda e: self.destroy())
        self.fill_domains()
        self.search.focus_set()
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
        self.geometry("+%d+%d" % (max(x, 0), max(y, 0)))

    def matching(self):
        text = self.search_var.get().strip()
        return self.library.search(text) if text else list(self.library)

    def fill_domains(self):
        comps = self.matching()
        cats = sorted({c.category for c in comps})
        current = self.domains.selection()
        self.domains.delete(*self.domains.get_children())
        self.domains.insert("", "end", iid="*", text="  All Components (%d)" % len(comps), open=True)
        for cat in cats:
            count = sum(1 for c in comps if c.category == cat)
            self.domains.insert("*", "end", iid=cat, text="  %s (%d)" % (cat, count))
        target = current[0] if current and self.domains.exists(current[0]) else "*"
        if self.search_var.get().strip():
            target = "*"
        self.domains.selection_set(target)
        self.fill_components()

    def fill_components(self):
        sel = self.domains.selection()
        domain = sel[0] if sel else "*"
        self.components.delete(*self.components.get_children())
        for comp in sorted(self.matching(), key=lambda c: (c.category, c.name)):
            if domain == "*" or comp.category == domain:
                self.components.insert("", "end", iid=comp.key, text="  " + comp.name)
        kids = self.components.get_children()
        if kids:
            self.components.selection_set(kids[0])

    def select(self, key):
        comp = self.library[key]
        self.domains.selection_set(comp.category)
        self.fill_components()
        self.components.selection_set(key)
        self.components.see(key)

    def describe(self):
        sel = self.components.selection()
        comp = self.library.components.get(sel[0]) if sel else None
        self.description.configure(text=("%s  -  %s" % (comp.name, comp.description)) if comp else "")

    def _first_component(self):
        kids = self.components.get_children()
        if kids:
            self.components.focus_set()
            self.components.focus(kids[0])
            self.components.selection_set(kids[0])
        return "break"

    def ok(self):
        sel = self.components.selection()
        if sel:
            self.result = sel[0]
            self.destroy()

    def run(self):
        self.grab_set()
        self.wait_window()
        return self.result
