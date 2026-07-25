"""First-party AIOS plugins.

Reference plugins that demonstrate real use of the Plugin API and Plugin
Manager. They live outside the runtime core and are opt-in; the runtime never
imports them.
"""

from __future__ import annotations

from aios.plugins.logging import LoggingPlugin
from aios.plugins.metrics import MetricsPlugin
from aios.plugins.tracing import TracingPlugin

__all__ = ["LoggingPlugin", "MetricsPlugin", "TracingPlugin"]
