"""Loading components (.pwc files).

A component joins what the original PWCT kept in three files: the
interaction page (IDF/ISF), the transporter with its template (TRF) and the
entry in the components tree (PAF).  A ``.pwc`` file has three sections::

    [component]
    name: Print
    category: Console
    description: Print a message on the screen
    position: auto        (where to insert: auto, inside, after, before)
    layout: rows          (rows: one field per row, flow: fields share a
                           row until "enter", like the PWCT pages generator)

    [interaction]
    title Print
    text! msg | Message | Hello, World!
    list kind | Message type | Text | Text, Expression
    check newline | New line | 1

    [template]
    <PWCT:NEWSTEP> Print <msg>
    print(<msg|repr>)

Interaction lines are ``kind name | label | default | options``.
Kinds (the PWCT interaction script command in brackets):

``title``      a title bar (TITLE)          ``help``       a line of help text
``enter``      start a new row (ENTER)      ``page``       start a new page
``text``       large text box (LARGEGET)    ``small``      small text box (SMALLGET)
``memo``       multi-line text              ``check``      check box, ``1``/``0``
``list``       list box (LISTBOX), the value is the chosen item
``listindex``  list box, the value is the item number (1, 2 ...)

A ``!`` after the kind marks a required field.  Options are separated by
commas.  Labels and values can not contain ``|``.
"""

import os
import re

from .template import DIRECTIVE_RE, PLACEHOLDER_RE, TemplateError, expand

BUILTIN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "components")
INPUT_KINDS = ("text", "small", "memo", "check", "list", "listindex")
LAYOUT_KINDS = ("title", "help", "enter", "page")
FIELD_KINDS = set(INPUT_KINDS) | set(LAYOUT_KINDS)
KEY_RE = re.compile(r"^[A-Za-z0-9_\-]+(/[A-Za-z0-9_\-]+)*$")


def user_dir():
    """Where installed (user) components are kept."""
    home = os.environ.get("PWCT_HOME") or os.path.join(os.path.expanduser("~"), ".pwct-python")
    return os.path.join(home, "components")


class Field:
    def __init__(self, kind, name="", label="", default="", options=None, required=False):
        self.kind = kind
        self.name = name
        self.label = label            # may be empty: the name is shown
        self.default = default
        self.options = options or []
        self.required = required

    @property
    def is_input(self):
        return self.kind in INPUT_KINDS

    @property
    def caption(self):
        return self.label or self.name

    def to_line(self):
        head = self.kind + ("!" if self.required else "")
        if not self.is_input:
            return (head + " " + self.label).rstrip()
        default = self.default.replace("\n", "\\n") if self.kind == "memo" else self.default
        parts = [self.name, self.label, default, ", ".join(self.options)]
        while parts and not parts[-1]:
            parts.pop()
        return head + " " + " | ".join(parts)


class Component:
    def __init__(self, key, name, category, description, fields, template, path=None,
                 position="auto", layout="rows"):
        self.key = key
        self.position = position
        self.layout = layout
        self.name = name
        self.category = category
        self.description = description
        self.fields = fields
        self.template = template
        self.path = path

    def input_fields(self):
        return [f for f in self.fields if f.is_input]

    def default_values(self):
        values = {}
        for f in self.input_fields():
            if f.kind == "check":
                values[f.name] = "1" if f.default.strip() in ("1", "true", "yes") else "0"
            elif f.kind == "list" and not f.default and f.options:
                values[f.name] = f.options[0]
            elif f.kind == "listindex" and not f.default:
                values[f.name] = "1" if f.options else ""
            elif f.kind == "memo":
                values[f.name] = f.default.replace("\\n", "\n")
            else:
                values[f.name] = f.default
        return values

    def validate(self, values):
        """Return a list of error messages for the given values."""
        errors = []
        for f in self.input_fields():
            if f.required and not str(values.get(f.name, "")).strip():
                errors.append("'%s' is required" % f.caption)
        return errors

    def expand(self, values):
        full = self.default_values()
        full.update(values)
        return expand(self.template, full)

    @property
    def builtin(self):
        return bool(self.path) and os.path.abspath(self.path).startswith(os.path.abspath(BUILTIN_DIR))

    def to_text(self):
        """The ``.pwc`` file text of the component."""
        meta = ["name: " + self.name, "category: " + self.category]
        if self.description:
            meta.append("description: " + self.description)
        if self.position != "auto":
            meta.append("position: " + self.position)
        if self.layout != "rows":
            meta.append("layout: " + self.layout)
        return ("[component]\n" + "\n".join(meta) + "\n\n[interaction]\n"
                + "".join(f.to_line() + "\n" for f in self.fields)
                + "\n[template]\n" + self.template.strip("\n") + "\n")

    def __repr__(self):
        return "<Component %s>" % self.key


def parse_field(line):
    head, _, rest = line.partition(" ")
    kind = head.strip().lower()
    required = kind.endswith("!")
    kind = kind.rstrip("!")
    if kind not in FIELD_KINDS:
        raise ValueError("unknown field kind %r" % head)
    if kind in LAYOUT_KINDS:
        return Field(kind, label=rest.strip())
    parts = [p.strip() for p in rest.split("|")]
    parts += [""] * (4 - len(parts))
    name, label, default, options = parts[:4]
    if not name.isidentifier():
        raise ValueError("invalid field name %r" % name)
    options = [o.strip() for o in options.split(",") if o.strip()]
    return Field(kind, name, label, default, options, required)


