"""Click-based command-line interface for the AIOS runtime.

Only ``version`` and ``run`` are implemented in this release. The command group
is structured so future commands (``init``, ``doctor``, ``validate``,
``plugins``, ``events``) can be added without restructuring.
"""

from __future__ import annotations

import logging
from pathlib import Path

import click
from rich.console import Console

from aios import __version__
from aios.exceptions import AIOSError
from aios.logger import configure_logging
from aios.runtime import Runtime

_console = Console()
_error_console = Console(stderr=True)


@click.group(help="AIOS — Artificial Intelligence Operating System runtime.")
def cli() -> None:
    """Root command group for the ``aios`` executable."""


@cli.command(name="version")
def version_command() -> None:
    """Print the installed AIOS version."""
    _console.print(f"AIOS {__version__}")


@cli.command(name="run")
@click.argument(
    "manifest",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("-v", "--verbose", count=True, help="Increase log verbosity (-v, -vv).")
def run_command(manifest: Path, verbose: int) -> None:
    """Run the component described by MANIFEST."""
    configure_logging(_verbosity_to_level(verbose))
    try:
        result = Runtime().run(manifest)
    except AIOSError as exc:
        _error_console.print(f"[bold red]Error:[/] {exc}")
        raise SystemExit(1) from exc

    if result.success:
        if result.output is not None:
            _console.print(result.output, highlight=False)
    else:
        _error_console.print(f"[bold red]Failed:[/] {result.error}")
        raise SystemExit(1)


def _verbosity_to_level(verbose: int) -> int:
    """Map a ``-v`` count to a :mod:`logging` level."""
    if verbose >= 2:
        return logging.DEBUG
    if verbose == 1:
        return logging.INFO
    return logging.WARNING


if __name__ == "__main__":  # pragma: no cover
    cli()
