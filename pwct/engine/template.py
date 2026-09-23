"""Component template language.

A port of the RPWI template directives used by the original PWCT
(Programming Without Coding Technology) transporter files (TRF).

A template is plain text.  Lines that start with ``<PWCT:NAME>`` (or the
original ``<RPWI:NAME>`` spelling) are directives, every other line is code.
Placeholders like ``<name>`` are replaced with the value the user typed in
the interaction page.  A placeholder may carry filters: ``<name|repr>``,
``<name|space|repr>`` (see ``FILTERS``).

Conditional directives (resolved while expanding):

``<PWCT:VALUE> v``      set the value that ``TEST`` looks for (default ``0``)
``<PWCT:POSITIVE>``     ``TEST`` blocks are kept when the value is found
``<PWCT:NEGATIVE>``     ``TEST`` blocks are kept when the value is NOT found
``<PWCT:TEST> text``    start a block, closed by ``<PWCT:ENDTEST>``
``<PWCT:IF> a == b``    start a block (also ``a != b``, ``a``, ``not a``),
``<PWCT:ELSE>``         closed by ``<PWCT:ENDIF>``
``<PWCT:FOREACH> v in <list>``  repeat the lines up to ``<PWCT:ENDFOREACH>``
                        for every comma separated item, as placeholder ``<v>``
``<PWCT:NOTE> text``    comment inside the template, ignored

Structural directives (returned as operations for the goal designer):

``<PWCT:NEWSTEP> title``   create a new step, following code belongs to it
``<PWCT:PUTMARK> n``       remember the last created step as mark ``n``
``<PWCT:SETMARK> n``       new steps become children of mark ``n``
``<PWCT:INFORMATION> t``   add an information line to the current step
``<PWCT:IMPORT> module``   the step needs ``import module`` (or a full
                           ``from x import y`` line) at the top of the file
``<PWCT:IGNORELAST> c``    remove trailing ``c`` from the step's last line
``<PWCT:TABPUSH>`` / ``<PWCT:TABPOP>``  indent / unindent following lines
"""

import keyword
import re

DIRECTIVE_RE = re.compile(r"^\s*<(?:RPWI|PWCT):([A-Za-z]+)>[ \t]?(.*)$")
PLACEHOLDER_RE = re.compile(r"<([A-Za-z_][A-Za-z0-9_]*)((?:\|[A-Za-z_]+)*)>")

CONDITIONAL = {"VALUE", "POSITIVE", "NEGATIVE", "TEST", "ENDTEST",
               "IF", "ELSE", "ENDIF", "NOTE", "FOREACH", "ENDFOREACH"}
FOREACH_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(.*)$")
STRUCTURAL = {"NEWSTEP", "PUTMARK", "SETMARK", "INFORMATION", "IMPORT",
              "IGNORELAST", "IGNORELEVEL", "TABPUSH", "TABPOP"}
FALSE_WORDS = {"", "0", "false", "no", "none"}


class TemplateError(Exception):
    pass


def to_ident(value):
    """Turn any text into a valid Python identifier."""
    ident = re.sub(r"\W+", "_", value.strip())
    if not ident:
        return "_"
    if ident[0].isdigit():
        ident = "_" + ident
    if keyword.iskeyword(ident):
        ident += "_"
    return ident


FILTERS = {
    "repr": repr,
    "upper": str.upper,
    "lower": str.lower,
    "title": str.title,
    "strip": str.strip,
    "ident": to_ident,
    "or_none": lambda v: v.strip() or "None",
    "comment": lambda v: "\n".join("# " + line for line in v.split("\n")),
    "name": lambda v: re.split(r"[=:]", v, maxsplit=1)[0].strip(),
    "space": lambda v: v if not v or v[-1].isspace() else v + " ",
}


def substitute(text, values):
    """Replace ``<name>`` placeholders; unknown names are left untouched."""

    def replace(match):
        key = match.group(1).lower()
        if key not in values:
            return match.group(0)
        value = values[key]
        for name in match.group(2).split("|")[1:]:
            if name.lower() not in FILTERS:
                raise TemplateError("Unknown filter: %s" % name)
            value = FILTERS[name.lower()](value)
        return value

    return PLACEHOLDER_RE.sub(replace, text)


