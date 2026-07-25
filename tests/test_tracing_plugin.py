"""Tests for the reference TracingPlugin."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from aios import HookContext, LifecyclePhase
from aios.exceptions import RuntimeExecutionError
from aios.plugin_manager import PluginManager
from aios.plugins.tracing import TraceEvent, TracingPlugin

SUCCESS_PHASES = [
    LifecyclePhase.RUN_START,
    LifecyclePhase.COMPONENT_LOADED,
    LifecyclePhase.BEFORE_INITIALIZE,
    LifecyclePhase.AFTER_INITIALIZE,
    LifecyclePhase.BEFORE_EXECUTE,
    LifecyclePhase.AFTER_EXECUTE,
    LifecyclePhase.BEFORE_SHUTDOWN,
    LifecyclePhase.AFTER_SHUTDOWN,
    LifecyclePhase.RUN_END,
]


def _ctx(phase, *, run_id="rid", elapsed=None, error=None):
    return HookContext(
        phase=phase,
        run_id=run_id,
        component_name="Comp",
        metadata={"module": "m", "class": "Comp"},
        elapsed=elapsed,
        error=error,
    )


def _write_manifest(tmp_path: Path, module: str, class_name: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        f"version: 1\ncomponent:\n  module: {module}\n  class: {class_name}\n",
        encoding="utf-8",
    )
    return path


# -- metadata & basics -----------------------------------------------------------


def test_plugin_metadata():
    meta = TracingPlugin().metadata
    assert meta.name == "tracing"
    assert meta.version == "1.0"
    assert meta.description
    assert meta.api_version == "1"


def test_initially_empty():
    plugin = TracingPlugin()
    assert plugin.events == ()
    assert plugin.last_event is None


# -- recording -------------------------------------------------------------------


def test_records_a_trace_event():
    plugin = TracingPlugin()
    plugin.hooks()[0].on_lifecycle(_ctx(LifecyclePhase.RUN_START))
    assert len(plugin.events) == 1
    assert isinstance(plugin.events[0], TraceEvent)


def test_event_order_is_preserved():
    plugin = TracingPlugin()
    hook = plugin.hooks()[0]
    for phase in (LifecyclePhase.RUN_START, LifecyclePhase.BEFORE_EXECUTE, LifecyclePhase.RUN_END):
        hook.on_lifecycle(_ctx(phase))
    assert [e.phase for e in plugin.events] == [
        LifecyclePhase.RUN_START,
        LifecyclePhase.BEFORE_EXECUTE,
        LifecyclePhase.RUN_END,
    ]


def test_run_start_recorded():
    plugin = TracingPlugin()
    plugin.hooks()[0].on_lifecycle(_ctx(LifecyclePhase.RUN_START))
    assert plugin.last_event is not None
    assert plugin.last_event.phase is LifecyclePhase.RUN_START


def test_run_end_recorded():
    plugin = TracingPlugin()
    plugin.hooks()[0].on_lifecycle(_ctx(LifecyclePhase.RUN_END))
    assert plugin.last_event is not None
    assert plugin.last_event.phase is LifecyclePhase.RUN_END


def test_on_error_recorded():
    plugin = TracingPlugin()
    error = ValueError("boom")
    plugin.hooks()[0].on_lifecycle(_ctx(LifecyclePhase.ON_ERROR, error=error))
    assert plugin.last_event is not None
    assert plugin.last_event.phase is LifecyclePhase.ON_ERROR
    assert plugin.last_event.error is error


def test_elapsed_is_carried():
    plugin = TracingPlugin()
    plugin.hooks()[0].on_lifecycle(_ctx(LifecyclePhase.RUN_END, elapsed=1.5))
    assert plugin.last_event is not None
    assert plugin.last_event.elapsed == 1.5


def test_run_id_is_carried():
    plugin = TracingPlugin()
    plugin.hooks()[0].on_lifecycle(_ctx(LifecyclePhase.RUN_START, run_id="abc"))
    assert plugin.last_event is not None
    assert plugin.last_event.run_id == "abc"


# -- immutability & views --------------------------------------------------------


def test_trace_event_is_immutable():
    plugin = TracingPlugin()
    plugin.hooks()[0].on_lifecycle(_ctx(LifecyclePhase.RUN_START))
    event = plugin.events[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.phase = LifecyclePhase.RUN_END  # type: ignore[misc]


def test_events_returns_immutable_tuple():
    plugin = TracingPlugin()
    plugin.hooks()[0].on_lifecycle(_ctx(LifecyclePhase.RUN_START))
    snapshot = plugin.events
    assert isinstance(snapshot, tuple)
    # A later event must not mutate a previously returned snapshot.
    plugin.hooks()[0].on_lifecycle(_ctx(LifecyclePhase.RUN_END))
    assert len(snapshot) == 1
    assert len(plugin.events) == 2


def test_clear_discards_events():
    plugin = TracingPlugin()
    plugin.hooks()[0].on_lifecycle(_ctx(LifecyclePhase.RUN_START))
    plugin.clear()
    assert plugin.events == ()
    assert plugin.last_event is None


# -- integration -----------------------------------------------------------------


def test_plugin_manager_integration(examples_manifest):
    plugin = TracingPlugin()
    manager = PluginManager(plugins=[plugin])
    runtime = manager.start()
    runtime.run(examples_manifest)
    manager.close()

    assert [e.phase for e in plugin.events] == SUCCESS_PHASES
    run_ids = {e.run_id for e in plugin.events}
    assert len(run_ids) == 1  # stable across the run
    assert next(iter(run_ids)) != ""


def test_context_manager_integration_records_error(tmp_path):
    plugin = TracingPlugin()
    manifest = _write_manifest(tmp_path, "lifecycle_components", "FailingComponent")
    with PluginManager(plugins=[plugin]) as runtime:
        with pytest.raises(RuntimeExecutionError):
            runtime.run(manifest)

    phases = [e.phase for e in plugin.events]
    assert LifecyclePhase.ON_ERROR in phases
    assert LifecyclePhase.AFTER_EXECUTE not in phases
    assert phases[-1] is LifecyclePhase.RUN_END
