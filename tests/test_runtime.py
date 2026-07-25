"""Tests for the runtime orchestration and lifecycle guarantees."""

from __future__ import annotations

from pathlib import Path

import pytest

import lifecycle_components as fixtures
from aios.exceptions import RuntimeExecutionError
from aios.runtime import Runtime


def _write_manifest(tmp_path: Path, module: str, class_name: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        f"version: 1\ncomponent:\n  module: {module}\n  class: {class_name}\n",
        encoding="utf-8",
    )
    return path


def test_run_executes_full_lifecycle_in_order(tmp_path):
    fixtures.LifecycleSpy.calls.clear()
    manifest = _write_manifest(tmp_path, "lifecycle_components", "LifecycleSpy")

    result = Runtime().run(manifest)

    assert result.success is True
    assert result.output == "spied"
    assert fixtures.LifecycleSpy.calls == ["initialize", "execute", "shutdown"]


def test_shutdown_runs_even_when_execute_fails(tmp_path):
    fixtures.FailingComponent.shutdown_called = False
    manifest = _write_manifest(tmp_path, "lifecycle_components", "FailingComponent")

    with pytest.raises(RuntimeExecutionError):
        Runtime().run(manifest)

    assert fixtures.FailingComponent.shutdown_called is True


def test_run_with_hello_manifest(examples_manifest):
    result = Runtime().run(examples_manifest)
    assert result.success is True
    assert result.output == "Hello AIOS!"


def test_run_accepts_str_path(examples_manifest):
    result = Runtime().run(str(examples_manifest))
    assert result.output == "Hello AIOS!"


def test_bad_return_type_raises(tmp_path):
    manifest = _write_manifest(tmp_path, "lifecycle_components", "BadReturnComponent")
    with pytest.raises(RuntimeExecutionError, match="ExecutionResult"):
        Runtime().run(manifest)


def test_shutdown_failure_after_success_raises(tmp_path):
    manifest = _write_manifest(tmp_path, "lifecycle_components", "ShutdownFailingComponent")
    with pytest.raises(RuntimeExecutionError, match="shutdown"):
        Runtime().run(manifest)


def test_shutdown_failure_does_not_mask_execute_error(tmp_path):
    manifest = _write_manifest(
        tmp_path, "lifecycle_components", "ExecuteAndShutdownFailingComponent"
    )
    with pytest.raises(RuntimeExecutionError, match="execute boom"):
        Runtime().run(manifest)
