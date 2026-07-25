"""Execution context and result value objects passed through the runtime.

Both types are immutable, frozen dataclasses. ``ExecutionContext`` carries
everything a component needs to run, which keeps components stateless and makes
future concurrent or distributed execution safe by design. ``ExecutionResult``
is the single, typed return contract for :meth:`Component.execute`.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Immutable container handed to a component during its lifecycle.

    Attributes:
        component_name: Human-readable identifier for the running component.
        logger: Logger scoped to the component.
        config: Read-only configuration mapping (reserved extension point).
        metadata: Read-only descriptive metadata about the component/source.
    """

    component_name: str
    logger: logging.Logger
    config: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Immutable outcome returned by :meth:`Component.execute`.

    Attributes:
        success: Whether execution completed successfully.
        output: Arbitrary payload produced by the component.
        error: Human-readable error message when ``success`` is ``False``.
    """

    success: bool
    output: Any = None
    error: str | None = None

    @classmethod
    def ok(cls, output: Any = None) -> ExecutionResult:
        """Build a successful result carrying ``output``."""
        return cls(success=True, output=output)

    @classmethod
    def failed(cls, error: str) -> ExecutionResult:
        """Build a failed result carrying an ``error`` message."""
        return cls(success=False, error=error)
