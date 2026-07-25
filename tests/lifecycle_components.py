"""Fixture components used by the runtime tests.

These live in the ``tests`` package (added to ``pythonpath`` in
``pyproject.toml``) so manifests can reference them by module name.
"""

from __future__ import annotations

from typing import ClassVar

from aios import Component, ExecutionContext, ExecutionResult


class LifecycleSpy(Component):
    """Records the order of lifecycle calls into the class-level ``calls``."""

    calls: ClassVar[list[str]] = []

    def initialize(self, context: ExecutionContext) -> None:
        type(self).calls.append("initialize")

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        type(self).calls.append("execute")
        return ExecutionResult.ok("spied")

    def shutdown(self, context: ExecutionContext) -> None:
        type(self).calls.append("shutdown")


class FailingComponent(Component):
    """Raises during execute to test error handling and shutdown guarantees."""

    shutdown_called: ClassVar[bool] = False

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        raise ValueError("boom")

    def shutdown(self, context: ExecutionContext) -> None:
        type(self).shutdown_called = True


class BadReturnComponent(Component):
    """Returns a value that violates the ExecutionResult contract."""

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        return "not a result"  # type: ignore[return-value]


class ShutdownFailingComponent(Component):
    """Executes successfully but raises during shutdown."""

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        return ExecutionResult.ok("ok")

    def shutdown(self, context: ExecutionContext) -> None:
        raise RuntimeError("shutdown boom")


class ExecuteAndShutdownFailingComponent(Component):
    """Fails in both execute and shutdown; the execute error must win."""

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        raise ValueError("execute boom")

    def shutdown(self, context: ExecutionContext) -> None:
        raise RuntimeError("shutdown boom")
