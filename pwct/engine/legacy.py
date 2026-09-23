"""Import components of the original PWCT 1.x.

PWCT 1.x (the Visual FoxPro "RPWI" environment) keeps a component in DBF
tables with FPT memo files:

* ``TRFn.TRF`` - the transporter: one record per interaction page with the
  page file (``F_FILES``), the code mask (``F_MASK``) and the matching of
  page variables (``F_PAIR1``) to code mask variables (``F_PAIR2``);
* ``IDFn.IDF`` - an interaction page: one record per control (``RECTYPE``
  0 page, 1 label, 2 text box, 3 list box, 4 check box) with its position,
  caption, variable and list items;
* ``ISFn.ISF`` - the interaction script (TITLE, SMALLGET, LARGEGET ...)
  that the "Interaction Pages Generator" turns into an IDF file;
* ``*.PAF`` - the components tree: domains and the TRF file of each
  component.

The code masks use the same RPWI directives as PWCT-Python, so an imported
component works as it is; its code is the Harbour code of the original and
can be changed to Python in the Component Designer.
"""

import datetime
import os
import re
import struct

from .components import Component, Field

TITLE_COLOR = 7685727          # background of TITLE bars made by the pages generator


# --------------------------------------------------------------------- DBF
def _find_file(path, extensions):
    """``path`` with another extension, whatever the case of the name."""
    folder = os.path.dirname(path) or "."
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    wanted = {stem + e.lower() for e in extensions}
    for name in os.listdir(folder):
        if name.lower() in wanted:
            return os.path.join(folder, name)
    return None


def find_case_insensitive(folder, name):
    if not os.path.isdir(folder):
        return None
    for entry in os.listdir(folder):
        if entry.lower() == name.lower():
            return os.path.join(folder, entry)
    return None


class MemoFile:
    def __init__(self, path):
        with open(path, "rb") as fh:
            self.data = fh.read()
        self.block_size = struct.unpack(">H", self.data[6:8])[0] or 64

    def read(self, block):
        start = block * self.block_size
        if block <= 0 or start + 8 > len(self.data):
            return b""
        length = struct.unpack(">I", self.data[start + 4:start + 8])[0]
        return self.data[start + 8:start + 8 + length]


CODE_PAGES = {0x01: "cp437", 0x02: "cp850", 0x03: "cp1252", 0x7D: "cp1255", 0x7E: "cp1256",
              0xC8: "cp1250", 0xC9: "cp1251", 0xCB: "cp1253", 0xCA: "cp1254"}


def read_dbf(path, encoding=None):
    """Read a (Visual) FoxPro table and return its records as dictionaries
    with upper case field names.  Deleted records are skipped."""
    with open(path, "rb") as fh:
        data = fh.read()
    encoding = encoding or CODE_PAGES.get(data[29], "cp1252")
    count, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields = []
    pos = 32
    while pos + 32 <= header_len and data[pos] != 0x0D:
        raw = data[pos:pos + 32]
        name = raw[:11].split(b"\0")[0].decode("ascii", "replace").upper()
        ftype = chr(raw[11])
        offset = struct.unpack("<I", raw[12:16])[0]
        length, decimals = raw[16], raw[17]
        fields.append((name, ftype, offset, length, decimals))
        pos += 32
    # dBase files do not store the offsets: compute them
    if fields and all(f[2] == 0 for f in fields):
        offset, fixed = 1, []
        for name, ftype, _o, length, decimals in fields:
            fixed.append((name, ftype, offset, length, decimals))
            offset += length
        fields = fixed

    memo = None
    if any(f[1] in "MGW" for f in fields):
        memo_path = _find_file(path, [".fpt", ".sct", ".vct", ".dbt"])
        memo = MemoFile(memo_path) if memo_path else None

    records = []
    for n in range(count):
        start = header_len + n * record_len
        rec = data[start:start + record_len]
        if len(rec) < record_len or rec[:1] == b"*":
            continue
        row = {}
        for name, ftype, offset, length, decimals in fields:
            raw = rec[offset:offset + length]
            if ftype in "CV":
                row[name] = raw.decode(encoding, "replace").rstrip(" \0")
            elif ftype in "NF":
                text = raw.decode("ascii", "replace").strip()
                try:
                    row[name] = (float(text) if decimals or "." in text else int(text)) if text else None
                except ValueError:
                    row[name] = None
            elif ftype == "I":
                row[name] = struct.unpack("<i", raw)[0]
            elif ftype == "L":
                row[name] = raw in (b"T", b"t", b"Y", b"y")
            elif ftype == "D":
                text = raw.decode("ascii", "replace").strip()
                row[name] = datetime.date(int(text[:4]), int(text[4:6]), int(text[6:8])) if text else None
            elif ftype in "MGW":
                block = struct.unpack("<i", raw)[0] if length == 4 else int(raw.strip() or 0)
                row[name] = memo.read(block).decode(encoding, "replace") if memo else ""
            else:
                row[name] = raw
        records.append(row)
    return records


