"""Exception hierarchy for the AIOS runtime.

All AIOS errors derive from :class:`AIOSError`, so callers can catch the whole
family with a single ``except AIOSError`` while still being able to handle
specific failure modes when they need to.
"""

from __future__ import annotations


class AIOSError(Exception):
    """Base class for every error raised by AIOS."""


class ManifestError(AIOSError):
    """Raised when a manifest is missing, malformed or fails validation."""


class ComponentLoadError(AIOSError):
    """Raised when a component cannot be imported or instantiated."""


class RuntimeExecutionError(AIOSError):
    """Raised when component execution fails unexpectedly."""


class ConfigurationError(AIOSError):
    """Raised when runtime configuration is invalid."""
