"""Interaction pages: the dialog the user fills instead of writing code.

Styled like the "Interaction Using Transporter" window of PWCT: a purple
title bar, a green bar with the component, a white page with the fields
and the Ok / Cancel / Again buttons."""

import tkinter as tk
from tkinter import messagebox, ttk

from ..engine.template import TemplateError
from . import theme


class InteractionPage(tk.Toplevel):
    """Build a form from the component's interaction fields.

    After the window closes, ``result`` holds the values (or ``None`` when
    cancelled)."""

    def __init__(self, master, component, values=None, editing=False, preview=None, fonts=None):
        super().__init__(master, background=theme.WHITE)
        fonts = fonts or theme.Fonts(self)
        self.fonts = fonts
        self.component = component
        self.preview = preview
        self.result = None
        self.vars = {}
        self.memos = {}
        self.title("Interaction Using Transporter")
        self.transient(master)
        self.resizable(True, True)
        values = dict(component.default_values(), **(values or {}))

        head = tk.Frame(self, background=theme.PURPLE)
        head.pack(fill="x")
        tk.Label(head, text=component.name, font=fonts.title_small, background=theme.PURPLE,
                 foreground=theme.WHITE).pack(padx=16, pady=(6, 4))

        bar = tk.Frame(self, background=theme.GREEN)
        bar.pack(fill="x")
        tk.Label(bar, text="%s : %s%s" % (component.category, component.name,
                                           "   (Modify)" if editing else ""),
                 font=fonts.normal, background=theme.GREEN, foreground=theme.BLACK).pack(
            side="left", padx=8, pady=3)

        page = tk.Frame(self, background=theme.WHITE, padx=14, pady=10)
        page.pack(fill="both", expand=True)
        page.columnconfigure(1, weight=1)

        row = 0
        if component.description:
            tk.Label(page, text=component.description, wraplength=460, justify="left",
                     font=fonts.normal, background=theme.WHITE, foreground="#555555").grid(
                row=row, column=0, columnspan=2, sticky="w", pady=(0, 6))
            row += 1

        first = None
        for field in component.fields:
            if field.kind == "title":
                tk.Label(page, text=field.label, font=(fonts.header[0], 14), background=theme.WHITE,
                         foreground=theme.BLACK, anchor="w").grid(
                    row=row, column=0, columnspan=2, sticky="ew", pady=(8, 2))
                row += 1
                continue
            if field.kind == "help":
                tk.Label(page, text=field.label, wraplength=460, justify="left", font=fonts.normal,
                         background=theme.WHITE, foreground="#555555").grid(
                    row=row, column=0, columnspan=2, sticky="w", pady=2)
                row += 1
                continue
            value = values.get(field.name, "")
            label = field.label + (" *" if field.required else "")
            if field.kind == "check":
                var = tk.StringVar(value="1" if value == "1" else "0")
                widget = tk.Checkbutton(page, text=field.label, variable=var, onvalue="1",
                                        offvalue="0", font=fonts.normal, background=theme.WHITE,
                                        activebackground=theme.WHITE, highlightthickness=0)
                widget.grid(row=row, column=0, columnspan=2, sticky="w", pady=3)
                self.vars[field.name] = var
            else:
                tk.Label(page, text=label, font=fonts.normal, background=theme.FACE,
                         anchor="w", padx=6, relief="flat").grid(
                    row=row, column=0, sticky="nsew", padx=(0, 8), pady=3)
                if field.kind == "memo":
                    widget = tk.Text(page, width=46, height=7, wrap="none", undo=True,
                                     font=fonts.code, relief="solid", borderwidth=1)
                    widget.insert("1.0", value)
                    widget.bind("<Tab>", self._memo_tab)
                    self.memos[field.name] = widget
                elif field.kind == "list":
                    var = tk.StringVar(value=value)
                    widget = ttk.Combobox(page, textvariable=var, values=field.options,
                                          state="readonly", width=44, font=fonts.normal)
                    self.vars[field.name] = var
                else:
                    var = tk.StringVar(value=value)
                    widget = tk.Entry(page, textvariable=var, width=46, font=fonts.normal,
                                      relief="solid", borderwidth=1)
                    self.vars[field.name] = var
                widget.grid(row=row, column=1, sticky="ew", pady=3, ipady=2)
            first = first or widget
            row += 1

        tk.Frame(self, height=1, background=theme.GRAY).pack(fill="x")
        buttons = tk.Frame(self, background=theme.WHITE, padx=10, pady=8)
        buttons.pack(fill="x")
        if preview:
            tk.Button(buttons, text="Preview Code", width=12, font=fonts.button,
                      command=self.show_preview).pack(side="left")
        tk.Button(buttons, text="Cancel", width=10, font=fonts.button,
                  command=self.destroy).pack(side="right")
        tk.Button(buttons, text="Ok", width=10, font=fonts.button, default="active",
                  command=self.ok).pack(side="right", padx=6)
        tk.Button(buttons, text="Again", width=10, font=fonts.button,
                  command=self.again).pack(side="right")

        self.bind("<Return>", self._enter)
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        if first is not None:
            first.focus_set()
            if isinstance(first, tk.Entry):
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

    def again(self):
        """Put the default values back (the "Again" button of PWCT)."""
        defaults = self.component.default_values()
        for name, var in self.vars.items():
            var.set(defaults.get(name, ""))
        for name, widget in self.memos.items():
            widget.delete("1.0", "end")
            widget.insert("1.0", defaults.get(name, ""))

    def show_preview(self):
        try:
            text = self.preview(self.component, self.values())
        except TemplateError as exc:
            text = "Template error: %s" % exc
        except Exception as exc:          # a required field is empty ...
            text = str(exc)
        win = tk.Toplevel(self)
        win.title("Preview - " + self.component.name)
        box = tk.Text(win, width=70, height=18, font=self.fonts.code)
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
