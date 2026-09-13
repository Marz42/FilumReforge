"""Filum-specific adapter for pinned Paradigma 0.7.0; no site-package edits."""
from importlib.metadata import version
from pathlib import Path
import re


def install():
    from paradigma.application import versioning
    if getattr(versioning, "_filum_adapter", False):
        return
    if version("paradigma") != "0.7.0":
        raise RuntimeError("Filum adapter requires the pinned Paradigma 0.7.0; review before upgrading")
    original = versioning.read_distribution_version

    def read_distribution_version(root):
        root = Path(root).resolve()
        config = versioning.read_top_level_scalars(root / ".paradigma/config.yaml")
        configured = config.get("filum_paradigma_version_file")
        if configured is None:
            return original(root)
        if configured != ".paradigma/VERSION":
            raise versioning.VersionModelError("unsupported Filum protocol version path")
        product = original(root)
        if not versioning.SEMVER_PATTERN.fullmatch(product):
            raise versioning.VersionModelError("Filum product VERSION is not SemVer")
        path = (root / configured).resolve()
        if not path.is_relative_to(root):
            raise versioning.VersionModelError("protocol version path escapes repository")
        if not path.is_file():
            raise versioning.VersionModelError("missing .paradigma/VERSION")
        value = path.read_text(encoding="utf-8-sig").strip()
        if not value:
            raise versioning.VersionModelError("empty .paradigma/VERSION")
        return value

    versioning.read_distribution_version = read_distribution_version
    versioning._filum_adapter = True
