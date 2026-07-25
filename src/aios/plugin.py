"""Plugin API — type contract only (RFC-0002).

This module defines the *contract* that plugins implement and that a future,
separate Plugin Manager builds on. It contains **only types**: there is no
plugin manager, discovery, entry-point loading, loader, or registry here — by
design (Minimum Core principle). Nothing in the runtime imports this module;
the dependency direction is always plugin/manager → runtime, never the reverse.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from logging import Logger
from typing import Any

from aios.hooks import RuntimeHook


@dataclass(frozen=True, slots=True)
class PluginMetadata:
    """Immutable identity of a plugin.

    Descriptive data only; it carries no behaviour. A Plugin Manager uses it to
    identify, de-duplicate, order, and report plugins, and to check plugin-API
    compatibility via ``api_version``.

    Attributes:
        name: Unique plugin identifier (used by a manager for de-duplication).
        version: The plugin's own version string.
        description: Optional human-readable description.
        api_version: The AIOS plugin-API version this plugin targets.
    """

    name: str
    version: str
    description: str = ""
    api_version: str = "1"


@dataclass(frozen=True, slots=True)
class PluginContext:
    """Immutable, read-only context handed to a plugin during setup.

    The seam through which a plugin receives what it needs — a scoped logger,
    its configuration, the host version — without touching runtime internals.
    It holds no mutable state.

    Attributes:
        logger: Logger scoped to the plugin.
        config: Read-only configuration mapping for the plugin.
        aios_version: Version of the AIOS host running the plugin.
    """

    logger: Logger
    config: Mapping[str, Any]
    aios_version: str


class Plugin(ABC):
    """Base class every AIOS plugin implements.

    A plugin is a lifecycle-managed unit that contributes observational
    :class:`~aios.hooks.RuntimeHook` objects. Only :attr:`metadata` is
    mandatory; ``setup``, ``hooks``, and ``teardown`` are optional and default
    to no-ops so trivial plugins stay concise.

    The plugin lifecycle (setup once, teardown once) is coarser than and
    distinct from the per-run hook lifecycle. Both are driven from outside the
    runtime by a Plugin Manager, which is intentionally **not** part of this
    contract.
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return the plugin's immutable identity. Must be implemented."""

    def setup(self, context: PluginContext) -> None:
        """Prepare the plugin before it contributes hooks.

        Optional hook; the default implementation does nothing. Override to
        acquire resources. Implementations should be atomic: on failure they
        must clean up any partial state, because a failed setup is not torn
        down.
        """

    def hooks(self) -> Sequence[RuntimeHook]:
        """Return the runtime hooks this plugin contributes.

        Optional; the default returns an empty tuple. Called after
        :meth:`setup`, so hooks may use resources acquired there.
        """
        return ()

    def teardown(self) -> None:
        """Release resources after the plugin is no longer needed.

        Optional hook; the default implementation does nothing.
        """
