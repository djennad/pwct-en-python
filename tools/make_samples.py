"""Build the sample projects in pwct/samples using the engine API
(the same operations the GUI performs)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pwct.engine import Library, Project  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pwct", "samples")
lib = Library.default()


def add(project, key, parent=None, **values):
    return project.apply(lib[key], values, parent or project.root)


def after(step):
    """The step generated right after ``step`` (for example the Else of an If)."""
    return step.parent.children[step.index() + 1]


def hello_world():
    p = Project("Hello World")
    add(p, "other/comment", text="My first program made without coding")
    add(p, "console/print", msg="Hello, World!")
    add(p, "console/input", var="name", prompt="What is your name?")
    add(p, "console/print", msg='"Welcome, " + name + "!"', kind="Expression")
    return p


def guess_number():
    p = Project("Guess the Number")
    add(p, "console/print", msg="I am thinking of a number between 1 and 100")
    add(p, "math/random", var="secret", low="1", high="100")
    add(p, "variables/define", var="tries", type="Number", value="0")
    loop = add(p, "control/while", cond="True")
    add(p, "console/input", loop, var="guess", prompt="Your guess:", type="Integer")
    add(p, "variables/increment", loop, var="tries", step="1")
    cond = add(p, "control/if", loop, cond="guess < secret")
    add(p, "console/print", cond, msg="Too small!")
    cond2 = p.apply(lib["control/elif"], {"cond": "guess > secret"}, loop, cond.index() + 1)
    add(p, "console/print", cond2, msg="Too big!")
    other = p.apply(lib["control/else"], {}, loop, cond2.index() + 1)
    add(p, "console/print", other, msg='"Correct! You needed", tries, "tries"', kind="Expression")
    add(p, "control/break", other)
    return p


def factorial():
    p = Project("Factorial")
    func = add(p, "functions/define", name="factorial", params="n", doc="Return n! (recursive)")
    cond = add(p, "control/if", func, cond="n <= 1", **{"else": "1"})
    add(p, "functions/return", cond, value="1")
    add(p, "functions/return", after(cond), value="n * factorial(n - 1)")
    main = add(p, "functions/main")
    loop = add(p, "control/for_range", main, var="i", start="1", end="10")
    add(p, "console/print_values", loop, label="", values='f"{i}! =", factorial(i)')
    return p


def gui_counter():
    p = Project("GUI Counter")
    add(p, "variables/define", var="count", type="Number", value="0")
    win = add(p, "gui/window", var="win", title="Counter", width="300", height="160")
    controls = win.children[0]
    add(p, "gui/label", controls, var="lbl", text="Clicks: 0", font="16", x="90", y="20")
    button = add(p, "gui/button", controls, var="btn", text="Click Me", x="110", y="80")
    click = button.children[0]
    add(p, "other/code", click, title="Use the global counter", code="global count")
    add(p, "variables/increment", click, var="count", step="1")
    add(p, "gui/set_text", click, var="lbl", value='"Clicks: " + str(count)')
    return p


def shapes():
    p = Project("Classes and Objects")
    add(p, "modules/import", module="math")
    cls = add(p, "classes/class", name="Circle", attrs="radius")
    area = add(p, "classes/method", cls, name="area")
    add(p, "functions/return", area, value="math.pi * self.radius ** 2")
    cls2 = add(p, "classes/class", name="Rectangle", attrs="width, height")
    area2 = add(p, "classes/method", cls2, name="area")
    add(p, "functions/return", area2, value="self.width * self.height")
    add(p, "variables/define", var="shapes", type="List", value="Circle(1), Circle(2.5), Rectangle(3, 4)")
    loop = add(p, "control/for_each", var="shape", items="shapes")
    add(p, "console/print_values", loop, label="",
        values='type(shape).__name__, "area =", round(shape.area(), 2)')
    return p


SAMPLES = {"hello_world": hello_world, "guess_number": guess_number, "factorial": factorial,
           "gui_counter": gui_counter, "classes_objects": shapes}

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, build in SAMPLES.items():
        path = os.path.join(OUT, name + ".pwct")
        build().save(path)
        print("written", path)
