"""Runtime lifecycle hooks — observational only (RFC-0001).

Hooks observe the runtime lifecycle; they never modify the flow, the
:class:`~aios.context.ExecutionContext`, or the
:class:`~aios.context.ExecutionResult`. A hook that raises is isolated and
logged by the runtime and never affects execution or other hooks.

This module intentionally contains **only types**. There is no plugin manager,
event bus, priority system, or control flow here — those are out of scope by
design (see the Minimum Core principle).
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from aios.context import ExecutionContext, ExecutionResult


class LifecyclePhase(enum.Enum):
    """The observable points within a single :meth:`Runtime.run` call.

    Members are ordered as they occur on the success path. ``ON_ERROR`` is
    emitted instead of ``AFTER_EXECUTE`` when the component fails.
    """

    RUN_START = "run_start"
    COMPONENT_LOADED = "component_loaded"
    BEFORE_INITIALIZE = "before_initialize"
    AFTER_INITIALIZE = "after_initialize"
    BEFORE_EXECUTE = "before_execute"
    AFTER_EXECUTE = "after_execute"
    ON_ERROR = "on_error"
    BEFORE_SHUTDOWN = "before_shutdown"
    AFTER_SHUTDOWN = "after_shutdown"
    RUN_END = "run_end"


@dataclass(frozen=True, slots=True)
class HookContext:
    """Immutable snapshot passed to a hook at a single lifecycle phase.

    Attributes:
        phase: The lifecycle phase this notification represents.
        run_id: Identifier unique to one :meth:`Runtime.run` call and stable
            across every phase of that call. Lets stateful observers correlate
            phases (e.g. open a span at ``BEFORE_EXECUTE`` and close it at
            ``AFTER_EXECUTE``) without relying on call ordering.
        component_name: Name of the component being run.
        metadata: Read-only descriptive metadata (manifest module/class, ...).
        execution_context: Read-only reference to the component's context.
        result: The execution result; populated only at ``AFTER_EXECUTE`` on
            the success path, otherwise ``None``.
        error: The error being handled; populated only at ``ON_ERROR``.
        elapsed: Monotonic duration in seconds for the relevant phase — the
            execute duration at ``AFTER_EXECUTE`` and the total run duration at
            ``RUN_END``; ``None`` otherwise.
    """

    phase: LifecyclePhase
    run_id: str
    component_name: str
    metadata: Mapping[str, Any]
    execution_context: ExecutionContext | None = None
    result: ExecutionResult | None = None
    error: BaseException | None = None
    elapsed: float | None = None


@runtime_checkable
class RuntimeHook(Protocol):
    """Observer contract for the runtime lifecycle.

    A single method keeps the contract maximally stable: adding a new
    :class:`LifecyclePhase` never changes this interface. Implementations
    select the phases they care about via ``context.phase``.
    """

    def on_lifecycle(self, context: HookContext) -> None:
        """Handle a single lifecycle notification.

        Implementations must be observational and must not raise to influence
        control flow; any exception is isolated and logged by the runtime.
        """
