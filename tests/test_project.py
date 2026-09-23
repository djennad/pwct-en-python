import ast
import unittest

from pwct.engine import History, Library, Project, ProjectError, generate
from pwct.engine.components import parse_component

LIB = Library.default()


def body(project):
    return generate(project, header=False)[0]


def add(project, key, parent=None, index=None, **values):
    return project.apply(LIB[key], values, parent or project.root, index)


class ComponentTests(unittest.TestCase):
    def test_every_component_generates_valid_python(self):
        self.assertGreater(len(LIB), 40)
        for comp in LIB:
            with self.subTest(comp.key):
                project = Project()
                if comp.position == "after":      # Else / Else If follow an If
                    add(project, "control/if")
                project.apply(comp, {})
                # parse only: return / break are valid inside a function / loop
                ast.parse(body(project))

    def test_required_fields(self):
        with self.assertRaises(ProjectError):
            add(Project(), "control/if", cond="  ")

    def test_parse_component(self):
        comp = parse_component("[component]\nname: T\n[interaction]\ntext! a | A | 1\n"
                               "check b | B | 1\nlist c | C | | x, y\n[template]\n"
                               "<PWCT:NEWSTEP> T\nprint(<a>)", "t")
        self.assertEqual(comp.default_values(), {"a": "1", "b": "1", "c": "x"})
        self.assertTrue(comp.fields[0].required)


class ProjectTests(unittest.TestCase):
    def test_blocks_indent_children_and_get_pass(self):
        p = Project()
        loop = add(p, "control/for_range", var="i", start="1", end="3")
        self.assertEqual(body(p), "for i in range(1, 3 + 1):\n    pass\n")
        add(p, "console/print", loop, msg="i", kind="Expression")
        self.assertEqual(body(p), "for i in range(1, 3 + 1):\n    print(i)\n")

    def test_if_else_creates_two_steps(self):
        p = Project()
        first = add(p, "control/if", cond="x", **{"else": "1"})
        self.assertEqual([s.title for s in p.root.children], ["If x", "Else"])
        self.assertEqual(first.interaction, p.root.children[1].interaction)

    def test_marks_build_nested_steps(self):
        p = Project()
        win = add(p, "gui/window")
        self.assertEqual([c.title for c in win.children], ["Controls"])
        self.assertEqual(p.root.children[1].title, "Show window win")
        button = add(p, "gui/button", win.children[0])
        self.assertEqual([c.title for c in button.children], ["When btn is clicked", "Create button btn"])
        compile(generate(p)[0], "gui", "exec")

    def test_edit_keeps_user_steps(self):
        p = Project()
        loop = add(p, "control/while", cond="True")
        add(p, "console/print", loop, msg="inside")
        p.edit(loop.interaction, LIB["control/while"], {"cond": "n < 3"})
        self.assertEqual(body(p), "while n < 3:\n    print('inside')\n")

    def test_edit_removing_a_step_keeps_its_children(self):
        p = Project()
        cond = add(p, "control/if", cond="a", **{"else": "1"})
        other = p.root.children[1]
        add(p, "console/print", other, msg="b")
        p.edit(cond.interaction, LIB["control/if"], {"cond": "a", "else": "0"})
        self.assertEqual(body(p), "if a:\n    pass\nprint('b')\n")
        p.edit(cond.interaction, LIB["control/if"], {"cond": "a", "else": "1"})
        self.assertIn("else:", body(p))

    def test_insert_position(self):
        p = Project()
        loop = add(p, "control/while", cond="True")
        stmt = add(p, "console/print", loop)
        self.assertEqual(p.insert_position(loop), (loop, 1))
        self.assertEqual(p.insert_position(stmt), (loop, 1))
        self.assertEqual(p.insert_position(loop, "after"), (p.root, 1))
        self.assertEqual(p.insert_position(loop, "before"), (p.root, 0))

    def test_disabled_steps_become_comments(self):
        p = Project()
        loop = add(p, "control/while", cond="True")
        stmt = add(p, "console/print", loop, msg="x")
        p.set_disabled(stmt, True)
        self.assertEqual(body(p), "while True:\n    # print('x')\n    pass\n")

    def test_imports_are_collected_at_the_top(self):
        p = Project()
        add(p, "math/random")
        add(p, "math/random", var="m")
        add(p, "math/calculate")
        source = body(p)
        self.assertTrue(source.startswith("import random\nimport math\n\n"), source)
        self.assertEqual(source.count("import random"), 1)

    def test_owners_map_lines_to_steps(self):
        p = Project()
        step = add(p, "console/print")
        source, owners = generate(p)
        line = source.splitlines().index("print('Hello, World!')") + 1
        self.assertEqual(owners[line - 1], step.id)

    def test_move_indent_outdent_delete(self):
        p = Project()
        a = add(p, "control/while", cond="True")
        b = add(p, "console/print", msg="b")
        self.assertTrue(p.move(b, -1))
        self.assertEqual(p.root.children, [b, a])
        p.move(b, 1)
        self.assertTrue(p.indent(b))
        self.assertIs(b.parent, a)
        self.assertTrue(p.outdent(b))
        self.assertIs(b.parent, p.root)
        p.delete(a)
        self.assertEqual(list(p.interactions), [b.interaction])

    def test_copy_paste_gives_new_ids(self):
        p = Project()
        loop = add(p, "control/while", cond="True")
        add(p, "console/print", loop)
        clip = p.copy_steps(loop)
        copy = p.paste(clip, p.root)
        self.assertNotEqual(copy.interaction, loop.interaction)
        self.assertEqual(len({s.id for s in p.root.walk()}), 5)
        p.edit(copy.interaction, LIB["control/while"], {"cond": "False"})
        self.assertEqual(body(p).count("while True:"), 1)

    def test_save_load_and_undo(self):
        p = Project("Demo")
        add(p, "console/print")
        history = History()
        history.record(p)
        add(p, "console/print", msg="two")
        q = Project.from_json(p.to_json())
        self.assertEqual(generate(q), generate(p))
        self.assertGreater(q.next_id, max(int(s.id) for s in p.root.walk()))
        old = history.undo(p)
        self.assertNotIn("two", body(old))
        self.assertIn("two", body(history.redo(old)))


if __name__ == "__main__":
    unittest.main()
