"""Tests for the Plugin Manager (RFC-0003)."""

from __future__ import annotations

import pytest

from aios import LifecyclePhase, Runtime
from aios.plugin import Plugin, PluginMetadata
from aios.plugin_manager import PluginError, PluginManager

_ENTRY_POINTS = "aios.plugin_manager.importlib_metadata.entry_points"


class _Hook:
    """Records a marker into a shared list at RUN_START."""

    def __init__(self, label, events):
        self._label = label
        self._events = events

    def on_lifecycle(self, context):
        if context.phase is LifecyclePhase.RUN_START:
            self._events.append((self._label, "hook"))


class SpyPlugin(Plugin):
    """Configurable plugin that records its lifecycle into a shared list."""

    def __init__(
        self,
        name,
        events,
        *,
        provides_hook=True,
        api_version="1",
        fail_setup=False,
        fail_hooks=False,
        fail_teardown=False,
    ):
        self._name = name
        self._events = events
        self._provides_hook = provides_hook
        self._api_version = api_version
        self._fail_setup = fail_setup
        self._fail_hooks = fail_hooks
        self._fail_teardown = fail_teardown

    @property
    def metadata(self):
        return PluginMetadata(name=self._name, version="1.0", api_version=self._api_version)

    def setup(self, context):
        if self._fail_setup:
            raise RuntimeError("setup boom")
        self._events.append((self._name, "setup"))

    def hooks(self):
        if self._fail_hooks:
            raise RuntimeError("hooks boom")
        if self._provides_hook:
            return [_Hook(self._name, self._events)]
        return []

    def teardown(self):
        if self._fail_teardown:
            raise RuntimeError("teardown boom")
        self._events.append((self._name, "teardown"))


class _FakeEntryPoint:
    def __init__(self, name, plugin):
        self.name = name
        self._plugin = plugin

    def load(self):
        return self._plugin


_CLASS_EVENTS: list = []


class _NoArgPlugin(Plugin):
    """A zero-argument plugin, registered by class rather than instance."""

    @property
    def metadata(self):
        return PluginMetadata(name="classy", version="1")

    def setup(self, context):
        _CLASS_EVENTS.append(("classy", "setup"))


def _setups(events):
    return [e for e in events if e[1] == "setup"]


def _hooks(events):
    return [e for e in events if e[1] == "hook"]


def _teardowns(events):
    return [e for e in events if e[1] == "teardown"]


# -- basic lifecycle -------------------------------------------------------------


def test_manual_plugin_setup_hooks_teardown(examples_manifest):
    events: list = []
    manager = PluginManager(plugins=[SpyPlugin("a", events), SpyPlugin("b", events)])
    runtime = manager.start()
    assert isinstance(runtime, Runtime)
    runtime.run(examples_manifest)
    manager.close()

    assert _setups(events) == [("a", "setup"), ("b", "setup")]
    assert _hooks(events) == [("a", "hook"), ("b", "hook")]  # aggregation + order
    assert _teardowns(events) == [("b", "teardown"), ("a", "teardown")]  # reverse


def test_start_is_idempotent():
    manager = PluginManager()
    first = manager.start()
    second = manager.start()
    assert first is second
    manager.close()


def test_context_manager(examples_manifest):
    events: list = []
    with PluginManager(plugins=[SpyPlugin("a", events)]) as runtime:
        assert isinstance(runtime, Runtime)
        runtime.run(examples_manifest)
    assert ("a", "teardown") in events


def test_close_without_start_is_noop():
    PluginManager().close()  # must not raise


def test_manual_plugin_class_is_instantiated():
    _CLASS_EVENTS.clear()
    manager = PluginManager(plugins=[_NoArgPlugin])
    manager.start()
    manager.close()
    assert ("classy", "setup") in _CLASS_EVENTS


# -- ordering & dedup ------------------------------------------------------------


def test_manual_order_is_preserved():
    events: list = []
    PluginManager(plugins=[SpyPlugin("z", events), SpyPlugin("a", events)]).start()
    assert _setups(events) == [("z", "setup"), ("a", "setup")]


def test_dedup_by_name():
    events: list = []
    manager = PluginManager(plugins=[SpyPlugin("dup", events), SpyPlugin("dup", events)])
    manager.start()
    assert _setups(events) == [("dup", "setup")]


# -- error isolation (strict=False) ----------------------------------------------


def test_setup_failure_disables_plugin(examples_manifest):
    events: list = []
    manager = PluginManager(
        plugins=[SpyPlugin("bad", events, fail_setup=True), SpyPlugin("good", events)]
    )
    runtime = manager.start()
    runtime.run(examples_manifest)
    manager.close()

    assert ("bad", "setup") not in events
    assert ("good", "setup") in events
    assert _hooks(events) == [("good", "hook")]
    assert ("bad", "teardown") not in events  # failed setup is not torn down


