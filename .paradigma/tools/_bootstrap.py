"""Locate the installable package for source-tree compatibility entrypoints."""

from __future__ import annotations

from pathlib import Path
import sys


def ensure_package() -> Path:
    repository_root = Path(__file__).resolve().parents[2]
    source_root = repository_root / "src"
    if source_root.exists() and str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    adapter_root = repository_root / "scripts"
    if (adapter_root / "paradigma_adapter.py").is_file():
        sys.path.insert(0, str(adapter_root))
        from paradigma_adapter import install
        install()
    from paradigma.cli.output import configure_utf8_stdio

    configure_utf8_stdio()
    return repository_root
