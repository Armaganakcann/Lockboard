"""Tests for the reference MetricsPlugin."""

from __future__ import annotations

from pathlib import Path

import pytest

from aios import HookContext, LifecyclePhase
from aios.exceptions import RuntimeExecutionError
from aios.plugin_manager import PluginManager
from aios.plugins.metrics import MetricsPlugin


def _ctx(phase, *, error=None, elapsed=None):
    return HookContext(
        phase=phase,
        run_id="rid",
        component_name="Comp",
        metadata={"module": "m", "class": "Comp"},
        error=error,
        elapsed=elapsed,
    )


def _simulate_run(hook, *, failed=False, elapsed=1.0):
    hook.on_lifecycle(_ctx(LifecyclePhase.RUN_START))
    if failed:
        hook.on_lifecycle(_ctx(LifecyclePhase.ON_ERROR, error=ValueError("boom")))
    hook.on_lifecycle(_ctx(LifecyclePhase.RUN_END, elapsed=elapsed))


def _write_manifest(tmp_path: Path, module: str, class_name: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        f"version: 1\ncomponent:\n  module: {module}\n  class: {class_name}\n",
        encoding="utf-8",
    )
    return path


# -- metadata --------------------------------------------------------------------


def test_plugin_metadata():
    meta = MetricsPlugin().metadata
    assert meta.name == "metrics"
    assert meta.version == "1.0"
    assert meta.description
    assert meta.api_version == "1"


def test_initial_metrics_are_zero():
    plugin = MetricsPlugin()
    assert plugin.total_runs == 0
    assert plugin.total_elapsed == 0.0
    assert plugin.average_elapsed == 0.0  # zero-run branch


# -- counting --------------------------------------------------------------------


def test_total_runs():
    plugin = MetricsPlugin()
    hook = plugin.hooks()[0]
    for _ in range(3):
        _simulate_run(hook)
    assert plugin.total_runs == 3


def test_successful_and_failed_runs():
    plugin = MetricsPlugin()
    hook = plugin.hooks()[0]
    _simulate_run(hook)
    _simulate_run(hook, failed=True)
    _simulate_run(hook)
    assert plugin.total_runs == 3
    assert plugin.successful_runs == 2
    assert plugin.failed_runs == 1


# -- durations -------------------------------------------------------------------


def test_elapsed_accumulation():
    plugin = MetricsPlugin()
    hook = plugin.hooks()[0]
    _simulate_run(hook, elapsed=1.0)
    _simulate_run(hook, elapsed=2.5)
    assert plugin.total_elapsed == pytest.approx(3.5)


def test_average_elapsed():
    plugin = MetricsPlugin()
    hook = plugin.hooks()[0]
    _simulate_run(hook, elapsed=2.0)
    _simulate_run(hook, elapsed=4.0)
    assert plugin.average_elapsed == pytest.approx(3.0)


def test_last_elapsed():
    plugin = MetricsPlugin()
    hook = plugin.hooks()[0]
    _simulate_run(hook, elapsed=1.0)
    _simulate_run(hook, elapsed=9.0)
    assert plugin.last_elapsed == pytest.approx(9.0)


# -- teardown does not reset -----------------------------------------------------


def test_teardown_does_not_reset_metrics():
    plugin = MetricsPlugin()
    hook = plugin.hooks()[0]
    _simulate_run(hook, elapsed=1.0)
    plugin.teardown()  # inherited no-op
    assert plugin.total_runs == 1
    assert plugin.total_elapsed == pytest.approx(1.0)


# -- integration -----------------------------------------------------------------


def test_plugin_manager_integration(examples_manifest):
    plugin = MetricsPlugin()
    manager = PluginManager(plugins=[plugin])
    runtime = manager.start()
    runtime.run(examples_manifest)
    manager.close()

    assert plugin.total_runs == 1
    assert plugin.successful_runs == 1
    assert plugin.failed_runs == 0
    assert plugin.total_elapsed >= 0.0
    assert plugin.last_elapsed >= 0.0


def test_context_manager_integration_counts_failure(tmp_path):
    plugin = MetricsPlugin()
    manifest = _write_manifest(tmp_path, "lifecycle_components", "FailingComponent")
    with PluginManager(plugins=[plugin]) as runtime:
        with pytest.raises(RuntimeExecutionError):
            runtime.run(manifest)
    assert plugin.total_runs == 1
    assert plugin.failed_runs == 1
    assert plugin.successful_runs == 0
