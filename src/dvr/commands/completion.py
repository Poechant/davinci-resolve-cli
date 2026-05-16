"""`dvr completion install` — friendlier wrapper around Typer's built-in completion installer.

Typer ships `dvr --install-completion <shell>` already, but it's a global option
many users never discover, and it requires you to pass the shell name. This
subcommand auto-detects the shell from `$SHELL` and runs the same flow with a
clearer success message.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional

import typer

from ..errors import ApiCallFailed, ValidationError
from ..output import emit, resolve_format

app = typer.Typer(help="Shell completion installation.")

SUPPORTED_SHELLS = {"zsh", "bash", "fish"}


def detect_shell() -> Optional[str]:
    """Best-effort shell detection from $SHELL."""
    shell_path = os.environ.get("SHELL", "")
    name = os.path.basename(shell_path).lower()
    return name if name in SUPPORTED_SHELLS else None


def _dvr_binary() -> str:
    """Locate the on-disk `dvr` entrypoint to re-invoke for the completion install."""
    found = shutil.which("dvr")
    if found:
        return found
    if sys.argv and sys.argv[0]:
        return sys.argv[0]
    raise ApiCallFailed("locate dvr binary", "could not resolve own entrypoint path")


def install_completion(shell: Optional[str] = None) -> dict:
    """Install shell completion. Returns a structured result for `--format json`."""
    if shell is None:
        detected = detect_shell()
        if detected is None:
            raise ValidationError(
                f"cannot auto-detect shell from SHELL={os.environ.get('SHELL', '<unset>')!r}",
                hint=f"Pass --shell explicitly (one of: {', '.join(sorted(SUPPORTED_SHELLS))}).",
            )
        shell = detected
    if shell not in SUPPORTED_SHELLS:
        raise ValidationError(
            f"unsupported shell: {shell!r}",
            hint=f"Supported: {', '.join(sorted(SUPPORTED_SHELLS))}.",
        )

    dvr_bin = _dvr_binary()
    res = subprocess.run(
        [dvr_bin, "--install-completion", shell],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise ApiCallFailed(
            "dvr --install-completion",
            (res.stderr or f"exit code {res.returncode}").strip(),
            hint="If your shell isn't supported, run `dvr --show-completion <shell>` "
            "and paste the snippet into your shell rc manually.",
        )
    return {
        "ok": True,
        "shell": shell,
        "message": (res.stdout or "").strip() or f"Completion installed for {shell}.",
        "next_step": f"Open a new shell (or `exec {shell}`) to enable completion.",
    }


@app.command("install")
def cli_install(
    shell: Optional[str] = typer.Option(None, "--shell", "-s", help="zsh / bash / fish (auto-detect from $SHELL if omitted)"),
    fmt: Optional[str] = typer.Option(None, "--format", "-f"),
) -> None:
    """Install shell completion for the dvr command."""
    emit(install_completion(shell), resolve_format(fmt))
