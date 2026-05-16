"""Root Typer app + global flags + DvrError → structured exit handler."""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

import typer

from . import __version__
from .commands import completion as completion_cmd
from .commands import doctor as doctor_cmd
from .commands import install_wi as install_wi_cmd
from .commands import mcp_cmd
from .commands import media as media_cmd
from .commands import project as project_cmd
from .commands import render as render_cmd
from .commands import timeline as timeline_cmd
from .errors import DvrError

app = typer.Typer(
    name="dvr",
    help="DaVinci Resolve CLI — project / media / render / timeline.",
    no_args_is_help=True,
    add_completion=True,
)

app.add_typer(doctor_cmd.app, name="doctor")
app.add_typer(project_cmd.app, name="project")
app.add_typer(media_cmd.app, name="media")
app.add_typer(render_cmd.app, name="render")
app.add_typer(timeline_cmd.app, name="timeline")
app.add_typer(mcp_cmd.app, name="mcp")
app.add_typer(install_wi_cmd.app, name="install-wi")
app.add_typer(completion_cmd.app, name="completion")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Global flags. Subcommands inherit no state — keep them composable."""
    return


def _print_error(err: DvrError) -> None:
    sys.stderr.write(json.dumps(err.to_dict(), ensure_ascii=False) + "\n")


def run() -> int:
    debug = os.environ.get("DVR_DEBUG") == "1"
    try:
        app()
        return 0
    except DvrError as err:
        if debug:
            import traceback
            traceback.print_exc(file=sys.stderr)
        _print_error(err)
        return err.exit_code
    except typer.Exit as e:
        return int(e.exit_code or 0)
    except SystemExit as e:
        code = e.code
        return int(code) if isinstance(code, int) else 0
    except Exception as exc:
        if debug:
            raise
        err = DvrError(
            error_code="internal_error",
            message=f"unexpected error: {exc}",
            hint="Set DVR_DEBUG=1 to see traceback.",
            exit_code=70,
        )
        _print_error(err)
        return err.exit_code


def main_entry() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main_entry()
