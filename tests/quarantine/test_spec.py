from __future__ import annotations

from types import SimpleNamespace

from bench.quarantine import ParsesCheck, PythonCheck, QuarantineSpec, infer_spec
from bench.quarantine.checks import HttpServesCheck


def art(kind, value, **meta):
    return SimpleNamespace(kind=kind, value=value, meta=meta)


def test_infer_http_check_for_url_plus_html():
    result = SimpleNamespace(artifacts=[art("url", "https://x-8000.preview.getsolari.com")])
    spec = infer_spec(result, files={"index.html": "<h1>Kobo</h1>"})
    kinds = [type(c).__name__ for c in spec.checks]
    assert "HttpServesCheck" in kinds
    http = next(c for c in spec.checks if isinstance(c, HttpServesCheck))
    assert http.port == 8000


def test_infer_python_and_parse_checks():
    result = SimpleNamespace(artifacts=[])
    spec = infer_spec(result, files={"pull.py": "print(1)", "out.json": "{}", "rows.csv": "a,b"})
    names = {type(c).__name__ for c in spec.checks}
    assert {"PythonCheck", "ParsesCheck"} <= names


def test_infer_adds_pip_setup_when_requirements_present():
    spec = infer_spec(SimpleNamespace(artifacts=[]), files={"requirements.txt": "httpx\n", "app.py": "x"})
    assert ["pip", "install", "-q", "-r", "requirements.txt"] in spec.setup


def test_infer_pulls_file_contents_from_artifact_meta():
    result = SimpleNamespace(artifacts=[art("file", "report.json", content='{"ok": true}')])
    spec = infer_spec(result)
    assert spec.files["report.json"] == '{"ok": true}'
    assert any(isinstance(c, ParsesCheck) for c in spec.checks)


def test_infer_falls_back_to_file_presence_check():
    spec = infer_spec(SimpleNamespace(artifacts=[]), files={"notes.md": "# hi"})
    assert len(spec.checks) == 1 and spec.checks[0].__class__.__name__ == "FileCheck"


def test_spec_from_dict_round_trip():
    spec = QuarantineSpec.from_dict({
        "files": {"a.py": "print(1)"},
        "setup": [["pip", "install", "ruff"]],
        "checks": [{"type": "python", "name": "runs", "code": "import a"},
                   {"type": "command", "name": "lint", "cmd": "ruff", "args": ["check", "."]}],
        "workdir": "/app",
    })
    assert spec.workdir == "/app"
    assert isinstance(spec.checks[0], PythonCheck)
    assert spec.setup == [["pip", "install", "ruff"]]


def test_infer_pulls_binary_content_and_adds_existence_check():
    import base64

    raw = b"\x89PNG-fake-bytes"
    result = SimpleNamespace(artifacts=[art("image", "icon.png", content_b64=base64.b64encode(raw).decode())])
    spec = infer_spec(result)
    assert spec.binary_files == {"icon.png": raw}
    names = [type(c).__name__ for c in spec.checks]
    assert "CommandCheck" in names
    cc = next(c for c in spec.checks if type(c).__name__ == "CommandCheck")
    assert "icon.png" in cc.name and str(len(raw)) in cc.name


def test_infer_binary_only_result_does_not_fail_closed():
    import base64

    result = SimpleNamespace(artifacts=[art("file", "report.pdf", content_b64=base64.b64encode(b"%PDF-x").decode())])
    spec = infer_spec(result)
    assert len(spec.checks) == 1   # existence check, not the "nothing to verify" dead end


def test_spec_from_dict_round_trips_binary_files():
    import base64

    spec = QuarantineSpec.from_dict({"binary_files_b64": {"a.bin": base64.b64encode(b"xyz").decode()}})
    assert spec.binary_files == {"a.bin": b"xyz"}
