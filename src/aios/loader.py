"""Dynamic component loading via :mod:`importlib`.

The loader never hard-codes class names; it resolves both the module and the
class purely from the manifest's :class:`ComponentSpec`. This is the seam a
future plugin manager would build on (e.g. ``importlib.metadata`` entry points).
"""

from __future__ import annotations

import importlib
import inspect
import os
import sys

from aios.component import Component
from aios.exceptions import ComponentLoadError
from aios.manifest import ComponentSpec


def _ensure_cwd_on_path() -> None:
    """Make the current working directory importable.

    Console scripts do not place the invocation directory on ``sys.path``.
    Adding it lets manifests reference project-local modules such as
    ``examples.hello_component`` when AIOS is run from the project root.
    """
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)


def load_component(spec: ComponentSpec) -> Component:
    """Import and instantiate the component described by ``spec``.

    Args:
        spec: The manifest component locator.

    Returns:
        A ready-to-use :class:`Component` instance.

    Raises:
        ComponentLoadError: If the module or class cannot be imported, the
            attribute is not a :class:`Component` subclass, or instantiation
            fails.
    """
    _ensure_cwd_on_path()

    try:
        module = importlib.import_module(spec.module)
    except ImportError as exc:
        raise ComponentLoadError(f"Cannot import module '{spec.module}': {exc}") from exc

    try:
        attribute = getattr(module, spec.class_name)
    except AttributeError as exc:
        raise ComponentLoadError(
            f"Module '{spec.module}' has no attribute '{spec.class_name}'."
        ) from exc

    if not inspect.isclass(attribute) or not issubclass(attribute, Component):
        raise ComponentLoadError(
            f"'{spec.module}.{spec.class_name}' is not an aios.Component subclass."
        )

    try:
        return attribute()
    except Exception as exc:  # broad on purpose: surfaced as a typed load error
        raise ComponentLoadError(
            f"Failed to instantiate '{spec.module}.{spec.class_name}': {exc}"
        ) from exc
