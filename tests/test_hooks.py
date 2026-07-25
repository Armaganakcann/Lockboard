"""Tests for the observational runtime hooks (RFC-0001)."""

from __future__ import annotations

from pathlib import Path

import pytest

import lifecycle_components as fixtures
from aios import HookContext, LifecyclePhase, Runtime
from aios.exceptions import RuntimeExecutionError

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

FAILURE_PHASES = [
    LifecyclePhase.RUN_START,
    LifecyclePhase.COMPONENT_LOADED,
    LifecyclePhase.BEFORE_INITIALIZE,
    LifecyclePhase.AFTER_INITIALIZE,
    LifecyclePhase.BEFORE_EXECUTE,
    LifecyclePhase.ON_ERROR,
    LifecyclePhase.BEFORE_SHUTDOWN,
    LifecyclePhase.AFTER_SHUTDOWN,
    LifecyclePhase.RUN_END,
]


class RecordingHook:
    """Structural RuntimeHook that records every notification it receives."""

    def __init__(self) -> None:
        self.contexts: list[HookContext] = []

    @property
    def phases(self) -> list[LifecyclePhase]:
        return [ctx.phase for ctx in self.contexts]

    def on_lifecycle(self, context: HookContext) -> None:
        self.contexts.append(context)


class OrderHook:
    """Appends its own label to a shared list to prove cross-hook ordering."""

    def __init__(self, label: str, sink: list[str]) -> None:
        self._label = label
        self._sink = sink

    def on_lifecycle(self, context: HookContext) -> None:
        self._sink.append(self._label)


class FailingHook:
    """A hook that always raises, to prove exception isolation."""

    def __init__(self) -> None:
        self.calls = 0

    def on_lifecycle(self, context: HookContext) -> None:
        self.calls += 1
        raise RuntimeError("hook boom")


def _write_manifest(tmp_path: Path, module: str, class_name: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        f"version: 1\ncomponent:\n  module: {module}\n  class: {class_name}\n",
        encoding="utf-8",
    )
    return path


# --- Backward compatibility / zero-hook behavior --------------------------------


def test_no_hooks_behaves_as_before(examples_manifest):
    result = Runtime().run(examples_manifest)
    assert result.success is True
    assert result.output == "Hello AIOS!"


def test_empty_hook_list_behaves_as_before(examples_manifest):
    result = Runtime(hooks=[]).run(examples_manifest)
    assert result.output == "Hello AIOS!"


# --- Phase ordering -------------------------------------------------------------


def test_hook_receives_success_phases_in_order(examples_manifest):
    hook = RecordingHook()
    Runtime(hooks=[hook]).run(examples_manifest)
    assert hook.phases == SUCCESS_PHASES


def test_hook_receives_failure_phases_in_order(tmp_path):
    hook = RecordingHook()
    manifest = _write_manifest(tmp_path, "lifecycle_components", "FailingComponent")
    with pytest.raises(RuntimeExecutionError):
        Runtime(hooks=[hook]).run(manifest)
    assert hook.phases == FAILURE_PHASES


# --- Multiple hooks -------------------------------------------------------------


def test_multiple_hooks_all_receive_every_phase(examples_manifest):
    first, second = RecordingHook(), RecordingHook()
    Runtime(hooks=[first, second]).run(examples_manifest)
    assert first.phases == SUCCESS_PHASES
    assert second.phases == SUCCESS_PHASES


def test_hooks_called_in_registration_order(examples_manifest):
    sink: list[str] = []
    Runtime(hooks=[OrderHook("a", sink), OrderHook("b", sink)]).run(examples_manifest)
    # For every phase, hook "a" is notified before hook "b".
    assert sink == ["a", "b"] * len(SUCCESS_PHASES)


# --- Exception isolation --------------------------------------------------------


def test_failing_hook_does_not_break_run(examples_manifest):
    failing = FailingHook()
    observer = RecordingHook()
    result = Runtime(hooks=[failing, observer]).run(examples_manifest)
    # The run still succeeds ...
    assert result.output == "Hello AIOS!"
    # ... the failing hook was invoked for every phase ...
    assert failing.calls == len(SUCCESS_PHASES)
    # ... and the following hook still received every phase.
    assert observer.phases == SUCCESS_PHASES


# --- Runtime guarantees preserved ----------------------------------------------


def test_shutdown_guarantee_preserved_with_hooks(tmp_path):
    fixtures.FailingComponent.shutdown_called = False
    hook = RecordingHook()
    manifest = _write_manifest(tmp_path, "lifecycle_components", "FailingComponent")
    with pytest.raises(RuntimeExecutionError):
        Runtime(hooks=[hook]).run(manifest)
    assert fixtures.FailingComponent.shutdown_called is True
    assert LifecyclePhase.ON_ERROR in hook.phases
    assert hook.phases[-1] is LifecyclePhase.RUN_END


# --- HookContext payload --------------------------------------------------------


def test_hook_context_fields_on_success(examples_manifest):
    hook = RecordingHook()
    Runtime(hooks=[hook]).run(examples_manifest)

    run_ids = {ctx.run_id for ctx in hook.contexts}
    assert len(run_ids) == 1  # stable across all phases
    assert next(iter(run_ids)) != ""

    for ctx in hook.contexts:
        assert ctx.component_name == "HelloComponent"
        assert ctx.metadata["class"] == "HelloComponent"
        assert ctx.execution_context is not None

    after_execute = next(c for c in hook.contexts if c.phase is LifecyclePhase.AFTER_EXECUTE)
    assert after_execute.result is not None
    assert after_execute.result.output == "Hello AIOS!"
    assert after_execute.elapsed is not None and after_execute.elapsed >= 0.0

    run_end = next(c for c in hook.contexts if c.phase is LifecyclePhase.RUN_END)
    assert run_end.elapsed is not None and run_end.elapsed >= 0.0


def test_hook_context_error_populated_on_failure(tmp_path):
    hook = RecordingHook()
    manifest = _write_manifest(tmp_path, "lifecycle_components", "FailingComponent")
    with pytest.raises(RuntimeExecutionError):
        Runtime(hooks=[hook]).run(manifest)

    on_error = next(c for c in hook.contexts if c.phase is LifecyclePhase.ON_ERROR)
    assert isinstance(on_error.error, RuntimeExecutionError)
    # No AFTER_EXECUTE on the failure path.
    assert LifecyclePhase.AFTER_EXECUTE not in hook.phases
