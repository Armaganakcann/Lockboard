"""MetricsPlugin — a purely observational run-metrics collector.

Contributes a single :class:`~aios.hooks.RuntimeHook` that tallies run counts
and durations from the lifecycle. It uses only fields already present on
:class:`~aios.hooks.HookContext` (``phase``, ``run_id``, ``elapsed``,
``error``), produces no new information, and changes no runtime behaviour. All
state is kept inside the plugin and exposed through read-only properties; it is
never written back to the runtime. No threads, no async.
"""

from __future__ import annotations

from collections.abc import Sequence

from aios.hooks import HookContext, LifecyclePhase, RuntimeHook
from aios.plugin import Plugin, PluginMetadata

_DESCRIPTION = "Collects observational run metrics (counts and durations) from the lifecycle."


class _MetricsHook:
    """Observational hook that records run outcomes into its plugin."""

    def __init__(self, plugin: MetricsPlugin) -> None:
        """Bind the hook to the plugin that owns the metrics."""
        self._plugin = plugin

    def on_lifecycle(self, context: HookContext) -> None:
        """Forward each lifecycle notification to the plugin's recorder."""
        self._plugin.record(context)


class MetricsPlugin(Plugin):
    """Plugin that aggregates run metrics via one observational hook.

    A run counts as failed if ``ON_ERROR`` was observed during it, and
    successful otherwise. Durations use the total run time reported at
    ``RUN_END``.
    """

    def __init__(self) -> None:
        """Initialise all counters to zero and build the metrics hook."""
        self._total_runs = 0
        self._successful_runs = 0
        self._failed_runs = 0
        self._total_elapsed = 0.0
        self._last_elapsed = 0.0
        self._current_failed = False
        self._hook: _MetricsHook = _MetricsHook(self)

    @property
    def metadata(self) -> PluginMetadata:
        """Return the plugin's immutable identity."""
        return PluginMetadata(name="metrics", version="1.0", description=_DESCRIPTION)

    def hooks(self) -> Sequence[RuntimeHook]:
        """Return the single metrics hook."""
        return (self._hook,)

    def record(self, context: HookContext) -> None:
        """Update the metrics from a lifecycle notification.

        Public so the hook can forward to it; not a setter for the metrics
        themselves. Only observes ``RUN_START``, ``ON_ERROR``, and ``RUN_END``.
        """
        phase = context.phase
        if phase is LifecyclePhase.RUN_START:
            self._current_failed = False
        elif phase is LifecyclePhase.ON_ERROR:
            self._current_failed = True
        elif phase is LifecyclePhase.RUN_END:
            elapsed = context.elapsed or 0.0
            self._total_runs += 1
            self._total_elapsed += elapsed
            self._last_elapsed = elapsed
            if self._current_failed:
                self._failed_runs += 1
            else:
                self._successful_runs += 1

    @property
    def total_runs(self) -> int:
        """Number of completed runs."""
        return self._total_runs

    @property
    def successful_runs(self) -> int:
        """Number of runs that finished without an error."""
        return self._successful_runs

    @property
    def failed_runs(self) -> int:
        """Number of runs during which an error was observed."""
        return self._failed_runs

    @property
    def total_elapsed(self) -> float:
        """Sum of run durations in seconds."""
        return self._total_elapsed

    @property
    def last_elapsed(self) -> float:
        """Duration in seconds of the most recent run."""
        return self._last_elapsed

    @property
    def average_elapsed(self) -> float:
        """Mean run duration in seconds, or ``0.0`` when there are no runs."""
        if self._total_runs == 0:
            return 0.0
        return self._total_elapsed / self._total_runs
