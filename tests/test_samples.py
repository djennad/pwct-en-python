import os
import subprocess
import sys
import unittest

from pwct.engine import Project, generate
from pwct.gui.runner import error_line

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "pwct", "samples")


def run_cli(*args, stdin=""):
    return subprocess.run([sys.executable, "-m", "pwct"] + list(args), cwd=ROOT, input=stdin,
                          capture_output=True, text=True, timeout=60)


class SampleTests(unittest.TestCase):
    def test_samples_compile(self):
        names = [n for n in os.listdir(SAMPLES) if n.endswith(".pwct")]
        self.assertGreaterEqual(len(names), 5)
        for name in names:
            with self.subTest(name):
                compile(generate(Project.load(os.path.join(SAMPLES, name)))[0], name, "exec")

    def test_run_hello_world(self):
        result = run_cli("run", os.path.join(SAMPLES, "hello_world.pwct"), stdin="Sara\n")
        self.assertIn("Welcome, Sara!", result.stdout)

    def test_run_factorial(self):
        result = run_cli("run", os.path.join(SAMPLES, "factorial.pwct"))
        self.assertIn("10! = 3628800", result.stdout)

    def test_build_writes_file(self):
        result = run_cli("build", os.path.join(SAMPLES, "factorial.pwct"))
        self.assertIn("def factorial(n):", result.stdout)

    def test_error_line(self):
        out = 'Traceback:\n  File "/tmp/a.py", line 3, in <module>\n  File "/lib/x.py", line 9\n'
        self.assertEqual(error_line(out, "/tmp/a.py"), 3)
        self.assertIsNone(error_line(out, "/tmp/b.py"))


if __name__ == "__main__":
    unittest.main()
