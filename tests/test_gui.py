"""Drive the main window (skipped when Tkinter or a display is missing).
On a server run it with:  xvfb-run python -m unittest tests.test_gui"""

import os
import shutil
import tempfile
import time
import unittest

from foxpro import make_component

try:
    import tkinter
    tkinter.Tk().destroy()
    HAVE_TK = True
except Exception:   # no tkinter module or no display
    HAVE_TK = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_code(project):
    from pwct.engine import generate
    return generate(project)[0]


@unittest.skipUnless(HAVE_TK, "Tkinter with a display is needed")
class GuiTests(unittest.TestCase):
    def setUp(self):
        from pwct.gui import app, interaction
        self.home = tempfile.mkdtemp()
        self.old_home = os.environ.get("PWCT_HOME")
        os.environ["PWCT_HOME"] = self.home
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
        self.app.studio.dirty = False
        self.app.quit_app()
        if self.old_home is None:
            os.environ.pop("PWCT_HOME", None)
        else:
            os.environ["PWCT_HOME"] = self.old_home
        shutil.rmtree(self.home)

    def wait(self, condition, seconds=10):
        end = time.time() + seconds
        while time.time() < end and not condition():
            self.app.update()
            time.sleep(0.02)

    def test_add_edit_undo(self):
        app = self.app
        app._reveal(app.project.root.id)
        self.answers.append({"cond": "True"})
        app.add_component("control/while")
        loop = app.selected()
        self.assertEqual(loop.title, "While True")
        self.answers.append({"msg": "again"})
        app.add_component("console/print")
        self.assertIn("while True:\n    print('again')", app.source)
        app._reveal(loop.id)
        self.answers.append({"cond": "False"})
        app.edit_step()
        self.assertIn("while False:\n    print('again')", app.source)
        app.undo()
        self.assertIn("while True:", app.source)
        app.redo()
        self.assertIn("while False:", app.source)

    def test_components_browser(self):
        from pwct.gui.browser import ComponentBrowser
        app = self.app
        browser = ComponentBrowser(app, app.library, app.insert_mode, app.fonts, app.icons)
        browser.search_var.set("while")
        self.assertIn("control/while", browser.components.get_children())
        browser.search_var.set("")
        browser.select("gui/button")
        self.assertEqual(browser.domains.selection(), ("GUI (Tkinter)",))
        browser.ok()
        self.assertEqual(browser.result, "gui/button")

    def test_new_step_and_ignore(self):
        from tkinter import simpledialog
        app = self.app
        old = simpledialog.askstring
        simpledialog.askstring = lambda *a, **k: "My group"
        try:
            app._reveal(app.project.root.id)
            app.new_step()
        finally:
            simpledialog.askstring = old
        step = app.selected()
        self.assertEqual(step.title, "My group")
        self.assertIsNone(step.interaction)
        first = app.project.root.children[0]
        app._reveal(first.id)
        app.disabled_var.set(1)
        app._disabled_clicked()
        self.assertTrue(first.disabled)
        self.assertIn("# # My first program", app.source)

    def test_design_install_and_use_component(self):
        from tkinter import messagebox
        app = self.app
        app.show_panel("transporter")
        designer = app.transporter_designer
        designer.meta["key"][0].set("my/greet")
        designer.meta["name"][0].set("Greet")
        designer.meta["category"][0].set("My Components/Hello")
        designer.mask.delete("1.0", "end")
        designer.mask.insert("1.0", "<PWCT:NEWSTEP> Greet <msg>\nprint('Hi', <msg|repr>)")
        app.update()
        self.assertEqual(app.studio.component.template.splitlines()[1], "print('Hi', <msg|repr>)")

        inter = app.interaction_designer
        app.show_panel("interaction")
        inter.add_field("check")
        self.assertEqual([f.kind for f in app.studio.component.fields], ["title", "text", "check"])
        inter.list.selection_set("2")
        app.update()
        inter.name_var.set("loud")
        inter.label_var.set("Shout")
        self.assertEqual(app.studio.component.fields[2].name, "loud")
        inter.render_preview()
        self.assertIn("loud", inter.form.values())

        self.assertTrue(app.studio.install())
        self.assertIn("my/greet", app.library)
        self.assertTrue(os.path.exists(os.path.join(self.home, "components", "my", "greet.pwc")))
        project = designer.run_test(None)
        self.assertIn("print('Hi', 'Hello')", generate_code(project))

        app.show_goal_designer()
        app._reveal(app.project.root.id)
        self.answers.append({"msg": "PWCT"})
        app.add_component("my/greet")
        self.assertIn("print('Hi', 'PWCT')", app.source)

        old = messagebox.askyesno
        messagebox.askyesno = lambda *a, **k: True
        try:
            app.studio.uninstall()
        finally:
            messagebox.askyesno = old
        self.assertNotIn("my/greet", app.library)

    def test_import_pwct_component(self):
        app = self.app
        folder = tempfile.mkdtemp()
        try:
            app.studio.import_trf(make_component(folder))
        finally:
            shutil.rmtree(folder)
        comp = app.studio.component
        self.assertEqual(comp.name, "Label")
        self.assertEqual(len(app.interaction_designer.list.get_children()), len(comp.fields))
        from pwct.gui.interaction import InteractionForm
        form = InteractionForm(app, comp, fonts=app.fonts)
        values = form.values()
        self.assertEqual(values["D_LB_Align"], "1")
        self.assertEqual(values["D_CB_Bold"], "0")
        form.lists["D_LB_Align"][0].selection_clear(0, "end")
        form.lists["D_LB_Align"][0].selection_set(2)
        self.assertEqual(form.values()["D_LB_Align"], "3")
        form.destroy()
        app.studio.dirty = False

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
