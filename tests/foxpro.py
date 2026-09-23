"""Write small Visual FoxPro tables (DBF + FPT) for the tests of the PWCT
1.x importer, so no file of the original PWCT is needed."""

import struct

BLOCK = 64


def write_table(path, fields, records, memo_path=None):
    """``fields``: ``[(name, type, length)]`` with types C, N, M;
    ``records``: list of dictionaries."""
    memos = bytearray()
    next_block = 512 // BLOCK

    def memo(text):
        nonlocal next_block
        data = text.encode("cp1256")
        block = next_block
        chunk = struct.pack(">II", 1, len(data)) + data
        chunk += b"\0" * (-len(chunk) % BLOCK)
        memos.extend(chunk)
        next_block += len(chunk) // BLOCK
        return block

    layout, offset = [], 1
    for name, ftype, length in fields:
        length = 4 if ftype == "M" else length
        layout.append((name, ftype, offset, length))
        offset += length
    record_len = offset
    header_len = 32 + 32 * len(fields) + 1 + 263
    out = bytearray(struct.pack("<BBBBIHH", 0x30, 124, 1, 1, len(records), header_len, record_len))
    out += b"\0" * 16 + bytes([0x02 if memo_path else 0x00, 0x7E]) + b"\0" * 2
    for name, ftype, off, length in layout:
        out += name.encode("ascii").ljust(11, b"\0") + ftype.encode("ascii")
        out += struct.pack("<IBB", off, length, 0) + b"\0" * 14
    out += b"\x0d" + b"\0" * 263
    for rec in records:
        row = bytearray(b" ")
        for name, ftype, off, length in layout:
            value = rec.get(name)
            if ftype == "M":
                row += struct.pack("<i", memo(value) if value else 0)
            elif ftype == "N":
                row += ("" if value is None else str(value)).rjust(length).encode("ascii")
            else:
                row += (value or "").encode("cp1256")[:length].ljust(length)
        out += row
    out += b"\x1a"
    with open(path, "wb") as fh:
        fh.write(out)
    if memo_path:
        head = struct.pack(">I", next_block) + b"\0\0" + struct.pack(">H", BLOCK)
        with open(memo_path, "wb") as fh:
            fh.write(head.ljust(512, b"\0") + bytes(memos))


IDF_FIELDS = [("RECTYPE", "N", 1), ("O_TOP", "N", 5), ("O_LEFT", "N", 5), ("O_WIDTH", "N", 5),
              ("O_HEIGHT", "N", 5), ("O_CAPTION", "C", 60), ("O_BCOLOR", "N", 10),
              ("O_FSIZE", "N", 3), ("O_TRANS", "N", 1), ("O_VAR", "C", 30), ("O_OPTIONS", "M", 4)]
TRF_FIELDS = [("F_PAGES", "C", 20), ("F_FILES", "C", 120), ("F_MASK", "M", 4),
              ("F_PAIR1", "M", 4), ("F_PAIR2", "M", 4)]
PAF_FIELDS = [("RECTYPE", "N", 1), ("REG1", "C", 40), ("REG2", "C", 40), ("REG3", "C", 120),
              ("REG4", "N", 3)]


def make_component(folder):
    """A PWCT 1.x component like the "Image" control: a TRF, its IDF page
    and a PAF components tree.  Returns the path of the TRF."""
    import os
    os.makedirs(os.path.join(folder, "TRF"))
    os.makedirs(os.path.join(folder, "IDF"))
    idf = [
        {"RECTYPE": 0, "O_TOP": 0},
        {"RECTYPE": 1, "O_TOP": 0, "O_LEFT": -8, "O_WIDTH": 1288, "O_CAPTION": "   Define New Label",
         "O_BCOLOR": 7685727, "O_FSIZE": 14},
        {"RECTYPE": 1, "O_TOP": 40, "O_LEFT": 10, "O_WIDTH": 150, "O_CAPTION": "Row", "O_FSIZE": 9},
        {"RECTYPE": 2, "O_TOP": 40, "O_LEFT": 130, "O_WIDTH": 70, "O_VAR": "D_TB_Row"},
        {"RECTYPE": 1, "O_TOP": 40, "O_LEFT": 230, "O_WIDTH": 150, "O_CAPTION": "Caption", "O_FSIZE": 9},
        {"RECTYPE": 2, "O_TOP": 40, "O_LEFT": 350, "O_WIDTH": 222, "O_VAR": "D_TB_Caption"},
        {"RECTYPE": 4, "O_TOP": 80, "O_LEFT": 10, "O_WIDTH": 101, "O_CAPTION": "Bold", "O_VAR": "D_CB_Bold"},
        {"RECTYPE": 1, "O_TOP": 120, "O_LEFT": 10, "O_WIDTH": 50, "O_CAPTION": "Align", "O_FSIZE": 9},
        {"RECTYPE": 3, "O_TOP": 120, "O_LEFT": 130, "O_WIDTH": 222, "O_VAR": "D_LB_Align",
         "O_TRANS": 0, "O_OPTIONS": "Left\r\nCenter\r\nRight"},
    ]
    write_table(os.path.join(folder, "IDF", "IDF7.IDF"), IDF_FIELDS, idf,
                os.path.join(folder, "IDF", "IDF7.FPT"))
    mask = ("<RPWI:VALUE> 1\r\n<RPWI:POSITIVE>\r\n<RPWI:NEWSTEP> Label <T_CAPTION>\r\n"
            "@ <T_ROW> LABEL <T_CAPTION>\r\n<RPWI:TEST> <T_BOLD>\r\nBOLD\r\n<RPWI:ENDTEST>\r\n"
            "<*> a comment of the original\r\nALIGN <T_ALIGN>")
    trf = [{"F_PAGES": "Page1", "F_FILES": "C:\\SSRPWI\\DOUBLES\\RPWI1\\IDF\\IDF7.IDF", "F_MASK": mask,
            "F_PAIR1": "[Page1] D_TB_Row\r\n[Page1] D_TB_Caption\r\n[Page1] D_CB_Bold\r\n[Page1] D_LB_Align",
            "F_PAIR2": "<T_ROW>\r\n<T_CAPTION>\r\n<T_BOLD>\r\n<T_ALIGN>"}]
    trf_path = os.path.join(folder, "TRF", "TRF7.TRF")
    write_table(trf_path, TRF_FIELDS, trf, os.path.join(folder, "TRF", "TRF7.FPT"))
    paf = [{"RECTYPE": 1, "REG1": "Test Language"},
           {"RECTYPE": 2, "REG1": "0_", "REG2": "48_", "REG3": "Test Language"},
           {"RECTYPE": 2, "REG1": "48_", "REG2": "49_", "REG3": "User Interface"},
           {"RECTYPE": 2, "REG1": "49_", "REG2": "53_", "REG3": "Controls"},
           {"RECTYPE": 3, "REG1": "        53_", "REG2": "Label", "REG3": "C:\\X\\TRF\\TRF7.TRF", "REG4": 2}]
    write_table(os.path.join(folder, "TEST.PAF"), PAF_FIELDS, paf)
    return trf_path
