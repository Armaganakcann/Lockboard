"""AIOS — Artificial Intelligence Operating System reference runtime.

AIOS is **not** a model, framework, LLM or agent. It is a minimal Operating
Layer / Runtime whose only responsibility is to load, run and manage the
lifecycle of AI *components*.

The public API intentionally stays small. Larger subsystems (event bus,
plugin manager, scheduler, workflow engine, registry, ...) are deliberately
left out of the core and documented as extension points instead.
"""

from __future__ import annotations

from aios.component import Component
from aios.context import ExecutionContext, ExecutionResult
from aios.exceptions import (
    AIOSError,
    ComponentLoadError,
    ConfigurationError,
    ManifestError,
    RuntimeExecutionError,
)
from aios.hooks import HookContext, LifecyclePhase, RuntimeHook
from aios.plugin import Plugin, PluginContext, PluginMetadata
from aios.runtime import Runtime

__version__ = "0.1.0a1"

__all__ = [
    "AIOSError",
    "Component",
    "ComponentLoadError",
    "ConfigurationError",
    "ExecutionContext",
    "ExecutionResult",
    "HookContext",
    "LifecyclePhase",
    "ManifestError",
    "Plugin",
    "PluginContext",
    "PluginMetadata",
    "Runtime",
    "RuntimeExecutionError",
    "RuntimeHook",
    "__version__",
]
