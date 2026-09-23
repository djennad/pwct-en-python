"""Component files, installing components and importing PWCT 1.x
components (no GUI needed)."""

import os
import shutil
import tempfile
import unittest

from pwct.engine import Library, Project, generate
from pwct.engine.components import Component, Field, matching, parse_component
from pwct.engine.legacy import import_trf, isf_fields, read_dbf
from pwct.engine.template import expand

from foxpro import make_component


class ComponentFileTests(unittest.TestCase):
    def test_every_component_survives_save_and_load(self):
        for comp in Library.default():
            with self.subTest(comp.key):
                again = parse_component(comp.to_text(), comp.key)
                self.assertEqual(again.to_text(), comp.to_text())
                self.assertEqual(again.default_values(), comp.default_values())

    def test_new_kinds_and_layout(self):
        comp = Component("t/x", "X", "Tests", "", [
            Field("page", label="First"), Field("small", "a", "A", "1"), Field("enter"),
            Field("memo", "m", "M", "line1\nline2"), Field("listindex", "n", "N", options=["x", "y"]),
            Field("check", "c", "C", "1", required=True)], "<PWCT:NEWSTEP> <a>", layout="flow")
        again = parse_component(comp.to_text(), comp.key)
        self.assertEqual(again.layout, "flow")
        self.assertEqual([f.kind for f in again.fields], ["page", "small", "enter", "memo", "listindex", "check"])
        self.assertEqual(again.default_values(), {"a": "1", "m": "line1\nline2", "n": "1", "c": "1"})

    def test_matching(self):
        comp = Component("t/x", "X", "T", "", [Field("text", "a"), Field("text", "b")],
                         "<PWCT:NEWVAR> tmp\n<PWCT:SETVARVALUE> <a>\n<PWCT:NEWSTEP> <tmp> <zz>")
        self.assertEqual(matching(comp), [("a", "a", "OK"), ("b", "", "not used in the code mask"),
                                          ("", "tmp", "template variable"), ("", "zz", "no page variable")])


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.old = os.environ.get("PWCT_HOME")
        os.environ["PWCT_HOME"] = self.home

    def tearDown(self):
        if self.old is None:
            os.environ.pop("PWCT_HOME", None)
        else:
            os.environ["PWCT_HOME"] = self.old
        shutil.rmtree(self.home)

    def test_install_and_uninstall(self):
        lib = Library.default()
        comp = Component("my/hello", "Hello", "My Components", "", [Field("text", "who", "Who", "you")],
                         "<PWCT:NEWSTEP> Hello <who>\nprint('Hello', <who|repr>)")
        path = lib.install(comp)
        self.assertTrue(path.startswith(self.home))
        again = Library.default()
        self.assertIn("my/hello", again)
        self.assertFalse(again["my/hello"].builtin)
        p = Project()
        p.apply(again["my/hello"], {"who": "PWCT"})
        self.assertIn("print('Hello', 'PWCT')", generate(p)[0])
        again.uninstall("my/hello")
        self.assertNotIn("my/hello", Library.default())

    def test_installed_component_replaces_builtin_until_uninstalled(self):
        lib = Library.default()
        comp = parse_component(lib["console/print"].to_text(), "console/print")
        comp.template = "<PWCT:NEWSTEP> Say <msg>\nprint('>>', <msg|repr>)"
        lib.install(comp)
        lib = Library.default()
        self.assertFalse(lib["console/print"].builtin)
        lib.uninstall("console/print")
        self.assertTrue(lib["console/print"].builtin)
        with self.assertRaises(ValueError):
            lib.uninstall("console/print")

    def test_bad_key(self):
        comp = Component("../evil", "X", "T", "", [], "<PWCT:NEWSTEP> x")
        with self.assertRaises(ValueError):
            Library.default().install(comp)


class TemplateVariableTests(unittest.TestCase):
    def test_newvar_setvarvalue(self):
        tpl = "\n".join(["<RPWI:NEWVAR> T_NAME", "<RPWI:VALUE> 1", "<RPWI:POSITIVE>",
                         "<RPWI:TEST> <cb>", "<RPWI:SETVARVALUE> NAME <nm>", "<RPWI:ENDTEST>",
                         "<RPWI:REPLACEVARSWITHVALUES>", "<*> comment", "item <T_NAME>"])
        self.assertEqual(expand(tpl, {"cb": "1", "nm": "x"}), [("code", "item NAME x")])
        self.assertEqual(expand(tpl, {"cb": "0", "nm": "x"}), [("code", "item")])


class LegacyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.trf = make_component(self.folder)

    def tearDown(self):
        shutil.rmtree(self.folder)

    def test_read_dbf(self):
        recs = read_dbf(self.trf)
        self.assertEqual(len(recs), 1)
        self.assertTrue(recs[0]["F_MASK"].startswith("<RPWI:VALUE> 1"))
        idf = read_dbf(os.path.join(self.folder, "IDF", "IDF7.IDF"))
        self.assertEqual(idf[-1]["O_OPTIONS"], "Left\r\nCenter\r\nRight")
        self.assertEqual(idf[1]["O_BCOLOR"], 7685727)

    def test_import_trf(self):
        comp = import_trf(self.trf)
        self.assertEqual(comp.name, "Label")
        self.assertEqual(comp.category, "Imported/User Interface/Controls")
        self.assertEqual(comp.layout, "flow")
        self.assertEqual([(f.kind, f.name, f.label) for f in comp.fields], [
            ("title", "", "Define New Label"), ("small", "D_TB_Row", "Row"),
            ("text", "D_TB_Caption", "Caption"), ("enter", "", ""), ("check", "D_CB_Bold", "Bold"),
            ("enter", "", ""), ("listindex", "D_LB_Align", "Align")])
        self.assertEqual(comp.fields[-1].options, ["Left", "Center", "Right"])
        self.assertIn("@ <D_TB_Row> LABEL <D_TB_Caption>", comp.template)
        p = Project()
        p.apply(comp, {"D_TB_Row": "5", "D_TB_Caption": "Hi", "D_CB_Bold": "1", "D_LB_Align": "2"})
        self.assertEqual(p.root.children[0].title, "Label Hi")
        self.assertEqual(p.root.children[0].code, ["@ 5 LABEL Hi", "BOLD", "ALIGN 2"])
        # the imported component can be saved as a .pwc file
        again = parse_component(comp.to_text(), comp.key)
        self.assertEqual(again.to_text(), comp.to_text())

    def test_isf(self):
        fields = isf_fields("TITLE Define New Image\nSMALLGET Top\nENTER\nLARGEGET Name\n"
                            "CHECKBOX ID\nCHECKBOXALONE Stretch\nLISTBOX Kind")
        self.assertEqual([(f.kind, f.name) for f in fields], [
            ("title", ""), ("small", "D_TB_Top"), ("enter", ""), ("text", "D_TB_Name"),
            ("check", "D_CB_ID"), ("text", "D_TB_ID"), ("check", "D_CB_Stretch"),
            ("listindex", "D_LB_Kind")])


if __name__ == "__main__":
    unittest.main()