# ----------------------------------------------------------- interaction
def _clean(text):
    return re.sub(r"\s+", " ", (text or "").replace("|", "/")).strip()


def _var(name):
    name = re.sub(r"\W", "_", (name or "").strip())
    return name if name.isidentifier() else ("V_" + name if name else "")


def idf_fields(records):
    """Turn the controls of an IDF page into fields (``flow`` layout)."""
    controls = []
    for r in records:
        kind = int(r.get("RECTYPE") or 0)
        if kind in (1, 2, 3, 4):
            controls.append(r)
    controls.sort(key=lambda r: (r.get("O_TOP") or 0, r.get("O_LEFT") or 0))

    rows = []
    for control in controls:
        top = control.get("O_TOP") or 0
        if rows and abs(top - (rows[-1][0].get("O_TOP") or 0)) <= 12:
            rows[-1].append(control)
        else:
            rows.append([control])

    fields = []
    for n, row in enumerate(rows):
        row.sort(key=lambda r: r.get("O_LEFT") or 0)
        if len(row) == 1 and int(row[0]["RECTYPE"]) == 1 and (
                (row[0].get("O_BCOLOR") == TITLE_COLOR) or (row[0].get("O_WIDTH") or 0) > 500
                or (row[0].get("O_FSIZE") or 0) >= 14):
            fields.append(Field("title", label=_clean(row[0].get("O_CAPTION"))))
            continue
        pending = None
        for control in row:
            kind = int(control["RECTYPE"])
            caption = _clean(control.get("O_CAPTION"))
            var = _var(control.get("O_VAR"))
            if kind == 1:
                if pending:
                    fields.append(Field("help", label=pending))
                pending = caption
            elif kind == 2 and var:
                small = (control.get("O_WIDTH") or 0) < 120
                fields.append(Field("small" if small else "text", var, pending or ""))
                pending = None
            elif kind == 3 and var:
                items = [i.strip().replace(",", ";") for i in (control.get("O_OPTIONS") or "").splitlines()
                         if i.strip()]
                returns_item = (control.get("O_TRANS") or 0) == 1
                fields.append(Field("list" if returns_item else "listindex", var, pending or "",
                                    options=items))
                pending = None
            elif kind == 4 and var:
                fields.append(Field("check", var, caption or pending or var, "0"))
                pending = None
        if pending:
            fields.append(Field("help", label=pending))
        if n < len(rows) - 1 and fields and fields[-1].kind not in ("title", "enter"):
            fields.append(Field("enter"))
    while fields and fields[-1].kind == "enter":
        fields.pop()
    return fields


def isf_fields(text):
    """Turn an interaction script (ISF) into fields, naming the variables
    like the PWCT "Interaction Pages Generator" does (``D_TB_``, ``D_CB_``,
    ``D_LB_`` prefixes)."""
    fields = []

    def var(prefix, label):
        return prefix + re.sub(r"\W", "_", label.strip().replace(" ", "_"))

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        cmd, _, arg = line.partition(" ")
        cmd, arg = cmd.upper(), _clean(arg)
        if cmd == "TITLE":
            fields.append(Field("title", label=arg))
        elif cmd == "ENTER":
            fields.append(Field("enter"))
        elif cmd == "SMALLGET":
            fields.append(Field("small", var("D_TB_", arg), arg))
        elif cmd == "LARGEGET":
            fields.append(Field("text", var("D_TB_", arg), arg))
        elif cmd == "LISTBOX":
            fields.append(Field("listindex", var("D_LB_", arg), arg))
        elif cmd == "CHECKBOXALONE":
            fields.append(Field("check", var("D_CB_", arg), arg, "0"))
        elif cmd in ("CHECKBOX", "SMALLCHECKBOX"):
            fields.append(Field("check", var("D_CB_", arg), arg, "0"))
            fields.append(Field("small" if cmd == "SMALLCHECKBOX" else "text", var("D_TB_", arg), ""))
        elif cmd == "CHECKBOXLISTBOX":
            fields.append(Field("check", var("D_CB_", arg), arg, "0"))
            fields.append(Field("listindex", var("D_LB_", arg), ""))
    return fields


