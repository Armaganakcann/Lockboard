"""Tests for the dynamic component loader."""

from __future__ import annotations

import pytest

from aios.component import Component
from aios.exceptions import ComponentLoadError
from aios.loader import load_component
from aios.manifest import ComponentSpec


def _spec(module: str, class_name: str) -> ComponentSpec:
    return ComponentSpec(module=module, **{"class": class_name})


def test_load_valid_component():
    component = load_component(_spec("examples.hello_component", "HelloComponent"))
    assert isinstance(component, Component)


def test_missing_module_raises():
    with pytest.raises(ComponentLoadError):
        load_component(_spec("does.not.exist", "Nope"))


def test_missing_class_raises():
    with pytest.raises(ComponentLoadError):
        load_component(_spec("examples.hello_component", "MissingClass"))


def test_non_component_class_raises():
    with pytest.raises(ComponentLoadError):
        load_component(_spec("collections", "OrderedDict"))


def test_abstract_component_base_raises():
    # The abstract base itself cannot be instantiated.
    with pytest.raises(ComponentLoadError):
        load_component(_spec("aios.component", "Component"))


def test_attribute_not_a_class_raises():
    # A module-level constant is not a class.
    with pytest.raises(ComponentLoadError):
        load_component(_spec("examples.hello_component", "_GREETING"))
