"""Loading components (.pwc files).

A component joins what the original PWCT kept in three files: the
interaction page (IDF/ISF), the transporter with its template (TRF) and the
entry in the components tree (PAF).  A ``.pwc`` file has three sections::

    [component]
    name: Print
    category: Console
    description: Print a message on the screen
    position: auto        (where to insert: auto, inside, after, before)

    [interaction]
    title Print
    text! msg | Message | Hello, World!
    list kind | Message type | Text | Text, Expression
    check newline | New line | 1

    [template]
    <PWCT:NEWSTEP> Print <msg>
    print(<msg|repr>)

Interaction lines are ``kind name | label | default | options``.
Kinds: ``title`` (page section), ``text``, ``memo`` (multi-line text),
``check`` (value ``1`` or ``0``), ``list`` (comma separated options) and
``help`` (a line of help text).  A ``!`` after the kind marks a required
field.
"""

import os

from .template import TemplateError, expand

BUILTIN_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "components")
FIELD_KINDS = {"text", "memo", "check", "list", "title", "help"}


class Field:
    def __init__(self, kind, name="", label="", default="", options=None, required=False):
        self.kind = kind
        self.name = name
        self.label = label or name
        self.default = default
        self.options = options or []
        self.required = required

    @property
    def is_input(self):
        return self.kind not in ("title", "help")


class Component:
    def __init__(self, key, name, category, description, fields, template, path=None,
                 position="auto"):
        self.key = key
        self.position = position
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
                errors.append("'%s' is required" % f.label)
        return errors

    def expand(self, values):
        full = self.default_values()
        full.update(values)
        return expand(self.template, full)

    def __repr__(self):
        return "<Component %s>" % self.key


def parse_field(line):
    head, _, rest = line.partition(" ")
    kind = head.strip().lower()
    required = kind.endswith("!")
    kind = kind.rstrip("!")
    if kind not in FIELD_KINDS:
        raise ValueError("unknown field kind %r" % head)
    if kind in ("title", "help"):
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
                     meta.get("position", "auto").lower())


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
        lib = cls().load_dir(BUILTIN_DIR)
        for extra in os.environ.get("PWCT_COMPONENTS", "").split(os.pathsep):
            if extra and os.path.isdir(extra):
                lib.load_dir(extra)
        return lib

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