# ------------------------------------------------------------ transporter
def _page_file(trf_path, recorded):
    """Find the IDF file of a page: the recorded path is an absolute
    Windows path of the author's computer."""
    name = re.split(r"[\\/]", recorded or "")[-1]
    if not name:
        return None
    base = os.path.dirname(os.path.abspath(trf_path))
    for folder in (base, os.path.join(base, "..", "IDF"), os.path.join(base, "IDF")):
        found = find_case_insensitive(folder, name)
        if found:
            return found
    return None


def _paf_info(trf_path):
    """``(name, domain)`` of a TRF from the components tree (PAF) found
    next to the TRF folder, or ``(None, None)``."""
    base = os.path.dirname(os.path.abspath(trf_path))
    trf_name = os.path.basename(trf_path).lower()
    for folder in (base, os.path.dirname(base)):
        for entry in os.listdir(folder):
            if not entry.lower().endswith(".paf"):
                continue
            try:
                records = read_dbf(os.path.join(folder, entry))
            except (OSError, struct.error, ValueError):
                continue
            domains = {}
            for r in records:
                if int(r.get("RECTYPE") or 0) == 2:
                    domains[str(r.get("REG2")).strip()] = (str(r.get("REG1")).strip(), _clean(r.get("REG3")))
            for r in records:
                if int(r.get("RECTYPE") or 0) != 3:
                    continue
                if re.split(r"[\\/]", r.get("REG3") or "")[-1].lower() != trf_name:
                    continue
                chain, key = [], str(r.get("REG1")).strip()
                while key in domains and len(chain) < 20:
                    parent, label = domains[key]
                    chain.insert(0, label)
                    key = parent
                return _clean(r.get("REG2")), "/".join(chain[1:] or chain)
    return None, None


def import_trf(path, key=None):
    """Read a PWCT 1.x component (TRF + IDF pages) as a Component."""
    records = read_dbf(path)
    if not records:
        raise ValueError("%s has no pages" % path)
    fields, mapping, used = [], {}, set()
    mask = ""
    missing = []
    for n, rec in enumerate(records, 1):
        mask = mask or rec.get("F_MASK") or ""
        page_path = _page_file(path, rec.get("F_FILES"))
        page_name = (rec.get("F_PAGES") or "Page%d" % n).strip()
        page_fields = idf_fields(read_dbf(page_path)) if page_path else []
        if not page_path:
            missing.append(rec.get("F_FILES") or page_name)
        renamed = {}
        for f in page_fields:
            if f.is_input:
                name = f.name
                if name.lower() in used:
                    name = "P%d_%s" % (n, name)
                    renamed[f.name.lower()] = name
                    f.name = name
                used.add(name.lower())
        if len(records) > 1:
            fields.append(Field("page", label=page_name))
        fields.extend(page_fields)
        for left, right in zip((rec.get("F_PAIR1") or "").splitlines(),
                               (rec.get("F_PAIR2") or "").splitlines()):
            page_var = re.sub(r"^\[[^\]]*\]", "", left).strip()
            mask_var = right.strip()
            if page_var and mask_var:
                mapping[mask_var] = "<%s>" % renamed.get(page_var.lower(), page_var)

    template = mask.replace("\r\n", "\n").replace("\r", "\n")
    for mask_var in sorted(mapping, key=len, reverse=True):
        template = re.sub(re.escape(mask_var), lambda m: mapping[mask_var], template, flags=re.I)

    name, domain = _paf_info(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    description = "Imported from PWCT 1.x (%s)" % os.path.basename(path)
    if missing:
        description += " - interaction page not found: " + ", ".join(missing)
    comp = Component(key or "imported/" + re.sub(r"\W", "_", stem.lower()), name or stem,
                     "Imported/" + (domain or "PWCT 1.x"), description, fields,
                     template.strip("\n") or "<PWCT:NEWSTEP> " + (name or stem), layout="flow")
    return comp
