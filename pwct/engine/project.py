"""The Goal Designer model: a tree of steps built by interactions.

Every time the user fills an interaction page, the component template is
expanded and the resulting steps are inserted in the tree.  Steps remember
the interaction that created them, so the interaction can be opened again
and the steps regenerated while the steps the user added under them are
kept - the same way the original PWCT goal designer works.
"""

import copy
import json

FORMAT = "pwct-python"
VERSION = 1


class Step:
    def __init__(self, id, title, code=None, info=None, interaction=None, num=0,
                 disabled=False, children=None, imports=None):
        self.id = id
        self.imports = imports or []
        self.title = title
        self.code = code or []
        self.info = info or []
        self.interaction = interaction
        self.num = num
        self.disabled = disabled
        self.children = children or []
        self.parent = None
        for child in self.children:
            child.parent = self

    def _statements(self):
        return [l for l in self.code if l.strip() and not l.strip().startswith("#")]

    @property
    def is_block(self):
        """The step's code ends with ``:`` (``if``, ``for``, ``def`` ...)."""
        lines = self._statements()
        return bool(lines) and lines[-1].rstrip().endswith(":")

    @property
    def child_indent(self):
        """How many levels the children are indented: they continue where
        the step's code ends (one level more after a ``:``)."""
        lines = self._statements()
        if not lines:
            return 0
        last = lines[-1]
        level = (len(last) - len(last.lstrip())) // 4
        return level + (1 if last.rstrip().endswith(":") else 0)

    @property
    def accepts_children(self):
        """The root, grouping steps (no code) and steps that open a block."""
        return (self.parent is None or not self.code
                or any(l.rstrip().endswith(":") for l in self._statements()))

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def index(self):
        return self.parent.children.index(self)

    def add(self, step, index=None):
        step.parent = self
        if index is None:
            self.children.append(step)
        else:
            self.children.insert(index, step)
        return step

    def to_dict(self):
        data = {"id": self.id, "title": self.title}
        if self.code:
            data["code"] = self.code
        if self.info:
            data["info"] = self.info
        if self.imports:
            data["imports"] = self.imports
        if self.interaction:
            data["interaction"] = self.interaction
            data["num"] = self.num
        if self.disabled:
            data["disabled"] = True
        if self.children:
            data["children"] = [c.to_dict() for c in self.children]
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(data["id"], data.get("title", ""), list(data.get("code", [])),
                   list(data.get("info", [])), data.get("interaction"),
                   data.get("num", 0), data.get("disabled", False),
                   [cls.from_dict(c) for c in data.get("children", [])],
                   list(data.get("imports", [])))

    def __repr__(self):
        return "<Step %s %r>" % (self.id, self.title)


class Interaction:
    def __init__(self, id, component, values):
        self.id = id
        self.component = component
        self.values = dict(values)

    def to_dict(self):
        return {"component": self.component, "values": self.values}


class ProjectError(Exception):
    pass


