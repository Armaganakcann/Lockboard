"""TracingPlugin — records the ordered sequence of runtime lifecycle events.

Purely observational. Contributes a single :class:`~aios.hooks.RuntimeHook`
that captures every lifecycle notification as an immutable :class:`TraceEvent`,
in the order they occur, using only fields already present on
:class:`~aios.hooks.HookContext`. It applies no filtering and changes no
runtime behaviour. No threads, no async.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aios.hooks import HookContext, LifecyclePhase, RuntimeHook
from aios.plugin import Plugin, PluginMetadata

_DESCRIPTION = "Records the ordered sequence of runtime lifecycle events as immutable traces."


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """An immutable record of a single runtime lifecycle event.

    Attributes:
        phase: The lifecycle phase observed.
        run_id: The run identifier carried by the hook context.
        elapsed: The phase/run duration in seconds, when one is provided.
        error: The error carried at ``ON_ERROR``, otherwise ``None``.
    """

    phase: LifecyclePhase
    run_id: str | None
    elapsed: float | None
    error: BaseException | None


class _TracingHook:
    """Observational hook that records each event into its plugin."""

    def __init__(self, plugin: TracingPlugin) -> None:
        """Bind the hook to the plugin that stores the trace."""
        self._plugin = plugin

    def on_lifecycle(self, context: HookContext) -> None:
        """Record every lifecycle notification, without filtering."""
        self._plugin.record(context)


class TracingPlugin(Plugin):
    """Plugin that captures the ordered runtime event trace via one hook."""

    def __init__(self) -> None:
        """Create an empty trace and the tracing hook."""
        self._events: list[TraceEvent] = []
        self._hook: _TracingHook = _TracingHook(self)

    @property
    def metadata(self) -> PluginMetadata:
        """Return the plugin's immutable identity."""
        return PluginMetadata(name="tracing", version="1.0", description=_DESCRIPTION)

    def hooks(self) -> Sequence[RuntimeHook]:
        """Return the single tracing hook."""
        return (self._hook,)

    def record(self, context: HookContext) -> None:
        """Append an immutable event for this notification (no filtering)."""
        self._events.append(
            TraceEvent(
                phase=context.phase,
                run_id=context.run_id,
                elapsed=context.elapsed,
                error=context.error,
            )
        )

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        """Return the recorded events, in order, as an immutable tuple."""
        return tuple(self._events)

    @property
    def last_event(self) -> TraceEvent | None:
        """Return the most recent event, or ``None`` if nothing is recorded."""
        if not self._events:
            return None
        return self._events[-1]

    def clear(self) -> None:
        """Discard all recorded events."""
        self._events.clear()
