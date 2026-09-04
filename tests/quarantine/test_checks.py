from __future__ import annotations

from bench.quarantine import (
    CommandCheck,
    FileCheck,
    HttpServesCheck,
    ParsesCheck,
    PythonCheck,
    check_from_dict,
)
from bench.quarantine.checks import CheckContext
from tests.quarantine.conftest import FakeQBox

CTX = CheckContext(workdir="/workspace")


def test_command_check_pass_and_fail():
    box = FakeQBox(lambda c, a, j: (0, "hello world", "") if c == "echo" else (1, "", "nope"))
    assert CommandCheck("echo runs", "echo", ["hi"]).run(box, CTX).passed
    r = CommandCheck("bad", "false").run(box, CTX)
    assert not r.passed and "exit 1" in r.detail


def test_command_check_stdout_contains():
    box = FakeQBox(lambda c, a, j: (0, "the build succeeded", ""))
    assert CommandCheck("build", "make", stdout_contains="succeeded").run(box, CTX).passed
    assert not CommandCheck("build", "make", stdout_contains="FAILED").run(box, CTX).passed


def test_python_check_writes_and_runs():
    box = FakeQBox(lambda c, a, j: (0, "", "") if c == "python3" else (0, "", ""))
    r = PythonCheck("script imports", "import json").run(box, CTX)
    assert r.passed
    assert any(p.endswith(".py") for p in box.files)          # snippet was written
    assert box.execs[-1][0] == "python3"


def test_python_check_reports_stderr_on_failure():
    box = FakeQBox(lambda c, a, j: (1, "", "Traceback: ModuleNotFoundError: foo"))
    r = PythonCheck("imports foo", "import foo").run(box, CTX)
    assert not r.passed and "ModuleNotFoundError" in r.detail


def test_file_check():
    box = FakeQBox()
    box.files["/workspace/index.html"] = "<h1>Kobo</h1>"
    assert FileCheck("html exists", "index.html").run(box, CTX).passed
    assert FileCheck("has heading", "index.html", contains="Kobo").run(box, CTX).passed
    miss = FileCheck("has footer", "index.html", contains="Footer").run(box, CTX)
    assert not miss.passed and "missing" in miss.detail
    assert not FileCheck("absent", "nope.txt").run(box, CTX).passed


def test_parses_check():
    box = FakeQBox(lambda c, a, j: (0, "ok\n", "") if "json.load" in j else (1, "", "boom"))
    assert ParsesCheck("data parses", "data.json", "json").run(box, CTX).passed
    box2 = FakeQBox(lambda c, a, j: (1, "", "json.decoder.JSONDecodeError"))
    r = ParsesCheck("data parses", "data.json", "json").run(box2, CTX)
    assert not r.passed and "JSONDecodeError" in r.detail


def test_http_serves_check_pass():
    def on_exec(cmd, args, joined):
        if "_qpoll.py" in joined:
            return (0, "200\n<h1>Kobo</h1>\n", "")
        return (0, "", "")
    box = FakeQBox(on_exec)
    r = HttpServesCheck("serves", ["python3", "-m", "http.server", "8000"], 8000,
                        body_contains="Kobo").run(box, CTX)
    assert r.passed and "HTTP 200" in r.detail


def test_http_serves_check_timeout():
    def on_exec(cmd, args, joined):
        if "_qpoll.py" in joined:
            return (1, "000\nConnectionRefusedError\n", "")
        if "tail" in joined:
            return (0, "Traceback: SyntaxError", "")
        return (0, "", "")
    box = FakeQBox(on_exec)
    r = HttpServesCheck("serves", ["python3", "app.py"], 5000).run(box, CTX)
    assert not r.passed and "HTTP 000" in r.detail and "SyntaxError" in r.detail


def test_http_serves_check_body_mismatch():
    box = FakeQBox(lambda c, a, j: (0, "200\nwrong page\n", "") if "_qpoll" in j else (0, "", ""))
    r = HttpServesCheck("serves", ["python3", "-m", "http.server", "8000"], 8000,
                        body_contains="Kobo").run(box, CTX)
    assert not r.passed and "body missing" in r.detail


def test_check_from_dict():
    c = check_from_dict({"type": "command", "name": "t", "cmd": "pytest", "args": ["-q"]})
    assert isinstance(c, CommandCheck) and c.args == ["-q"]
    import pytest
    with pytest.raises(ValueError):
        check_from_dict({"type": "nonsense", "name": "x"})
