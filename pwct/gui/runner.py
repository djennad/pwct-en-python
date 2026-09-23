"""Run the generated program in a separate Python process."""

import os
import queue
import re
import subprocess
import sys
import tempfile
import threading

TRACE_RE = re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+)')


def error_line(output, path):
    """The last line of ``path`` mentioned in a traceback, or ``None``."""
    line = None
    for match in TRACE_RE.finditer(output):
        if os.path.normcase(match.group("file")) == os.path.normcase(path or ""):
            line = int(match.group("line"))
    return line


class Runner:
    """Start a program and collect its output in a queue that the GUI reads
    with :meth:`poll`.  Lines typed by the user are sent with :meth:`send`."""

    def __init__(self):
        self.process = None
        self.path = None
        self.output = queue.Queue()
        self.last_error_line = None

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self, source, workdir=None):
        self.stop()
        fd, self.path = tempfile.mkstemp(prefix="pwct_", suffix=".py")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(source)
        self.last_error_line = None
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self.process = subprocess.Popen(
            [sys.executable, "-u", self.path], cwd=workdir or os.getcwd(),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=env, bufsize=0)
        self.output = queue.Queue()
        threading.Thread(target=self._read, args=(self.process, self.output, self.path),
                         daemon=True).start()

    def _read(self, process, events, path):
        stream = process.stdout
        tail = ""
        while True:
            try:
                data = os.read(stream.fileno(), 4096)
            except OSError:
                data = b""
            if not data:
                break
            text = data.decode("utf-8", errors="replace")
            tail = (tail + text)[-20000:]
            events.put(("out", text))
        code = process.wait()
        for pipe in (process.stdout, process.stdin):
            try:
                pipe.close()
            except OSError:
                pass
        if code:
            self.last_error_line = error_line(tail, path)
        events.put(("exit", code))

    def poll(self):
        """Return the pending ``(kind, data)`` events."""
        events = []
        while True:
            try:
                events.append(self.output.get_nowait())
            except queue.Empty:
                return events

    def send(self, line):
        if self.running:
            try:
                self.process.stdin.write((line + "\n").encode("utf-8"))
                self.process.stdin.flush()
            except OSError:
                pass

    def stop(self):
        if self.running:
            self.process.kill()
        self.process = None

    def cleanup(self):
        self.stop()
        if self.path and os.path.exists(self.path):
            try:
                os.remove(self.path)
            except OSError:
                pass
