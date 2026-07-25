"""Manifest schema, parsing and version dispatch.

Manifests are versioned from day one. :func:`parse_manifest` inspects the
``version`` field and dispatches to the matching Pydantic model, so new
manifest revisions can be added later without breaking existing files.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aios.exceptions import ManifestError

_VERSION_FIELD = "version"


class ComponentSpec(BaseModel):
    """Locator describing which class implements the component."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    module: str = Field(..., min_length=1, description="Importable module path.")
    class_name: str = Field(
        ...,
        alias="class",
        min_length=1,
        description="Component class name inside the module.",
    )


class ManifestV1(BaseModel):
    """Version 1 manifest schema."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    version: Literal[1]
    component: ComponentSpec


# Public type alias. As new schema versions are added this becomes a Union.
Manifest = ManifestV1

# Version dispatch table: the single place that must change to add a version.
_MANIFEST_MODELS: dict[int, type[ManifestV1]] = {1: ManifestV1}


def parse_manifest(data: object) -> Manifest:
    """Validate a raw manifest mapping and return a typed model.

    Args:
        data: The deserialized manifest (typically from YAML).

    Returns:
        A validated manifest model matching the declared version.

    Raises:
        ManifestError: If the payload is not a mapping, is missing/has an
            unsupported version, or fails schema validation.
    """
    if not isinstance(data, Mapping):
        raise ManifestError("Manifest root must be a mapping.")

    version = data.get(_VERSION_FIELD)
    if version is None:
        raise ManifestError("Manifest is missing the required 'version' field.")

    # ``bool`` is a subclass of ``int`` but never a valid version; reject it too.
    if not isinstance(version, int) or isinstance(version, bool):
        raise ManifestError(
            f"Manifest 'version' must be an integer, got {type(version).__name__}."
        )

    model = _MANIFEST_MODELS.get(version)
    if model is None:
        supported = ", ".join(str(key) for key in sorted(_MANIFEST_MODELS))
        raise ManifestError(
            f"Unsupported manifest version: {version!r}. Supported versions: {supported}."
        )

    try:
        return model.model_validate(dict(data))
    except ValidationError as exc:
        raise ManifestError(f"Manifest validation failed:\n{exc}") from exc


def load_manifest(path: str | Path) -> Manifest:
    """Read and validate a YAML manifest from ``path``.

    Args:
        path: Filesystem path to the YAML manifest. A plain ``str`` is accepted
            and coerced to :class:`~pathlib.Path`.

    Returns:
        A validated manifest model.

    Raises:
        ManifestError: If the file cannot be read or parsed, or is invalid.
    """
    path = Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"Cannot read manifest '{path}': {exc}") from exc

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ManifestError(f"Invalid YAML in manifest '{path}': {exc}") from exc

    return parse_manifest(data)