def truthy(text):
    return text.strip().lower() not in FALSE_WORDS


def eval_condition(expr, values):
    for op in ("==", "!="):
        if op in expr:
            left, right = expr.split(op, 1)
            equal = substitute(left, values).strip() == substitute(right, values).strip()
            return equal if op == "==" else not equal
    expr = expr.strip()
    if expr.lower().startswith("not "):
        return not truthy(substitute(expr[4:], values))
    return truthy(substitute(expr, values))


def expand(template, values):
    """Expand a template into a list of ``(operation, argument)`` tuples.

    Operations are ``code`` plus the lower-cased structural directives.
    """
    values = {str(k).lower(): "" if v is None else str(v) for k, v in values.items()}
    lines = [l.replace("\t", "    ") for l in template.splitlines()]
    return _expand(lines, 0, values)


def _find_end(lines, start, offset):
    """Index of the ``ENDFOREACH`` closing the ``FOREACH`` at ``start``."""
    depth = 0
    for i in range(start, len(lines)):
        match = DIRECTIVE_RE.match(lines[i])
        if not match:
            continue
        name = match.group(1).upper()
        if name == "FOREACH":
            depth += 1
        elif name == "ENDFOREACH":
            depth -= 1
            if depth == 0:
                return i
    raise TemplateError("Line %d: <PWCT:FOREACH> without <PWCT:ENDFOREACH>" % (start + offset + 1))


def _expand(lines, offset, values):
    ops = []
    active = [True]          # stack of "is this block kept"
    kinds = []               # "test" or "if" for each open block
    test_value, positive = "0", False
    i = 0
    while i < len(lines):
        line = lines[i]
        lineno = i + offset + 1
        i += 1
        match = DIRECTIVE_RE.match(line)
        if not match:
            if active[-1]:
                text = substitute(line, values)
                if "\n" in text:
                    indent = line[:len(line) - len(line.lstrip())]
                    parts = text.split("\n")
                    text = "\n".join([parts[0]] + [indent + p for p in parts[1:]])
                for part in text.split("\n"):
                    if part.strip():
                        ops.append(("code", part.rstrip()))
            continue

        name, arg = match.group(1).upper(), match.group(2).strip()
        if name not in CONDITIONAL and name not in STRUCTURAL:
            raise TemplateError("Line %d: unknown directive <PWCT:%s>" % (lineno, name))

        if name == "FOREACH":
            end = _find_end(lines, i - 1, offset)
            if active[-1]:
                loop = FOREACH_RE.match(arg)
                if not loop:
                    raise TemplateError("Line %d: use <PWCT:FOREACH> name in <list>" % lineno)
                var = loop.group(1).lower()
                items = [x.strip() for x in substitute(loop.group(2), values).split(",")]
                for item in items:
                    if item:
                        ops.extend(_expand(lines[i:end], offset + i, dict(values, **{var: item})))
            i = end + 1
        elif name == "ENDFOREACH":
            raise TemplateError("Line %d: <PWCT:ENDFOREACH> without <PWCT:FOREACH>" % lineno)
        elif name in ("TEST", "IF"):
            if name == "TEST":
                found = bool(test_value) and test_value in substitute(arg, values)
                keep = found if positive else not found
            else:
                keep = eval_condition(arg, values)
            active.append(active[-1] and keep)
            kinds.append(name.lower())
        elif name == "ELSE":
            if not kinds or kinds[-1] != "if":
                raise TemplateError("Line %d: <PWCT:ELSE> without <PWCT:IF>" % lineno)
            active[-1] = active[-2] and not active[-1]
        elif name in ("ENDTEST", "ENDIF"):
            if not kinds:
                raise TemplateError("Line %d: <PWCT:%s> without opening block" % (lineno, name))
            kinds.pop()
            active.pop()
        elif not active[-1] or name == "NOTE":
            continue
        elif name == "VALUE":
            test_value = substitute(arg, values).strip()
        elif name == "POSITIVE":
            positive = True
        elif name == "NEGATIVE":
            positive = False
        else:
            arg = substitute(arg, values).split("\n")[0].strip()
            ops.append((name.lower(), arg))

    if kinds:
        raise TemplateError("Template ends inside an open <PWCT:%s> block" % kinds[-1].upper())
    return ops
