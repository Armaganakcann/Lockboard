"""Tests for the reference HelloComponent."""

from __future__ import annotations

from examples.hello_component import HelloComponent


def test_execute_returns_hello(context):
    result = HelloComponent().execute(context)
    assert result.success is True
    assert result.output == "Hello AIOS!"