def parse_component(text, key, path=None):
    sections = {"component": [], "interaction": [], "template": []}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower() in ("[component]", "[interaction]", "[template]"):
            current = stripped[1:-1].lower()
            continue
        if current is None:
            continue
        sections[current].append(line)

    meta = {}
    for line in sections["component"]:
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            meta[k.strip().lower()] = v.strip()

    fields = []
    for n, line in enumerate(sections["interaction"], 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            fields.append(parse_field(line.strip()))
        except ValueError as exc:
            raise TemplateError("%s: interaction line %d: %s" % (key, n, exc))

    template = "\n".join(sections["template"]).strip("\n")
    if not template:
        raise TemplateError("%s: empty template" % key)
    name = meta.get("name") or key.rsplit("/", 1)[-1]
    return Component(key, name, meta.get("category", "Other"),
                     meta.get("description", ""), fields, template, path,
                     meta.get("position", "auto").lower(), meta.get("layout", "rows").lower())


class Library:
    """All the components available to a project, by key."""

    def __init__(self):
        self.components = {}

    def load_dir(self, root):
        for folder, _dirs, files in sorted(os.walk(root)):
            for filename in sorted(files):
                if not filename.endswith(".pwc"):
                    continue
                path = os.path.join(folder, filename)
                key = os.path.relpath(path, root)[:-4].replace(os.sep, "/")
                with open(path, encoding="utf-8") as fh:
                    self.components[key] = parse_component(fh.read(), key, path)
        return self

    @classmethod
    def default(cls):
        """The built-in components, then the installed ones (they replace a
        built-in component with the same key), then the folders listed in
        ``PWCT_COMPONENTS``."""
        lib = cls().load_dir(BUILTIN_DIR)
        extra = [user_dir()] + os.environ.get("PWCT_COMPONENTS", "").split(os.pathsep)
        for folder in extra:
            if folder and os.path.isdir(folder):
                lib.load_dir(folder)
        return lib

    def install(self, component, folder=None):
        """Save a component in the user folder ("Install Component")."""
        if not KEY_RE.match(component.key or ""):
            raise ValueError("Invalid component file name: %r (use letters, digits, _ and /)"
                             % component.key)
        text = component.to_text()
        parse_component(text, component.key)          # never install a broken file
        path = os.path.join(folder or user_dir(), *component.key.split("/")) + ".pwc"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        component.path = path
        self.components[component.key] = component
        return path

    def uninstall(self, key):
        """Remove an installed component (built-in ones can not be removed)."""
        comp = self.components.get(key)
        if comp is None:
            raise KeyError(key)
        if comp.builtin or not comp.path:
            raise ValueError("%s is a built-in component" % key)
        os.remove(comp.path)
        del self.components[key]
        if os.path.exists(os.path.join(BUILTIN_DIR, *key.split("/")) + ".pwc"):
            builtin = Library().load_dir(BUILTIN_DIR)
            self.components[key] = builtin[key]

    def domains(self):
        return sorted({c.category for c in self})

    def __getitem__(self, key):
        return self.components[key]

    def __contains__(self, key):
        return key in self.components

    def __iter__(self):
        return iter(self.components.values())

    def __len__(self):
        return len(self.components)

    def categories(self):
        """``{category: [components]}`` in a stable order."""
        result = {}
        for comp in sorted(self, key=lambda c: (c.category, c.name)):
            result.setdefault(comp.category, []).append(comp)
        return result

    def search(self, text):
        words = text.lower().split()
        return [c for c in self
                if all(w in (c.name + " " + c.category + " " + c.description).lower()
                       for w in words)]


# ------------------------------------------------ matching (Transporter)
def page_variables(component):
    return [f.name for f in component.fields if f.is_input]


def mask_variables(template):
    """Placeholders used in the code mask and variables it creates."""
    used, created = [], []
    for line in template.splitlines():
        match = DIRECTIVE_RE.match(line)
        if match and match.group(1).upper() in ("NEWVAR", "SELECTVAR"):
            name = match.group(2).strip("<> \t")
            if name and name not in created:
                created.append(name)
        if match and match.group(1).upper() == "FOREACH":
            name = match.group(2).split(" in ")[0].strip()
            if name and name not in created:
                created.append(name)
        text = line if not match else match.group(2)
        for m in PLACEHOLDER_RE.finditer(text):
            if m.group(1) not in used:
                used.append(m.group(1))
    return used, created


def matching(component):
    """``[(page variable, mask variable, status)]`` like the Matching page
    of the Transporter Designer."""
    pages = page_variables(component)
    used, created = mask_variables(component.template)
    lower_pages = {p.lower(): p for p in pages}
    lower_created = {c.lower() for c in created}
    rows = []
    for p in pages:
        found = [u for u in used if u.lower() == p.lower()]
        rows.append((p, found[0] if found else "", "OK" if found else "not used in the code mask"))
    for u in used:
        if u.lower() in lower_pages:
            continue
        status = "template variable" if u.lower() in lower_created else "no page variable"
        rows.append(("", u, status))
    return rows
