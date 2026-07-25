"""LoggingPlugin — the reference first-party plugin.

Demonstrates the Plugin API and Plugin Manager end to end. It contributes a
single, purely **observational** :class:`~aios.hooks.RuntimeHook` that logs
runtime lifecycle events. It changes no runtime behaviour, adds no new hook
type, phase, or lifecycle, and produces no information beyond what
:class:`~aios.hooks.HookContext` already carries.

Output goes through the logger supplied in :class:`~aios.plugin.PluginContext`;
it never uses ``print`` or writes to stdout directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from logging import Logger

from aios.hooks import HookContext, LifecyclePhase, RuntimeHook
from aios.plugin import Plugin, PluginContext, PluginMetadata

_DESCRIPTION = "Logs runtime lifecycle events (start, shutdown, errors, end) observationally."


class _LoggingHook:
    """Observational hook that logs selected lifecycle phases."""

    def __init__(self, logger: Logger) -> None:
        """Store the logger the plugin was configured with."""
        self._logger = logger

    def on_lifecycle(self, context: HookContext) -> None:
        """Log a message for the observed phases; ignore all others."""
        phase = context.phase
        if phase is LifecyclePhase.RUN_START:
            self._logger.info(
                "Run started (run_id=%s, component=%s)",
                context.run_id,
                context.component_name,
            )
        elif phase is LifecyclePhase.ON_ERROR:
            self._logger.error(
                "Run failed (run_id=%s, component=%s): %s",
                context.run_id,
                context.component_name,
                context.error,
            )
        elif phase is LifecyclePhase.AFTER_SHUTDOWN:
            self._logger.info(
                "Component shut down (run_id=%s, component=%s)",
                context.run_id,
                context.component_name,
            )
        elif phase is LifecyclePhase.RUN_END:
            self._logger.info(
                "Run finished (run_id=%s, component=%s, elapsed=%.6fs)",
                context.run_id,
                context.component_name,
                context.elapsed or 0.0,
            )


class LoggingPlugin(Plugin):
    """Plugin that logs runtime lifecycle events via one observational hook."""

    def __init__(self) -> None:
        """Create the plugin; the hook is built during :meth:`setup`."""
        self._hook: _LoggingHook | None = None

    @property
    def metadata(self) -> PluginMetadata:
        """Return the plugin's immutable identity."""
        return PluginMetadata(name="logging", version="1.0", description=_DESCRIPTION)

    def setup(self, context: PluginContext) -> None:
        """Build the logging hook from the context-supplied logger."""
        self._hook = _LoggingHook(context.logger)

    def hooks(self) -> Sequence[RuntimeHook]:
        """Return the single logging hook, or nothing before setup."""
        if self._hook is None:
            return ()
        return (self._hook,)

    def teardown(self) -> None:
        """Release the hook reference."""
        self._hook = None
