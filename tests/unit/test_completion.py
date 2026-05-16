"""`dvr completion install` — auto-detect shell + wrap typer's installer."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from dvr.commands import completion as comp
from dvr.errors import ApiCallFailed, ValidationError


def _fake_run_success(_args, capture_output: bool = True, text: bool = True):
    class _R:
        returncode = 0
        stdout = "Completion installed at /Users/x/.zshrc"
        stderr = ""
    return _R()


def _fake_run_failure(_args, capture_output: bool = True, text: bool = True):
    class _R:
        returncode = 2
        stdout = ""
        stderr = "shell not supported"
    return _R()


# ---------- detect_shell ----------

@pytest.mark.parametrize("shell_path,expected", [
    ("/bin/zsh", "zsh"),
    ("/usr/bin/bash", "bash"),
    ("/opt/homebrew/bin/fish", "fish"),
    ("/bin/sh", None),
    ("", None),
])
def test_detect_shell(monkeypatch, shell_path: str, expected) -> None:
    monkeypatch.setenv("SHELL", shell_path)
    assert comp.detect_shell() == expected


# ---------- install_completion happy paths ----------

def test_install_explicit_shell(monkeypatch) -> None:
    monkeypatch.setenv("SHELL", "")
    with patch("dvr.commands.completion.subprocess.run", _fake_run_success), \
         patch("dvr.commands.completion._dvr_binary", lambda: "/fake/dvr"):
        out = comp.install_completion(shell="zsh")
    assert out["ok"] is True
    assert out["shell"] == "zsh"
    assert "Completion installed" in out["message"]
    assert "exec zsh" in out["next_step"]


def test_install_auto_detect_from_shell_env(monkeypatch) -> None:
    monkeypatch.setenv("SHELL", "/bin/bash")
    with patch("dvr.commands.completion.subprocess.run", _fake_run_success), \
         patch("dvr.commands.completion._dvr_binary", lambda: "/fake/dvr"):
        out = comp.install_completion()
    assert out["shell"] == "bash"


# ---------- install_completion failure modes ----------

def test_install_raises_when_shell_unknown(monkeypatch) -> None:
    monkeypatch.setenv("SHELL", "/bin/csh")
    with pytest.raises(ValidationError) as exc:
        comp.install_completion()
    assert "auto-detect" in str(exc.value)
    assert exc.value.hint is not None and "--shell" in exc.value.hint


def test_install_raises_when_explicit_shell_unsupported() -> None:
    with pytest.raises(ValidationError) as exc:
        comp.install_completion(shell="csh")
    assert "unsupported shell" in str(exc.value)


def test_install_raises_when_subprocess_fails(monkeypatch) -> None:
    monkeypatch.setenv("SHELL", "/bin/zsh")
    with patch("dvr.commands.completion.subprocess.run", _fake_run_failure), \
         patch("dvr.commands.completion._dvr_binary", lambda: "/fake/dvr"):
        with pytest.raises(ApiCallFailed) as exc:
            comp.install_completion()
    assert exc.value.hint is not None and "--show-completion" in exc.value.hint
