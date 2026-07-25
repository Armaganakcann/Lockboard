"""Central logging utilities for the AIOS runtime.

The core package follows the standard-library best practice for libraries: it
never configures the root logger or attaches noisy handlers on import. A
:class:`logging.NullHandler` is attached to the package logger so that
applications embedding AIOS see no output unless they opt in.

Handler and formatter configuration is the responsibility of the application
layer (for example the CLI), via :func:`configure_logging`.
"""

from __future__ import annotations

import logging

from rich.logging import RichHandler

PACKAGE_LOGGER_NAME = "aios"
_DEFAULT_LOG_FORMAT = "%(message)s"
_DEFAULT_DATE_FORMAT = "[%X]"
_STREAM_LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"

# Attach a NullHandler exactly once so importing AIOS never emits log records.
logging.getLogger(PACKAGE_LOGGER_NAME).addHandler(logging.NullHandler())


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger namespaced under the AIOS package.

    Args:
        name: Optional dotted suffix. ``None`` returns the package root logger,
            otherwise ``aios.<name>`` is returned.

    Returns:
        A :class:`logging.Logger` scoped to the AIOS namespace.
    """
    if name is None or name == PACKAGE_LOGGER_NAME:
        return logging.getLogger(PACKAGE_LOGGER_NAME)
    return logging.getLogger(f"{PACKAGE_LOGGER_NAME}.{name}")


def configure_logging(level: int = logging.WARNING, *, use_rich: bool = True) -> None:
    """Configure handlers for the AIOS package logger.

    Intended to be called by application entry points (e.g. the CLI), never by
    library code. The call is idempotent: previously configured non-null
    handlers are replaced rather than accumulated.

    Args:
        level: Minimum log level for the package logger.
        use_rich: When ``True`` use Rich's colourised handler, otherwise a
            plain stream handler.
    """
    logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    logger.setLevel(level)

    for existing in list(logger.handlers):
        if not isinstance(existing, logging.NullHandler):
            logger.removeHandler(existing)

    handler: logging.Handler
    if use_rich:
        handler = RichHandler(rich_tracebacks=True, show_path=False)
        handler.setFormatter(
            logging.Formatter(_DEFAULT_LOG_FORMAT, datefmt=_DEFAULT_DATE_FORMAT)
        )
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_STREAM_LOG_FORMAT))

    handler.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
