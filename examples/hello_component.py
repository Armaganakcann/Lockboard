"""Reference component that greets the world.

Run it with::

    aios run examples/hello.yaml
"""

from __future__ import annotations

from aios import Component, ExecutionContext, ExecutionResult

_GREETING = "Hello AIOS!"


class HelloComponent(Component):
    """Minimal component demonstrating the full lifecycle."""

    def initialize(self, context: ExecutionContext) -> None:
        context.logger.info("Initializing %s", context.component_name)

    def execute(self, context: ExecutionContext) -> ExecutionResult:
        context.logger.info("Executing %s", context.component_name)
        return ExecutionResult.ok(_GREETING)

    def shutdown(self, context: ExecutionContext) -> None:
        context.logger.info("Shutting down %s", context.component_name)
