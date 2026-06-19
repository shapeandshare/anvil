"""Unit tests for the guarded-imports checker.

Tests that check_guarded_imports.py correctly flags TYPE_CHECKING-guarded
symbols used in runtime (non-annotation) code, and passes annotation-only
usage. Follows TDD per the constitution mandate.
"""

from scripts.ci.check_guarded_imports import (
    GuardedImportIssue,
    _extract_guarded_imports,
    _find_runtime_usages,
)


class TestExtractGuardedImports:
    """Tests for extracting TYPE_CHECKING imports from source."""

    def test_detects_guarded_import(self) -> None:
        """A TYPE_CHECKING guard block with a regular import is detected."""
        source = """
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .somewhere import SomeClass

class Foo:
    x: SomeClass | None = None
"""
        imports = _extract_guarded_imports(source, "test.py")
        assert len(imports) == 1
        assert imports[0].symbol == "SomeClass"

    def test_no_guard_is_empty(self) -> None:
        """A file with no TYPE_CHECKING guard returns nothing."""
        source = """
import os
from pathlib import Path

class Foo:
    pass
"""
        imports = _extract_guarded_imports(source, "test.py")
        assert len(imports) == 0


class TestFindRuntimeUsages:
    """Tests for detecting guarded symbols used outside annotations."""

    def test_annotation_only_passes(self) -> None:
        """A guarded symbol used only in type annotations is clean."""
        source = """
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .corpus import Corpus

class File:
    parent: Corpus | None = None
"""
        issues = _find_runtime_usages(source, {"Corpus"}, "test.py")
        assert len(issues) == 0

    def test_runtime_usage_is_flagged(self) -> None:
        """A guarded symbol used in a runtime context (not annotation) is an issue."""
        source = """
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .corpus import Corpus

class File:
    def get(self) -> None:
        c = Corpus()  # runtime instantiation — should be flagged
"""
        issues = _find_runtime_usages(source, {"Corpus"}, "test.py")
        assert len(issues) == 1
        assert issues[0].symbol == "Corpus"

    def test_only_annotation_without_future(self) -> None:
        """If from __future__ import annotations is absent, annotations
        ARE runtime and should be flagged."""
        source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .corpus import Corpus

class File:
    parent: "Corpus" = None
"""
        issues = _find_runtime_usages(source, {"Corpus"}, "test.py")
        assert len(issues) == 1
