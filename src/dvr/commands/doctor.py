"""`dvr doctor` — environment diagnostics."""
from __future__ import annotations

import os
import platform as platform_mod
import sys
from typing import Any, Optional

import typer

from .. import __version__
from ..bootstrap import (
    BridgePaths,
    MIN_RESOLVE_MAJOR,
    discover_paths,
    inject_sys_path,
    parse_version,
)
from ..errors import DvrError
from ..output import OutputFormat, emit, resolve_format

app = typer.Typer(help="Diagnose the DaVinci Resolve bridge environment.")


def build_report(
    paths: Optional[BridgePaths] = None,
    *,
    importer: Optional[Any] = None,
) -> dict[str, Any]:
    """Pure function — used by both `dvr doctor` and unit tests.

    `importer` lets tests inject a fake DaVinciResolveScript module to avoid the real import.
    """
    paths = paths or discover_paths()
    issues: list[dict[str, str]] = []
    bridge_status = "module_not_found"
    version_str: Optional[str] = None
    edition: Optional[str] = None
    resolve_running = False

    if paths.module_path is None:
        issues.append(
            {
                "code": "module_not_found",
                "message": f"DaVinciResolveScript.py not found under {paths.api_dir}/Modules",
                "hint": "Install DaVinci Resolve 18+ or set RESOLVE_SCRIPT_API to the Scripting folder.",
            }
        )
    elif paths.lib_path is None or not paths.lib_path.exists():
        issues.append(
            {
                "code": "lib_not_found",
                "message": f"fusionscript library missing at {paths.lib_path}",
                "hint": "Verify DaVinci Resolve install or set RESOLVE_SCRIPT_LIB.",
            }
        )
    else:
        inject_sys_path(paths)
        try:
            if importer is not None:
                dvr_script = importer()
            else:
                import DaVinciResolveScript as dvr_script  # type: ignore[import-not-found]
            resolve = dvr_script.scriptapp("Resolve")
            if resolve is None:
                bridge_status = "connect_failed"
                issues.append(
                    {
                        "code": "resolve_not_running",
                        "message": "DaVinciResolveScript loaded but scriptapp('Resolve') returned None.",
                        "hint": "Launch DaVinci Resolve and enable Preferences → System → External scripting using = Local.",
                    }
                )
            else:
                version_str = resolve.GetVersionString() or None
                product = (resolve.GetProductName() or "").lower()
                edition = "Studio" if "studio" in product else "Free"
                resolve_running = True
                major = parse_version(version_str or "")[:1]
                if major and major[0] < MIN_RESOLVE_MAJOR:
                    bridge_status = "version_unsupported"
                    issues.append(
                        {
                            "code": "version_unsupported",
                            "message": f"Detected Resolve {version_str}; minimum supported is {MIN_RESOLVE_MAJOR}.",
                            "hint": f"Upgrade to DaVinci Resolve {MIN_RESOLVE_MAJOR}+.",
                        }
                    )
                else:
                    bridge_status = "ok"
        except ImportError as exc:
            issues.append(
                {
                    "code": "import_failed",
                    "message": f"Cannot import DaVinciResolveScript: {exc}",
                    "hint": "Check that RESOLVE_SCRIPT_API points to the Scripting folder.",
                }
            )
        except Exception as exc:  # noqa: BLE001 — DVR may raise bare Exception
            bridge_status = "connect_failed"
            issues.append(
                {
                    "code": "connect_failed",
                    "message": f"Bridge connect failed: {exc}",
                    "hint": "Run DaVinci Resolve and retry.",
                }
            )

    return {
        "resolveRunning": resolve_running,
        "version": version_str,
        "edition": edition,
        "apiPath": str(paths.api_dir) if paths.api_dir else None,
        "libPath": str(paths.lib_path) if paths.lib_path else None,
        "bridgeStatus": bridge_status,
        "cliVersion": __version__,
        "platform": platform_mod.platform(),
        "issues": issues,
    }


@app.callback(invoke_without_command=True)
def doctor(
    fmt: Optional[str] = typer.Option(None, "--format", "-f", help="table | json | yaml"),
) -> None:
    report = build_report()
    output_fmt = resolve_format(fmt)
    if output_fmt is OutputFormat.TABLE:
        # custom table layout: header summary + issues table
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        console = Console()
        summary = (
            f"[bold]CLI[/bold] {report['cliVersion']}   "
            f"[bold]platform[/bold] {report['platform']}\n"
            f"[bold]resolveRunning[/bold] {report['resolveRunning']}   "
            f"[bold]bridgeStatus[/bold] {report['bridgeStatus']}\n"
            f"[bold]version[/bold] {report.get('version') or '-'}   "
            f"[bold]edition[/bold] {report.get('edition') or '-'}\n"
            f"[bold]apiPath[/bold] {report.get('apiPath') or '-'}\n"
            f"[bold]libPath[/bold] {report.get('libPath') or '-'}"
        )
        console.print(Panel(summary, title="dvr doctor"))
        if report["issues"]:
            issues_t = Table(title="Issues", show_header=True, header_style="bold red")
            issues_t.add_column("code")
            issues_t.add_column("message")
            issues_t.add_column("hint")
            for it in report["issues"]:
                issues_t.add_row(it["code"], it["message"], it.get("hint", ""))
            console.print(issues_t)
        else:
            console.print("[green]All checks passed.[/green]")
    else:
        emit(report, output_fmt)

    # Exit non-zero if bridge isn't ok, so CI can gate on it.
    if report["bridgeStatus"] != "ok":
        raise typer.Exit(code=2)
