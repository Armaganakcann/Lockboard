"""Shared pytest fixtures and path anchors."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from aios.context import ExecutionContext

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def project_root() -> Path:
    """Absolute path to the repository root."""
    return PROJECT_ROOT


@pytest.fixture()
def examples_manifest() -> Path:
    """Path to the bundled ``hello.yaml`` example manifest."""
    return PROJECT_ROOT / "examples" / "hello.yaml"


@pytest.fixture()
def context() -> ExecutionContext:
    """A lightweight execution context for direct component tests."""
    return ExecutionContext(
        component_name="test",
        logger=logging.getLogger("aios.test"),
    )