class Project:
    def __init__(self, name="Untitled"):
        self.name = name
        self.root = Step("1", "Start Here")
        self.interactions = {}
        self.next_id = 2

    # ------------------------------------------------------------------ ids
    def new_id(self):
        value = str(self.next_id)
        self.next_id += 1
        return value

    def find(self, step_id):
        for step in self.root.walk():
            if step.id == step_id:
                return step
        return None

    def steps_of(self, interaction_id):
        return [s for s in self.root.walk() if s.interaction == interaction_id]

    # --------------------------------------------------------- interactions
    def insert_position(self, selected, mode="auto"):
        """Where a new component goes when ``selected`` is the active step.

        ``mode`` is ``inside``, ``after``, ``before`` or ``auto`` (inside
        when the step can hold steps, otherwise right after it)."""
        if selected is None:
            selected = self.root
        if selected is self.root or mode == "inside":
            return selected, len(selected.children)
        if mode == "before":
            return selected.parent, selected.index()
        if mode == "auto" and selected.accepts_children:
            return selected, len(selected.children)
        return selected.parent, selected.index() + 1

    def apply(self, component, values, parent=None, index=None):
        """Run the interaction for ``component`` and insert the steps under
        ``parent`` at ``index``.  Returns the first created step."""
        full = component.default_values()
        full.update(values)
        errors = component.validate(full)
        if errors:
            raise ProjectError("\n".join(errors))
        parent = parent or self.root
        if index is None:
            index = len(parent.children)
        interaction = Interaction(self.new_id(), component.key, full)
        created = self._build(component.expand(full), interaction, parent, index, {})
        if not created:
            raise ProjectError("The component did not create any step")
        self.interactions[interaction.id] = interaction
        return created[0]

    def edit(self, interaction_id, component, values):
        """Open an interaction again with new values and regenerate its
        steps, keeping the steps the user added under them."""
        full = component.default_values()
        full.update(values)
        errors = component.validate(full)
        if errors:
            raise ProjectError("\n".join(errors))
        interaction = self.interactions[interaction_id]
        old = self.steps_of(interaction_id)
        if not old:
            raise ProjectError("The steps of this interaction were deleted")
        first = min(old, key=lambda s: s.num)
        parent, index = first.parent, first.index()
        existing = {s.num: s for s in old}
        interaction.values = full
        interaction.component = component.key
        created = self._build(component.expand(full), interaction, parent, index, existing)
        kept = {s.id for s in created}
        for step in old:
            if step.id in kept or step.parent is None:
                continue
            # a step that is no longer generated: keep the user's steps
            pos = step.index()
            step.parent.children.remove(step)
            for child in reversed(step.children):
                step.parent.add(child, pos)
        return created[0] if created else None

    def _build(self, ops, interaction, anchor, index, existing):
        marks = {}
        cursor = anchor
        target = None
        last = None
        created = []
        extra_indent = 0
        next_index = {id(anchor): index}
        num = 0
        pending = {}   # step id -> code lines to dedent

        def owned(step):
            return step is not None and step.interaction == interaction.id

        for op, arg in ops:
            if op == "newstep":
                num += 1
                step = existing.get(num)
                if step is not None:
                    step.title = arg
                    step.code, step.info, step.imports = [], [], []
                    if step.parent is not cursor:
                        step.parent.children.remove(step)
                        self._place(cursor, step, next_index)
                    else:
                        next_index[id(cursor)] = step.index() + 1
                else:
                    step = Step(self.new_id(), arg, interaction=interaction.id, num=num)
                    self._place(cursor, step, next_index)
                created.append(step)
                pending[step.id] = []
                last = target = step
                extra_indent = 0
            elif op == "putmark":
                marks[arg] = last
            elif op == "setmark":
                cursor = marks.get(arg) or anchor
                target = cursor if owned(cursor) else None
                extra_indent = 0
            elif op == "information":
                if owned(target):
                    target.info.append(arg)
            elif op == "import":
                if owned(target) and arg not in target.imports:
                    target.imports.append(arg)
            elif op == "tabpush":
                extra_indent += 1
            elif op == "tabpop":
                extra_indent = max(0, extra_indent - 1)
            elif op == "ignorelast":
                if owned(target) and pending[target.id]:
                    lines = pending[target.id]
                    lines[-1] = lines[-1].rstrip()
                    if arg and lines[-1].endswith(arg):
                        lines[-1] = lines[-1][:-len(arg)].rstrip()
            elif op == "code":
                if target is None:
                    num += 1
                    step = existing.get(num) or Step(self.new_id(), "", interaction=interaction.id, num=num)
                    if step.parent is None:
                        self._place(cursor, step, next_index)
                    step.code, step.info, step.imports = [], [], []
                    created.append(step)
                    pending[step.id] = []
                    last = target = step
                if owned(target):
                    pending[target.id].append("    " * extra_indent + arg)

        for step in created:
            step.code = dedent(pending.get(step.id, []))
            if not step.title:
                step.title = step.code[0].strip() if step.code else "Step"
        return created

    def _place(self, parent, step, next_index):
        pos = next_index.get(id(parent), len(parent.children))
        parent.add(step, pos)
        next_index[id(parent)] = pos + 1

    # ------------------------------------------------------ tree operations
    def check_editable(self, step):
        if step is None or step is self.root:
            raise ProjectError("The root step can not be changed this way")

    def delete(self, step):
        self.check_editable(step)
        step.parent.children.remove(step)
        step.parent = None
        self.cleanup()

    def move(self, step, delta):
        self.check_editable(step)
        siblings = step.parent.children
        pos = siblings.index(step)
        new = pos + delta
        if 0 <= new < len(siblings):
            siblings.insert(new, siblings.pop(pos))
            return True
        return False

    def outdent(self, step):
        """Move a step out of its parent (it becomes the parent's sibling)."""
        self.check_editable(step)
        parent = step.parent
        if parent is self.root:
            return False
        parent.children.remove(step)
        parent.parent.add(step, parent.index() + 1)
        return True

    def indent(self, step):
        """Move a step inside the previous sibling."""
        self.check_editable(step)
        pos = step.index()
        if pos == 0:
            return False
        prev = step.parent.children[pos - 1]
        step.parent.children.remove(step)
        prev.add(step)
        return True

    def set_disabled(self, step, disabled):
        self.check_editable(step)
        step.disabled = disabled

    def copy_steps(self, step):
        """Serialise a step (with its children and interactions) for the
        clipboard."""
        self.check_editable(step)
        ids = {s.interaction for s in step.walk() if s.interaction}
        return {"step": step.to_dict(),
                "interactions": {i: self.interactions[i].to_dict() for i in ids
                                 if i in self.interactions}}

    def paste(self, clip, parent, index=None):
        """Insert a copy made by :meth:`copy_steps`; new ids are given to
        the steps and interactions."""
        step = Step.from_dict(copy.deepcopy(clip["step"]))
        mapping = {}
        for old_id, data in clip.get("interactions", {}).items():
            new_id = self.new_id()
            mapping[old_id] = new_id
            self.interactions[new_id] = Interaction(new_id, data["component"], data["values"])
        for s in step.walk():
            s.id = self.new_id()
            if s.interaction:
                s.interaction = mapping.get(s.interaction)
                if s.interaction is None:
                    s.num = 0
        if index is None:
            index = len(parent.children)
        parent.add(step, index)
        return step

    def cleanup(self):
        used = {s.interaction for s in self.root.walk()}
        for key in list(self.interactions):
            if key not in used:
                del self.interactions[key]

    # ------------------------------------------------------- serialisation
    def to_dict(self):
        return {"format": FORMAT, "version": VERSION, "name": self.name,
                "next_id": self.next_id, "root": self.root.to_dict(),
                "interactions": {k: v.to_dict() for k, v in self.interactions.items()}}

    def to_json(self):
        return json.dumps(self.to_dict(), indent=1, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data):
        if data.get("format") != FORMAT:
            raise ProjectError("Not a PWCT-Python project file")
        project = cls(data.get("name", "Untitled"))
        project.root = Step.from_dict(data["root"])
        project.interactions = {k: Interaction(k, v["component"], v.get("values", {}))
                                for k, v in data.get("interactions", {}).items()}
        highest = max(int(s.id) for s in project.root.walk() if s.id.isdigit())
        highest = max([highest] + [int(k) for k in project.interactions if k.isdigit()])
        project.next_id = max(data.get("next_id", 0), highest + 1)
        return project

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(json.loads(text))

    def save(self, path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_json())

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as fh:
            return cls.from_json(fh.read())


def dedent(lines):
    """Remove the common leading indentation of the code lines."""
    lines = [l.replace("\t", "    ").rstrip() for l in lines if l.strip()]
    if not lines:
        return []
    margin = min(len(l) - len(l.lstrip()) for l in lines)
    return [l[margin:] for l in lines]


class History:
    """Undo / redo using snapshots of the whole project."""

    def __init__(self, limit=100):
        self.undo_stack = []
        self.redo_stack = []
        self.limit = limit

    def record(self, project):
        self.undo_stack.append(project.to_json())
        del self.undo_stack[:-self.limit]
        self.redo_stack.clear()

    def undo(self, project):
        if not self.undo_stack:
            return None
        self.redo_stack.append(project.to_json())
        return Project.from_json(self.undo_stack.pop())

    def redo(self, project):
        if not self.redo_stack:
            return None
        self.undo_stack.append(project.to_json())
        return Project.from_json(self.redo_stack.pop())
