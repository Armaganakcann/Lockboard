"""AIOS — Artificial Intelligence Operating System reference runtime.

AIOS is **not** a model, framework, LLM or agent. It is a minimal Operating
Layer / Runtime whose only responsibility is to load, run and manage the
lifecycle of AI *components*.

The core public API stays deliberately small: the runtime, the component and
manifest model, the observational lifecycle hooks, and the plugin *contract*.
The plugin manager and the first-party plugins live in separate modules
(``aios.plugin_manager``, ``aios.plugins``), and larger subsystems (event bus,
scheduler, workflow engine, registry, ...) remain out of the core and are
documented as extension points instead.
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

__version__ = "0.3.0a1"

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
