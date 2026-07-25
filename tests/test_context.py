"""Tests for the ExecutionContext and ExecutionResult value objects."""

from __future__ import annotations

import dataclasses

import pytest

from aios import ExecutionResult


def test_result_ok_defaults():
    result = ExecutionResult.ok("payload")
    assert result.success is True
    assert result.output == "payload"
    assert result.error is None


def test_result_ok_without_output():
    result = ExecutionResult.ok()
    assert result.success is True
    assert result.output is None


def test_result_failed():
    result = ExecutionResult.failed("bad")
    assert result.success is False
    assert result.error == "bad"
    assert result.output is None


def test_result_is_frozen():
    result = ExecutionResult.ok("x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.success = False  # type: ignore[misc]


def test_context_has_empty_defaults(context):
    assert context.config == {}
    assert context.metadata == {}


def test_context_is_frozen(context):
    with pytest.raises(dataclasses.FrozenInstanceError):
        context.component_name = "changed"  # type: ignore[misc]
