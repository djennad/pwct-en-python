"""Command line entry point.

    python -m pwct                       open the visual environment
    python -m pwct project.pwct          open a project
    python -m pwct build project.pwct    write the Python code (-o file.py)
    python -m pwct run project.pwct      generate and run the program
    python -m pwct components            list the available components
"""

import argparse
import os
import subprocess
import sys
import tempfile

from . import __version__
from .engine import Library, Project, generate


def cmd_build(args):
    source = generate(Project.load(args.project))[0]
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(source)
        print("Written", args.output)
    else:
        sys.stdout.write(source)
    return 0


def cmd_run(args):
    source = generate(Project.load(args.project))[0]
    fd, path = tempfile.mkstemp(prefix="pwct_", suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(source)
    try:
        return subprocess.call([sys.executable, path],
                               cwd=os.path.dirname(os.path.abspath(args.project)))
    finally:
        os.remove(path)


def cmd_components(args):
    for category, comps in Library.default().categories().items():
        print(category)
        for comp in comps:
            print("    %-28s %s" % (comp.key, comp.name))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    commands = {"build": cmd_build, "run": cmd_run, "components": cmd_components}
    if argv and argv[0] in commands:
        parser = argparse.ArgumentParser(prog="pwct")
        sub = parser.add_subparsers(dest="command")
        p = sub.add_parser("build", help="write the Python code of a project")
        p.add_argument("project")
        p.add_argument("-o", "--output")
        p = sub.add_parser("run", help="run a project")
        p.add_argument("project")
        sub.add_parser("components", help="list the components")
        args = parser.parse_args(argv)
        return commands[args.command](args)

    parser = argparse.ArgumentParser(prog="pwct", description="PWCT-Python visual programming")
    parser.add_argument("project", nargs="?", help="project file (.pwct) to open")
    parser.add_argument("--version", action="version", version="PWCT-Python " + __version__)
    args = parser.parse_args(argv)
    try:
        from .gui.app import main as gui_main
    except ImportError as exc:
        print("The GUI needs Tkinter (%s).\nOn Debian/Ubuntu: sudo apt install python3-tk" % exc)
        return 1
    gui_main(args.project)
    return 0


if __name__ == "__main__":
    sys.exit(main())