def test_hooks_failure_yields_no_hooks(examples_manifest):
    events: list = []
    manager = PluginManager(plugins=[SpyPlugin("h", events, fail_hooks=True)])
    runtime = manager.start()
    runtime.run(examples_manifest)
    manager.close()

    assert _hooks(events) == []
    assert ("h", "setup") in events
    assert ("h", "teardown") in events  # still active, still torn down


def test_teardown_failure_continues():
    events: list = []
    manager = PluginManager(
        plugins=[SpyPlugin("t", events, fail_teardown=True), SpyPlugin("u", events)]
    )
    manager.start()
    manager.close()  # must not raise
    assert ("u", "teardown") in events  # reverse order: u torn down despite t failing


def test_api_version_mismatch_disables_plugin(examples_manifest):
    events: list = []
    manager = PluginManager(
        plugins=[SpyPlugin("old", events, api_version="2"), SpyPlugin("good", events)]
    )
    runtime = manager.start()
    runtime.run(examples_manifest)
    manager.close()

    assert ("old", "setup") not in events
    assert ("good", "setup") in events


def test_non_plugin_candidate_is_skipped(examples_manifest):
    events: list = []
    manager = PluginManager(plugins=[object(), SpyPlugin("ok", events)])
    runtime = manager.start()
    runtime.run(examples_manifest)
    manager.close()
    assert ("ok", "setup") in events


# -- error isolation (strict=True) -----------------------------------------------


def test_strict_setup_failure_raises_and_tears_down_prior():
    events: list = []
    manager = PluginManager(
        plugins=[SpyPlugin("ok", events), SpyPlugin("bad", events, fail_setup=True)],
        strict=True,
    )
    with pytest.raises(PluginError):
        manager.start()
    assert ("ok", "setup") in events
    assert ("ok", "teardown") in events  # prior plugin cleaned up on abort


def test_strict_api_version_mismatch_raises():
    events: list = []
    with pytest.raises(PluginError):
        PluginManager(plugins=[SpyPlugin("old", events, api_version="2")], strict=True).start()


def test_strict_teardown_failure_raises():
    events: list = []
    manager = PluginManager(plugins=[SpyPlugin("t", events, fail_teardown=True)], strict=True)
    manager.start()
    with pytest.raises(PluginError):
        manager.close()


# -- entry points ----------------------------------------------------------------


def test_entry_points_disabled_by_default(monkeypatch, examples_manifest):
    def boom(*args, **kwargs):
        raise AssertionError("entry points must not be scanned when disabled")

    monkeypatch.setattr(_ENTRY_POINTS, boom)
    events: list = []
    manager = PluginManager(plugins=[SpyPlugin("m", events)])
    manager.start()
    manager.close()
    assert ("m", "setup") in events


def test_entry_points_enabled(monkeypatch, examples_manifest):
    events: list = []
    ep_plugin = SpyPlugin("ep", events)

    def fake_entry_points(group):
        assert group == "aios.plugins"
        return [_FakeEntryPoint("ep_plugin", ep_plugin)]

    monkeypatch.setattr(_ENTRY_POINTS, fake_entry_points)
    manager = PluginManager(plugins=[SpyPlugin("manual", events)], discover_entry_points=True)
    runtime = manager.start()
    runtime.run(examples_manifest)
    manager.close()

    assert _setups(events) == [("manual", "setup"), ("ep", "setup")]  # manual first


def test_entry_points_sorted_by_name(monkeypatch):
    events: list = []

    def fake_entry_points(group):
        return [
            _FakeEntryPoint("second", SpyPlugin("b_plugin", events)),
            _FakeEntryPoint("first", SpyPlugin("a_plugin", events)),
        ]

    monkeypatch.setattr(_ENTRY_POINTS, fake_entry_points)
    PluginManager(discover_entry_points=True).start()
    assert _setups(events) == [("a_plugin", "setup"), ("b_plugin", "setup")]  # sorted by name


def test_entry_point_load_failure_is_isolated(monkeypatch, examples_manifest):
    events: list = []

    class _BadEntryPoint:
        name = "broken"

        def load(self):
            raise ImportError("cannot import")

    def fake_entry_points(group):
        return [_BadEntryPoint(), _FakeEntryPoint("ok", SpyPlugin("ep_ok", events))]

    monkeypatch.setattr(_ENTRY_POINTS, fake_entry_points)
    manager = PluginManager(discover_entry_points=True)
    runtime = manager.start()
    runtime.run(examples_manifest)
    manager.close()
    assert ("ep_ok", "setup") in events
