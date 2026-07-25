"""Tests for the Plugin API contract (RFC-0002)."""

from __future__ import annotations

import dataclasses
import logging

import pytest

import aios
from aios import Plugin, PluginContext, PluginMetadata


class _DummyPlugin(Plugin):
    """A minimal concrete plugin using only the mandatory metadata."""

    metadata = PluginMetadata(name="dummy", version="1.0")


class _NoMetadataPlugin(Plugin):
    """A subclass that omits metadata, so it must remain abstract."""


def _context() -> PluginContext:
    return PluginContext(
        logger=logging.getLogger("aios.test.plugin"),
        config={},
        aios_version=aios.__version__,
    )


def test_metadata_fields_and_defaults():
    meta = PluginMetadata(name="m", version="2.0")
    assert meta.name == "m"
    assert meta.version == "2.0"
    assert meta.description == ""
    assert meta.api_version == "1"


def test_metadata_is_immutable():
    meta = PluginMetadata(name="m", version="1")
    with pytest.raises(dataclasses.FrozenInstanceError):
        meta.name = "other"  # type: ignore[misc]


def test_context_holds_fields():
    ctx = _context()
    assert ctx.config == {}
    assert ctx.aios_version == aios.__version__
    assert ctx.logger.name == "aios.test.plugin"


def test_context_is_immutable():
    ctx = _context()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.aios_version = "9"  # type: ignore[misc]


def test_default_hooks_is_empty():
    assert _DummyPlugin().hooks() == ()


def test_default_setup_is_noop():
    assert _DummyPlugin().setup(_context()) is None


def test_default_teardown_is_noop():
    assert _DummyPlugin().teardown() is None


def test_metadata_is_accessible():
    assert _DummyPlugin().metadata.name == "dummy"


def test_metadata_is_mandatory():
    with pytest.raises(TypeError):
        _NoMetadataPlugin()  # type: ignore[abstract]


def test_public_exports():
    for name in ("Plugin", "PluginMetadata", "PluginContext"):
        assert name in aios.__all__
        assert hasattr(aios, name)
