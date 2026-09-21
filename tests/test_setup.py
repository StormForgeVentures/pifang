"""Setup / dependency guidance tests."""

from __future__ import annotations

import json
import subprocess
import sys

from pifang.core.setup_deps import setup_report
from pifang.domains.doc.engines import default_engine


def test_default_engine_is_fast() -> None:
    assert default_engine().name == "fast"


def test_setup_report_suggested() -> None:
    data = setup_report()
    assert data["ok"] is True
    assert data["default_doc_engine"] == "fast"
    assert "doc" in data["pip_extras"]
    assert "doc-odl" in data["pip_extras"]
    assert any(h["name"] == "ffmpeg" for h in data["system"])
    assert any(h["name"] == "java" and h.get("optional") for h in data["system"])


def test_setup_unknown_extra() -> None:
    data = setup_report(extras=["nope"])
    assert data["ok"] is False
    assert data["error_code"] == "UNKNOWN_EXTRA"


def test_setup_extras_dry_command() -> None:
    data = setup_report(extras=["doc", "transcribe"], install=False)
    assert data["ok"] is True
    assert data["install"]["dry_run"] is True
    assert "pifang[doc]" in " ".join(data["install"]["command"])


def test_setup_cli() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "pifang.cli.main", "--json", "setup", "--extras", "doc"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["default_doc_engine"] == "fast"


def test_install_pip_extras_timeout(monkeypatch) -> None:
    import subprocess as sp

    from pifang.core import setup_deps
    from pifang.errors import ProcessingError

    def _fake_run(*args, **kwargs):
        raise sp.TimeoutExpired(cmd=args[0] if args else "pip", timeout=0.01)

    monkeypatch.setattr(setup_deps.subprocess, "run", _fake_run)
    try:
        setup_deps.install_pip_extras(["doc"], timeout=0.01)
        raise AssertionError("expected ProcessingError")
    except ProcessingError as exc:
        assert exc.error_code == "SUBPROCESS_TIMEOUT"
        assert exc.exit_code == 3
