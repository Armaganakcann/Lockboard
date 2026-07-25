"""Abstract base class defining the AIOS component contract.

The lifecycle is deliberately small and explicit. Only :meth:`execute` is
abstract, so trivial components stay concise while the runtime can always call
the full ``initialize`` → ``execute`` → ``shutdown`` sequence uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from aios.context import ExecutionContext, ExecutionResult


class Component(ABC):
    """Base class every AIOS component must implement.

    Components are expected to be stateless: all inputs arrive through the
    :class:`ExecutionContext`, and all outputs leave through the returned
    :class:`ExecutionResult`.
    """

    def initialize(self, context: ExecutionContext) -> None:
        """Prepare the component before execution.

        Optional hook; the default implementation does nothing. Override to
        acquire resources or validate preconditions.
        """

    @abstractmethod
    def execute(self, context: ExecutionContext) -> ExecutionResult:
        """Run the component's work and return an :class:`ExecutionResult`.

        Args:
            context: The immutable execution context for this run.

        Returns:
            The outcome of the component's work.
        """
        raise NotImplementedError

    def shutdown(self, context: ExecutionContext) -> None:
        """Release resources after execution.

        Optional hook; the default implementation does nothing. The runtime
        always invokes this, even when execution fails.
        """
