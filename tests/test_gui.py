"""Drive the main window (skipped when Tkinter or a display is missing).
On a server run it with:  xvfb-run python -m unittest tests.test_gui"""

import os
import time
import unittest

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_TK = True
except Exception:   # no tkinter module or no display
    HAVE_TK = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(HAVE_TK, "Tkinter with a display is needed")
class GuiTests(unittest.TestCase):
    def setUp(self):
        from pwct.gui import app, interaction
        self.answers = []

        def fake_run(page):
            values = page.values()
            if self.answers:
                values.update(self.answers.pop(0))
            page.result = values
            page.destroy()
            return values

        self._old_run = interaction.InteractionPage.run
        interaction.InteractionPage.run = fake_run
        self.app = app.App(os.path.join(ROOT, "pwct", "samples", "hello_world.pwct"))
        self.app.update()

    def tearDown(self):
        from pwct.gui import interaction
        interaction.InteractionPage.run = self._old_run
        self.app.dirty = False
        self.app.quit_app()

    def wait(self, condition, seconds=10):
        end = time.time() + seconds
        while time.time() < end and not condition():
            self.app.update()
            time.sleep(0.02)

    def test_add_edit_undo(self):
        app = self.app
        app._reveal(app.project.root.id)
        self.answers.append({"cond": "True"})
        app.comp_tree.selection_set("control/while")
        app.use_component()
        loop = app.selected()
        self.assertEqual(loop.title, "While True")
        self.answers.append({"msg": "again"})
        app.comp_tree.selection_set("console/print")
        app.use_component()
        self.assertIn("while True:\n    print('again')", app.source)
        app._reveal(loop.id)
        self.answers.append({"cond": "False"})
        app.edit_step()
        self.assertIn("while False:\n    print('again')", app.source)
        app.undo()
        self.assertIn("while True:", app.source)
        app.redo()
        self.assertIn("while False:", app.source)

    def test_run_with_input_and_error(self):
        app = self.app
        app.project.apply(app.library["other/code"], {"code": "x = 1 / 0", "title": "Divide"})
        app.refresh()
        app.run_program()
        self.wait(lambda: "name?" in app.output.get("1.0", "end"))
        app.input_var.set("Ahmed")
        app.send_input()
        self.wait(lambda: "finished" in app.output.get("1.0", "end"))
        self.assertIn("Welcome, Ahmed!", app.output.get("1.0", "end"))
        self.assertEqual(app.selected().title, "Divide")


if __name__ == "__main__":
    unittest.main()
