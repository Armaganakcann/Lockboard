"""Verify the packaged entry points for the first-party plugins.

These check the real installed distribution metadata (group ``aios.plugins``),
complementing the monkeypatched discovery tests in ``test_plugin_manager``.
"""

from __future__ import annotations

from importlib import metadata

from aios.plugin import Plugin
from aios.plugin_manager import PluginManager
from aios.plugins.logging import LoggingPlugin
from aios.plugins.metrics import MetricsPlugin

_GROUP = "aios.plugins"


def _entry_points():
    return {ep.name: ep for ep in metadata.entry_points(group=_GROUP)}


def test_official_plugins_are_registered():
    names = set(_entry_points())
    assert {"logging", "metrics"} <= names


def test_logging_entry_point_loads_class():
    loaded = _entry_points()["logging"].load()
    assert loaded is LoggingPlugin
    assert issubclass(loaded, Plugin)


def test_metrics_entry_point_loads_class():
    loaded = _entry_points()["metrics"].load()
    assert loaded is MetricsPlugin
    assert issubclass(loaded, Plugin)


def test_manager_discovers_registered_plugins(examples_manifest):
    manager = PluginManager(discover_entry_points=True)
    runtime = manager.start()
    runtime.run(examples_manifest)  # discovered plugins' hooks run without error
    manager.close()
