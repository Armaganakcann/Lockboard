"""Tests for manifest parsing, validation and version dispatch."""

from __future__ import annotations

import pytest

from aios.exceptions import ManifestError
from aios.manifest import ManifestV1, load_manifest, parse_manifest


def test_parse_valid_manifest():
    data = {"version": 1, "component": {"module": "pkg.mod", "class": "Cls"}}
    manifest = parse_manifest(data)
    assert isinstance(manifest, ManifestV1)
    assert manifest.component.module == "pkg.mod"
    assert manifest.component.class_name == "Cls"


def test_missing_version_raises():
    with pytest.raises(ManifestError):
        parse_manifest({"component": {"module": "m", "class": "C"}})


def test_unsupported_version_raises():
    with pytest.raises(ManifestError):
        parse_manifest({"version": 99, "component": {"module": "m", "class": "C"}})


def test_extra_field_forbidden():
    with pytest.raises(ManifestError):
        parse_manifest(
            {"version": 1, "component": {"module": "m", "class": "C", "extra": 1}}
        )


def test_non_mapping_root_raises():
    with pytest.raises(ManifestError):
        parse_manifest(["not", "a", "mapping"])


def test_version_wrong_type_raises():
    with pytest.raises(ManifestError):
        parse_manifest({"version": [1], "component": {"module": "m", "class": "C"}})


def test_version_bool_raises():
    with pytest.raises(ManifestError):
        parse_manifest({"version": True, "component": {"module": "m", "class": "C"}})


def test_missing_component_raises():
    with pytest.raises(ManifestError):
        parse_manifest({"version": 1})


def test_load_manifest_from_file(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text("version: 1\ncomponent:\n  module: m\n  class: C\n", encoding="utf-8")
    manifest = load_manifest(path)
    assert manifest.component.class_name == "C"


def test_load_manifest_missing_file(tmp_path):
    with pytest.raises(ManifestError):
        load_manifest(tmp_path / "nope.yaml")


def test_load_manifest_accepts_str(tmp_path):
    path = tmp_path / "m.yaml"
    path.write_text("version: 1\ncomponent:\n  module: m\n  class: C\n", encoding="utf-8")
    manifest = load_manifest(str(path))
    assert manifest.component.module == "m"


def test_load_manifest_empty_file_raises(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)


def test_load_manifest_invalid_yaml(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("version: 1\n  bad: : :\n", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)
