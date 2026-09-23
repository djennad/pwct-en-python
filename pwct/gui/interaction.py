"""Interaction pages: the dialog the user fills instead of writing code."""

import tkinter as tk
from tkinter import messagebox, ttk

from ..engine.template import TemplateError


class InteractionPage(tk.Toplevel):
    """Build a form from the component's interaction fields.

    After the window closes, ``result`` holds the values (or ``None`` when
    cancelled)."""

    def __init__(self, master, component, values=None, editing=False, preview=None):
        super().__init__(master)
        self.component = component
        self.preview = preview
        self.result = None
        self.vars = {}
        self.memos = {}
        self.title(("Edit - " if editing else "") + component.name)
        self.transient(master)
        self.resizable(True, True)
        values = dict(component.default_values(), **(values or {}))

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        header = ttk.Label(outer, text=component.name, style="PageTitle.TLabel")
        header.grid(row=0, column=0, columnspan=2, sticky="w")
        if component.description:
            ttk.Label(outer, text=component.description, wraplength=440,
                      foreground="#555").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))

        row = 2
        first = None
        for field in component.fields:
            if field.kind == "title":
                ttk.Label(outer, text=field.label, style="Section.TLabel").grid(
                    row=row, column=0, columnspan=2, sticky="w", pady=(10, 2))
                ttk.Separator(outer).grid(row=row + 1, column=0, columnspan=2, sticky="ew")
                row += 2
                continue
            if field.kind == "help":
                ttk.Label(outer, text=field.label, wraplength=440, foreground="#555").grid(
                    row=row, column=0, columnspan=2, sticky="w", pady=2)
                row += 1
                continue
            value = values.get(field.name, "")
            label = field.label + (" *" if field.required else "")
            if field.kind == "check":
                var = tk.StringVar(value="1" if value == "1" else "0")
                widget = ttk.Checkbutton(outer, text=field.label, variable=var,
                                         onvalue="1", offvalue="0")
                widget.grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
                self.vars[field.name] = var
            else:
                ttk.Label(outer, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=4)
                if field.kind == "memo":
                    widget = tk.Text(outer, width=46, height=7, wrap="none", undo=True,
                                     font=("Courier New", 10))
                    widget.insert("1.0", value)
                    widget.bind("<Tab>", self._memo_tab)
                    self.memos[field.name] = widget
                elif field.kind == "list":
                    var = tk.StringVar(value=value)
                    widget = ttk.Combobox(outer, textvariable=var, values=field.options,
                                          state="readonly", width=44)
                    self.vars[field.name] = var
                else:
                    var = tk.StringVar(value=value)
                    widget = ttk.Entry(outer, textvariable=var, width=46)
                    self.vars[field.name] = var
                widget.grid(row=row, column=1, sticky="ew", pady=4)
            first = first or widget
            row += 1

        buttons = ttk.Frame(outer)
        buttons.grid(row=row, column=0, columnspan=2, sticky="e", pady=(14, 0))
        if preview:
            ttk.Button(buttons, text="Preview Code", command=self.show_preview).pack(side="left", padx=4)
        ttk.Button(buttons, text="OK", command=self.ok, default="active").pack(side="left", padx=4)
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left", padx=4)

        self.bind("<Return>", self._enter)
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        if first is not None:
            first.focus_set()
            if isinstance(first, ttk.Entry):
                first.select_range(0, "end")
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
        self.geometry("+%d+%d" % (max(x, 0), max(y, 0)))

    def _memo_tab(self, event):
        event.widget.insert("insert", "    ")
        return "break"

    def _enter(self, event):
        if isinstance(event.widget, tk.Text):
            return None
        self.ok()
        return "break"

    def values(self):
        result = {name: var.get() for name, var in self.vars.items()}
        for name, widget in self.memos.items():
            result[name] = widget.get("1.0", "end-1c")
        return result

    def show_preview(self):
        try:
            text = self.preview(self.component, self.values())
        except TemplateError as exc:
            text = "Template error: %s" % exc
        win = tk.Toplevel(self)
        win.title("Preview - " + self.component.name)
        box = tk.Text(win, width=70, height=18, font=("Courier New", 10))
        box.insert("1.0", text)
        box.configure(state="disabled")
        box.pack(fill="both", expand=True)

    def ok(self):
        values = self.values()
        errors = self.component.validate(values)
        if errors:
            messagebox.showwarning("Interaction", "\n".join(errors), parent=self)
            return
        self.result = values
        self.destroy()

    def run(self):
        self.grab_set()
        self.wait_window()
        return self.result
