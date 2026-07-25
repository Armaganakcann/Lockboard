"""Plugin Manager — orchestrates the plugin lifecycle (RFC-0003).

The manager lives **outside** the runtime core: the dependency direction is
always manager → runtime, never the reverse, and the runtime never learns about
plugins. The single public type is :class:`PluginManager`. There is
intentionally no separate loader, registry, or pipeline (Minimum Core).

Lifecycle: discover → instantiate → validate(api_version) → setup(context)
→ collect hooks → ``Runtime(hooks=...)`` → teardown.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from importlib import metadata as importlib_metadata
from types import TracebackType
from typing import Any

from aios import __version__
from aios.exceptions import AIOSError
from aios.hooks import RuntimeHook
from aios.logger import get_logger
from aios.plugin import Plugin, PluginContext, PluginMetadata
from aios.runtime import Runtime

SUPPORTED_PLUGIN_API_VERSION = "1"


class PluginError(AIOSError):
    """Raised when plugin activation or teardown fails in strict mode."""


def _major(api_version: str) -> str:
    """Return the major component of an ``api_version`` string."""
    return api_version.split(".", 1)[0]


class PluginManager:
    """Manages the lifecycle of plugins and produces a configured runtime.

    The manager discovers plugins (manual registration plus optional Python
    entry points), sets them up, aggregates their hooks into a single
    :class:`~aios.runtime.Runtime`, and tears them down. It never modifies the
    runtime, the component, the hooks, or the plugin API.

    Args:
        plugins: Manually registered plugins — instances or ``Plugin``
            subclasses. Their registration order is preserved.
        discover_entry_points: When ``True``, also discover plugins from Python
            entry points. Disabled by default (avoids running third-party code
            implicitly).
        entry_point_group: The entry-point group to scan when discovery is on.
        config: Optional mapping of plugin name to that plugin's configuration.
        strict: When ``True``, the first activation error raises
            :class:`PluginError` instead of skipping the offending plugin.
    """

    def __init__(
        self,
        plugins: Sequence[Plugin | type[Plugin]] = (),
        discover_entry_points: bool = False,
        entry_point_group: str = "aios.plugins",
        config: Mapping[str, Mapping[str, Any]] | None = None,
        strict: bool = False,
    ) -> None:
        """Store configuration; no discovery or setup happens until ``start``."""
        self._manual: tuple[Plugin | type[Plugin], ...] = tuple(plugins)
        self._discover_entry_points = discover_entry_points
        self._entry_point_group = entry_point_group
        self._config: Mapping[str, Mapping[str, Any]] = config or {}
        self._strict = strict
        self._logger = get_logger("plugin_manager")
        self._active: list[Plugin] = []
        self._runtime: Runtime | None = None

    def start(self) -> Runtime:
        """Activate all plugins and return a runtime configured with their hooks.

        Idempotent: calling ``start`` again returns the same runtime without
        re-activating. In strict mode, an activation failure tears down any
        already-set-up plugins before propagating.

        Returns:
            A :class:`~aios.runtime.Runtime` built with the aggregated hooks.
        """
        if self._runtime is not None:
            return self._runtime

        self._active = []
        try:
            for plugin in self._dedup(self._discover()):
                if self._validate_api(plugin):
                    self._setup_plugin(plugin)
            hooks = self._collect_hooks()
        except PluginError:
            self._teardown()
            self._active = []
            raise

        self._runtime = Runtime(hooks=hooks)
        return self._runtime

    def close(self) -> None:
        """Tear down active plugins in reverse setup order.

        Every teardown is attempted even if some fail; failures are logged. In
        strict mode a :class:`PluginError` is raised after all teardowns run.
        """
        if self._runtime is None:
            return

        errors = self._teardown()
        self._active = []
        self._runtime = None
        if self._strict and errors:
            name, exc = errors[0]
            raise PluginError(f"plugin '{name}' failed during teardown") from exc

    def __enter__(self) -> Runtime:
        """Enter the context manager, activating plugins via :meth:`start`."""
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the context manager, tearing down plugins via :meth:`close`."""
        self.close()

    # -- internal helpers --------------------------------------------------

    def _discover(self) -> list[Plugin]:
        plugins: list[Plugin] = []
        for candidate in self._manual:
            plugin = self._instantiate_safe(candidate, "a manually registered plugin")
            if plugin is not None:
                plugins.append(plugin)
        if self._discover_entry_points:
            plugins.extend(self._entry_point_plugins())
        return plugins

    def _entry_point_plugins(self) -> list[Plugin]:
        plugins: list[Plugin] = []
        for entry_point in importlib_metadata.entry_points(group=self._entry_point_group):
            loaded = self._load_entry_point(entry_point)
            if loaded is None:
                continue
            plugin = self._instantiate_safe(loaded, f"entry point '{entry_point.name}'")
            if plugin is not None:
                plugins.append(plugin)
        plugins.sort(key=lambda plugin: plugin.metadata.name)
        return plugins

    def _load_entry_point(self, entry_point: importlib_metadata.EntryPoint) -> object | None:
        try:
            loaded: object = entry_point.load()
        except Exception as exc:  # isolated per error policy
            self._report(f"failed to load entry point '{entry_point.name}'", exc)
            return None
        return loaded

    def _instantiate_safe(self, candidate: object, label: str) -> Plugin | None:
        try:
            return self._instantiate(candidate)
        except Exception as exc:  # isolated per error policy
            self._report(f"failed to instantiate {label}", exc)
            return None

    def _instantiate(self, candidate: object) -> Plugin:
        if isinstance(candidate, Plugin):
            return candidate
        if isinstance(candidate, type) and issubclass(candidate, Plugin):
            return candidate()
        raise PluginError(f"{candidate!r} is not a Plugin instance or subclass")

    def _dedup(self, plugins: list[Plugin]) -> list[Plugin]:
        seen: set[str] = set()
        unique: list[Plugin] = []
        for plugin in plugins:
            name = plugin.metadata.name
            if name in seen:
                self._logger.warning("Duplicate plugin '%s' ignored", name)
                continue
            seen.add(name)
            unique.append(plugin)
        return unique

    def _validate_api(self, plugin: Plugin) -> bool:
        api_version = plugin.metadata.api_version
        if _major(api_version) != _major(SUPPORTED_PLUGIN_API_VERSION):
            self._report(
                f"plugin '{plugin.metadata.name}' targets unsupported plugin api_version "
                f"{api_version!r} (supported: {SUPPORTED_PLUGIN_API_VERSION})"
            )
            return False
        return True

    def _setup_plugin(self, plugin: Plugin) -> None:
        context = self._build_context(plugin.metadata)
        try:
            plugin.setup(context)
        except Exception as exc:  # isolated per error policy
            self._report(f"plugin '{plugin.metadata.name}' failed during setup", exc)
            return
        self._active.append(plugin)

    def _build_context(self, metadata: PluginMetadata) -> PluginContext:
        plugin_config: Mapping[str, Any] = self._config.get(metadata.name, {})
        return PluginContext(
            logger=get_logger(f"plugin.{metadata.name}"),
            config=plugin_config,
            aios_version=__version__,
        )

    def _collect_hooks(self) -> list[RuntimeHook]:
        hooks: list[RuntimeHook] = []
        for plugin in self._active:
            try:
                hooks.extend(plugin.hooks())
            except Exception as exc:  # isolated per error policy
                self._report(f"plugin '{plugin.metadata.name}' failed during hooks()", exc)
        return hooks

    def _teardown(self) -> list[tuple[str, BaseException]]:
        errors: list[tuple[str, BaseException]] = []
        for plugin in reversed(self._active):
            try:
                plugin.teardown()
            except Exception as exc:  # never abort teardown; collect and continue
                self._logger.error(
                    "plugin '%s' failed during teardown: %s", plugin.metadata.name, exc
                )
                errors.append((plugin.metadata.name, exc))
        return errors

    def _report(self, message: str, exc: BaseException | None = None) -> None:
        if self._strict:
            raise PluginError(message) from exc
        if exc is None:
            self._logger.error("%s", message)
        else:
            self._logger.error("%s: %s", message, exc)
