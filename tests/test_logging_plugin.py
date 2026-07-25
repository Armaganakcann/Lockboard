"""Tests for the reference LoggingPlugin."""

from __future__ import annotations

import logging

import pytest

from aios import HookContext, LifecyclePhase
from aios.plugin import PluginContext
from aios.plugin_manager import PluginManager
from aios.plugins.logging import LoggingPlugin

_LOGGER_NAME = "aios.plugin.logging"


class _ListHandler(logging.Handler):
    """Captures emitted log messages into a list."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture()
def captured():
    """Attach a capturing handler to the plugin logger regardless of config."""
    logger = logging.getLogger(_LOGGER_NAME)
    handler = _ListHandler()
    logger.addHandler(handler)
    old_level = logger.level
    logger.setLevel(logging.DEBUG)
    try:
        yield logger, handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)


def _ctx(phase, *, error=None, elapsed=None):
    return HookContext(
        phase=phase,
        run_id="rid-123",
        component_name="Comp",
        metadata={"module": "m", "class": "Comp"},
        error=error,
        elapsed=elapsed,
    )


def _text(handler):
    return "\n".join(handler.messages)


# -- metadata & lifecycle --------------------------------------------------------


def test_plugin_metadata():
    meta = LoggingPlugin().metadata
    assert meta.name == "logging"
    assert meta.version == "1.0"
    assert meta.description
    assert meta.api_version == "1"


def test_hooks_empty_before_setup():
    assert LoggingPlugin().hooks() == ()


def test_setup_produces_single_hook(captured):
    logger, _ = captured
    plugin = LoggingPlugin()
    plugin.setup(PluginContext(logger=logger, config={}, aios_version="x"))
    assert len(plugin.hooks()) == 1


def test_teardown_releases_hook(captured):
    logger, _ = captured
    plugin = LoggingPlugin()
    plugin.setup(PluginContext(logger=logger, config={}, aios_version="x"))
    plugin.teardown()
    assert plugin.hooks() == ()


# -- observed events -------------------------------------------------------------


def _hook_for(logger):
    plugin = LoggingPlugin()
    plugin.setup(PluginContext(logger=logger, config={}, aios_version="x"))
    return plugin.hooks()[0]


def test_logs_on_run_start(captured):
    logger, handler = captured
    _hook_for(logger).on_lifecycle(_ctx(LifecyclePhase.RUN_START))
    assert "Run started" in _text(handler)
    assert "rid-123" in _text(handler)


def test_logs_on_run_end(captured):
    logger, handler = captured
    _hook_for(logger).on_lifecycle(_ctx(LifecyclePhase.RUN_END, elapsed=0.125))
    assert "Run finished" in _text(handler)
    assert "0.125000" in _text(handler)


def test_logs_on_error(captured):
    logger, handler = captured
    _hook_for(logger).on_lifecycle(_ctx(LifecyclePhase.ON_ERROR, error=ValueError("boom")))
    assert "Run failed" in _text(handler)
    assert "boom" in _text(handler)


def test_logs_on_shutdown(captured):
    logger, handler = captured
    _hook_for(logger).on_lifecycle(_ctx(LifecyclePhase.AFTER_SHUTDOWN))
    assert "shut down" in _text(handler)


def test_unobserved_phase_is_silent(captured):
    logger, handler = captured
    _hook_for(logger).on_lifecycle(_ctx(LifecyclePhase.BEFORE_EXECUTE))
    assert handler.messages == []


# -- integration -----------------------------------------------------------------


def test_plugin_manager_integration(captured, examples_manifest):
    _logger, handler = captured
    manager = PluginManager(plugins=[LoggingPlugin()])
    runtime = manager.start()
    runtime.run(examples_manifest)
    manager.close()
    text = _text(handler)
    assert "Run started" in text
    assert "Component shut down" in text
    assert "Run finished" in text


def test_context_manager_integration(captured, examples_manifest):
    _logger, handler = captured
    with PluginManager(plugins=[LoggingPlugin()]) as runtime:
        runtime.run(examples_manifest)
    assert "Run started" in _text(handler)
