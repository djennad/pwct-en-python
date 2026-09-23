"""Interaction pages: the forms the user fills instead of writing code.

The look follows the pages made by the PWCT "Interaction Pages Generator"
(``ipwriter.scx``): a light gray page, TITLE bars in purple with white
text, gray labels, large text boxes, real list boxes and fields that share
a row until ENTER (``flow`` layout).  The dialog follows the "Interaction
Using Transporter" window (``runtrf.scx``): a purple title, a green file
bar, page navigation buttons and Ok / Cancel / Again.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from ..engine.template import TemplateError
from . import theme


def split_pages(fields):
    """``[(page title, [fields])]`` - a ``page`` field starts a new page."""
    pages = [["", []]]
    for field in fields:
        if field.kind == "page":
            if pages[-1][1] or pages[-1][0]:
                pages.append([field.label, []])
            else:
                pages[-1][0] = field.label
        else:
            pages[-1][1].append(field)
    return [(title or "Page %d" % n, items) for n, (title, items) in enumerate(pages, 1)]


class InteractionForm(tk.Frame):
    """The fields of a component; ``values()`` returns what the user typed.

    Used by the interaction dialog and by the live preview of the
    Interaction Designer."""

    def __init__(self, master, component, values=None, fonts=None, width=520, on_change=None):
        super().__init__(master, background=theme.PAGE_BG)
        self.fonts = fonts or theme.Fonts(self)
        self.component = component
        self.on_change = on_change
        self.vars = {}
        self.memos = {}
        self.lists = {}
        self.widgets = {}
        self.first = None
        self.wrap = width - 40
        values = dict(component.default_values(), **(values or {}))
        self.pages = []
        for title, fields in split_pages(component.fields):
            frame = tk.Frame(self, background=theme.PAGE_BG, padx=10, pady=8)
            self._build(frame, fields, values)
            self.pages.append((title, frame))
        self.current = 0
        self.show_page(0)

    # ------------------------------------------------------------- building
    def _row(self, parent):
        row = tk.Frame(parent, background=theme.PAGE_BG)
        row.pack(fill="x", anchor="w", pady=3)
        return row

    def _build(self, page, fields, values):
        flow = self.component.layout == "flow"
        row = None
        previous = None
        for field in fields:
            if field.kind == "title":
                bar = tk.Label(page, text="   " + field.label, anchor="w", font=(self.fonts.header[0], 14),
                               background=theme.TITLE_BAR, foreground=theme.WHITE)
                bar.pack(fill="x", pady=(8 if row is not None else 0, 4))
                row = None
            elif field.kind == "help":
                tk.Label(page, text=field.label, anchor="w", justify="left", wraplength=self.wrap,
                         font=self.fonts.normal, background=theme.PAGE_BG, foreground="#404040").pack(
                    fill="x", pady=2)
                row = None
            elif field.kind == "enter":
                row = None
            elif field.is_input:
                if row is None or not flow or field.kind == "memo":
                    row = self._row(page)
                after_check = flow and previous is not None and previous.kind == "check"
                self._field(row, field, values.get(field.name, ""), show_label=not (
                    after_check and not field.label))
                if field.kind == "memo" and flow:
                    row = None
            previous = field

    def _label(self, row, field):
        text = field.caption + (" *" if field.required else "")
        tk.Label(row, text=text, anchor="w", font=(self.fonts.normal[0], 9), background=theme.FACE,
                 padx=6, pady=4, width=max(len(text) + 2, 12) if self.component.layout == "flow" else 22
                 ).pack(side="left", fill="y", padx=(0, 6))

    def _field(self, row, field, value, show_label=True):
        entry_font = (self.fonts.normal[0], 12)
        if field.kind == "check":
            var = tk.StringVar(value="1" if value == "1" else "0")
            widget = tk.Checkbutton(row, text=field.caption, variable=var, onvalue="1", offvalue="0",
                                    font=(self.fonts.normal[0], 9), background=theme.WHITE,
                                    activebackground=theme.WHITE, highlightthickness=0, anchor="w",
                                    padx=4, pady=3, command=self._changed)
            widget.pack(side="left", padx=(0, 8))
            self.vars[field.name] = var
        else:
            if show_label:
                self._label(row, field)
            if field.kind == "memo":
                widget = tk.Text(row, width=46, height=6, wrap="none", undo=True, font=self.fonts.code,
                                 relief="solid", borderwidth=1)
                widget.insert("1.0", value)
                widget.bind("<Tab>", self._memo_tab)
                widget.bind("<<Modified>>", self._memo_modified)
                widget.pack(side="left", fill="x", expand=True)
                self.memos[field.name] = widget
            elif field.kind in ("list", "listindex"):
                holder = tk.Frame(row, background=theme.WHITE, relief="solid", borderwidth=1)
                box = tk.Listbox(holder, height=min(max(len(field.options), 2), 4), width=26,
                                 exportselection=False, font=(self.fonts.normal[0], 11), relief="flat",
                                 borderwidth=0, activestyle="none", selectbackground=theme.SELECT)
                for option in field.options:
                    box.insert("end", option)
                if len(field.options) > 4:
                    scroll = ttk.Scrollbar(holder, orient="vertical", command=box.yview)
                    box.configure(yscrollcommand=scroll.set)
                    scroll.pack(side="right", fill="y")
                box.pack(side="left", fill="both", expand=True)
                index = self._list_index(field, value)
                if index is not None:
                    box.selection_set(index)
                    box.see(index)
                box.bind("<<ListboxSelect>>", lambda e: self._changed())
                holder.pack(side="left", padx=(0, 8))
                self.lists[field.name] = (box, field)
                widget = box
            else:
                var = tk.StringVar(value=value)
                width = 8 if field.kind == "small" else 28
                widget = tk.Entry(row, textvariable=var, width=width, font=entry_font, relief="solid",
                                  borderwidth=1)
                widget.pack(side="left", padx=(0, 8), ipady=1, fill="x",
                            expand=self.component.layout != "flow")
                var.trace_add("write", lambda *a: self._changed())
                self.vars[field.name] = var
        self.widgets[field.name] = widget
        self.first = self.first or widget

    @staticmethod
    def _list_index(field, value):
        if field.kind == "listindex":
            try:
                n = int(str(value).strip()) - 1
            except ValueError:
                return None
            return n if 0 <= n < len(field.options) else None
        return field.options.index(value) if value in field.options else None

    def _memo_tab(self, event):
        event.widget.insert("insert", "    ")
        return "break"

    def _memo_modified(self, event):
        if event.widget.edit_modified():
            event.widget.edit_modified(False)
            self._changed()

    def _changed(self):
        if self.on_change:
            self.on_change()

    # --------------------------------------------------------------- values
    def values(self):
        result = {name: var.get() for name, var in self.vars.items()}
        for name, widget in self.memos.items():
            result[name] = widget.get("1.0", "end-1c")
        for name, (box, field) in self.lists.items():
            sel = box.curselection()
            if field.kind == "listindex":
                result[name] = str(sel[0] + 1) if sel else "0"
            else:
                result[name] = box.get(sel[0]) if sel else ""
        return result

    def set_values(self, values):
        for name, var in self.vars.items():
            var.set(values.get(name, ""))
        for name, widget in self.memos.items():
            widget.delete("1.0", "end")
            widget.insert("1.0", values.get(name, ""))
        for name, (box, field) in self.lists.items():
            box.selection_clear(0, "end")
            index = self._list_index(field, values.get(name, ""))
            if index is not None:
                box.selection_set(index)

    # ---------------------------------------------------------------- pages
    def show_page(self, index):
        if not self.pages:
            return
        index = max(0, min(index, len(self.pages) - 1))
        for _title, frame in self.pages:
            frame.pack_forget()
        self.pages[index][1].pack(fill="both", expand=True)
        self.current = index

    def focus_first(self):
        if self.first is not None:
            self.first.focus_set()
            if isinstance(self.first, tk.Entry):
                self.first.select_range(0, "end")


class InteractionPage(tk.Toplevel):
    """The interaction dialog.  After the window closes, ``result`` holds
    the values (or ``None`` when cancelled)."""

    def __init__(self, master, component, values=None, editing=False, preview=None, fonts=None):
        super().__init__(master, background=theme.WHITE)
        self.fonts = fonts = fonts or theme.Fonts(self)
        self.component = component
        self.preview = preview
        self.result = None
        self.title("Interaction Using Transporter")
        self.transient(master)
        self.resizable(True, True)

        head = tk.Frame(self, background=theme.PURPLE)
        head.pack(fill="x")
        tk.Label(head, text=component.name, font=fonts.title_small, background=theme.PURPLE,
                 foreground=theme.WHITE).pack(padx=16, pady=(4, 2))
        bar = tk.Frame(self, background=theme.GREEN)
        bar.pack(fill="x")
        tk.Label(bar, text="File : %s.pwc   -   %s%s" % (component.key, component.category,
                                                           "   (Modify)" if editing else ""),
                 font=fonts.normal, background=theme.GREEN, foreground=theme.BLACK).pack(
            side="left", padx=8, pady=2)

        # scrollable page area
        body = tk.Frame(self, background=theme.PAGE_BG)
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, background=theme.PAGE_BG, highlightthickness=0)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.form = InteractionForm(self.canvas, component, values, fonts)
        self.canvas.create_window(0, 0, window=self.form, anchor="nw")
        self.canvas.pack(side="left", fill="both", expand=True)
        self._scroll = scroll
        self.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        tk.Frame(self, height=1, background=theme.GRAY).pack(fill="x")
        buttons = tk.Frame(self, background=theme.WHITE, padx=10, pady=8)
        buttons.pack(fill="x")
        if len(self.form.pages) > 1:
            self._navigation(buttons)
        if preview:
            tk.Button(buttons, text="Preview Code", width=12, font=fonts.button,
                      command=self.show_preview).pack(side="left", padx=(8, 0))
        tk.Button(buttons, text="Cancel", width=9, font=fonts.button,
                  command=self.destroy).pack(side="right")
        tk.Button(buttons, text="Ok", width=9, font=fonts.button, default="active",
                  command=self.ok).pack(side="right", padx=6)
        tk.Button(buttons, text="Again", width=9, font=fonts.button,
                  command=self.again).pack(side="right")

        self.bind("<Return>", self._enter)
        self.bind("<Escape>", lambda e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.form.focus_first()
        self._fit()
        x = master.winfo_rootx() + (master.winfo_width() - self.winfo_width()) // 2
        y = master.winfo_rooty() + (master.winfo_height() - self.winfo_height()) // 3
        self.geometry("+%d+%d" % (max(x, 0), max(y, 0)))

    def _navigation(self, parent):
        icons = [("|<", 0), ("<", -1), (">", 1), (">|", None)]
        for text, step in icons[:2]:
            tk.Button(parent, text=text, width=3, font=self.fonts.button,
                      command=lambda s=step: self.go(s)).pack(side="left")
        self.page_var = tk.StringVar()
        self.page_box = ttk.Combobox(parent, textvariable=self.page_var, state="readonly", width=18,
                                     values=[t for t, _f in self.form.pages])
        self.page_box.pack(side="left", padx=4)
        self.page_box.bind("<<ComboboxSelected>>", lambda e: self.go_to(self.page_box.current()))
        for text, step in icons[2:]:
            tk.Button(parent, text=text, width=3, font=self.fonts.button,
                      command=lambda s=step: self.go(s)).pack(side="left")
        self.page_var.set(self.form.pages[0][0])

    def go(self, step):
        if step == 0:
            self.go_to(0)
        elif step is None:
            self.go_to(len(self.form.pages) - 1)
        else:
            self.go_to(self.form.current + step)

    def go_to(self, index):
        self.form.show_page(index)
        if hasattr(self, "page_var"):
            self.page_var.set(self.form.pages[self.form.current][0])
        self._fit()

    def _fit(self):
        self.form.update_idletasks()
        width = max(self.form.winfo_reqwidth(), 480)
        height = self.form.winfo_reqheight()
        visible = min(height, int(self.winfo_screenheight() * 0.6))
        self.canvas.configure(width=width, height=visible, scrollregion=(0, 0, width, height))
        if height > visible:
            self._scroll.pack(side="right", fill="y")
        else:
            self._scroll.pack_forget()

    def _enter(self, event):
        if isinstance(event.widget, (tk.Text, tk.Listbox)):
            return None
        self.ok()
        return "break"

    def values(self):
        return self.form.values()

    def again(self):
        """Put the default values back (the "Again" button of PWCT)."""
        self.form.set_values(self.component.default_values())

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
