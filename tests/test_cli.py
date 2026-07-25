"""Tests for the Click command-line interface."""

from __future__ import annotations

from click.testing import CliRunner

from aios import __version__
from aios.cli.main import cli


def test_version_command():
    result = CliRunner().invoke(cli, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_run_command_outputs_hello(examples_manifest):
    result = CliRunner().invoke(cli, ["run", str(examples_manifest)])
    assert result.exit_code == 0
    assert "Hello AIOS!" in result.output


def test_run_command_missing_manifest():
    result = CliRunner().invoke(cli, ["run", "definitely_missing.yaml"])
    assert result.exit_code != 0
