import unittest

from pwct.engine.template import TemplateError, expand, substitute


def code(ops):
    return [arg for op, arg in ops if op == "code"]


class TemplateTests(unittest.TestCase):
    def test_substitute_is_case_insensitive_and_keeps_unknown(self):
        self.assertEqual(substitute("<Name> < <other>", {"name": "x"}), "x < <other>")

    def test_filters(self):
        values = {"v": "my var", "s": "Hi"}
        self.assertEqual(substitute("<v|ident>", values), "my_var")
        self.assertEqual(substitute("<s|repr>", values), "'Hi'")
        self.assertEqual(substitute("<s|space|repr>", values), "'Hi '")
        with self.assertRaises(TemplateError):
            substitute("<s|nothing>", values)

    def test_if_else(self):
        tpl = "<PWCT:IF> <k> == A\na\n<PWCT:ELSE>\nb\n<PWCT:ENDIF>"
        self.assertEqual(code(expand(tpl, {"k": "A"})), ["a"])
        self.assertEqual(code(expand(tpl, {"k": "B"})), ["b"])

    def test_nested_if_in_false_block(self):
        tpl = "<PWCT:IF> <a>\n<PWCT:IF> <b>\nx\n<PWCT:ELSE>\ny\n<PWCT:ENDIF>\n<PWCT:ENDIF>"
        self.assertEqual(code(expand(tpl, {"a": "0", "b": "0"})), [])
        self.assertEqual(code(expand(tpl, {"a": "1", "b": "0"})), ["y"])

    def test_condition_value_with_operator_inside(self):
        tpl = "<PWCT:IF> <cond>\nif <cond>:\n<PWCT:ENDIF>"
        self.assertEqual(code(expand(tpl, {"cond": "x == 1"})), ["if x == 1:"])

    def test_original_rpwi_test_blocks(self):
        # the syntax used by the transporter files of the original PWCT
        tpl = "\n".join([
            "<RPWI:VALUE> 1", "<RPWI:POSITIVE>",
            "<RPWI:TEST> <cb>", "yes", "<RPWI:ENDTEST>",
            "<RPWI:NEGATIVE>",
            "<RPWI:TEST> <cb>", "no", "<RPWI:ENDTEST>"])
        self.assertEqual(code(expand(tpl, {"cb": "1"})), ["yes"])
        self.assertEqual(code(expand(tpl, {"cb": "0"})), ["no"])

    def test_foreach(self):
        tpl = "<PWCT:FOREACH> a in <attrs>\nself.<a|name> = <a|name>\n<PWCT:ENDFOREACH>"
        self.assertEqual(code(expand(tpl, {"attrs": "x, y=2"})), ["self.x = x", "self.y = y"])

    def test_multiline_value_keeps_indentation(self):
        self.assertEqual(code(expand("    <body>", {"body": "a\nb"})), ["    a", "    b"])

    def test_structural_ops(self):
        ops = expand("<PWCT:NEWSTEP> Step <n>\n<PWCT:PUTMARK> 2\n<PWCT:SETMARK> 2", {"n": "1"})
        self.assertEqual(ops, [("newstep", "Step 1"), ("putmark", "2"), ("setmark", "2")])

    def test_errors(self):
        for tpl in ["<PWCT:IF> 1\nx", "<PWCT:ENDIF>", "<PWCT:ELSE>", "<PWCT:WHAT>",
                    "<PWCT:FOREACH> a in b\nx"]:
            with self.assertRaises(TemplateError, msg=tpl):
                expand(tpl, {})


if __name__ == "__main__":
    unittest.main()
