# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for CorpusLoader — directory walk, pattern filtering, chunk orchestration."""

import tempfile
from pathlib import Path

import pytest

from anvil.services.datasets.corpus_loader import (
    CorpusLoader,
    _build_spec,
    detect_language,
)


def test_detect_language():
    assert detect_language("main.py") == "Python"
    assert detect_language("README.md") == "Markdown"
    assert detect_language("script.js") == "JavaScript"
    assert detect_language("unknown.xyz") is None
    assert detect_language("noext") is None


def test_build_spec_defaults():
    spec = _build_spec(None, None)
    assert spec.match_file("main.py") is True
    assert spec.match_file("README.md") is True
    assert spec.match_file(".git/HEAD") is False
    assert spec.match_file("node_modules/pkg/index.js") is False
    assert spec.match_file("image.png") is False


def test_build_spec_custom_include():
    spec = _build_spec(include_patterns=["*.py"], exclude_patterns=None)
    assert spec.match_file("main.py") is True
    assert spec.match_file("README.md") is False


def test_build_spec_custom_exclude():
    spec = _build_spec(include_patterns=None, exclude_patterns=["tests/"])
    assert spec.match_file("main.py") is True
    assert spec.match_file("tests/test_main.py") is False


@pytest.fixture
def sample_dir():
    with tempfile.TemporaryDirectory() as td:
        for name, content in [
            ("main.py", "def hello():\n    pass\n"),
            ("utils.py", "import os\n"),
            ("README.md", "# Project\nDocs here.\n"),
            ("image.png", b"\x89PNG\r\n\x1a\n"),
            (".hidden", "secret"),
        ]:
            p = Path(td) / name
            if isinstance(content, bytes):
                p.write_bytes(content)
            else:
                p.write_text(content)
        (Path(td) / ".git").mkdir()
        (Path(td) / ".git" / "HEAD").write_text("ref: main\n")
        yield td


class TestCorpusLoaderIntegration:
    def test_basic_ingest(self, sample_dir):
        loader = CorpusLoader(block_size=16)
        result = loader.ingest(sample_dir)

        paths = {f["relative_path"] for f in result.files}
        assert "main.py" in paths
        assert "utils.py" in paths
        assert "README.md" in paths
        assert ".hidden" not in paths
        assert ".git/HEAD" not in paths
        assert "image.png" not in paths

        assert result.language_map.get("Python", 0) >= 2
        assert result.language_map.get("Markdown", 0) >= 1

    def test_include_patterns(self, sample_dir):
        loader = CorpusLoader(block_size=16)
        result = loader.ingest(sample_dir, include_patterns=["*.py"])
        paths = {f["relative_path"] for f in result.files}
        assert "main.py" in paths
        assert "utils.py" in paths
        assert "README.md" not in paths

    def test_exclude_patterns(self, sample_dir):
        loader = CorpusLoader(block_size=16)
        result = loader.ingest(sample_dir, exclude_patterns=["utils.py"])
        paths = {f["relative_path"] for f in result.files}
        assert "main.py" in paths
        assert "utils.py" not in paths

    def test_line_chunking_strategy(self, sample_dir):
        loader = CorpusLoader(block_size=16)
        result = loader.ingest(
            sample_dir,
            include_patterns=["README.md"],
            chunking_strategy="line",
        )
        # README has 2 non-empty lines
        for f in result.files:
            assert f["chunk_count"] == 2 if f["relative_path"] == "README.md" else True

    def test_file_chunking_strategy(self, sample_dir):
        loader = CorpusLoader(block_size=16)
        result = loader.ingest(
            sample_dir,
            include_patterns=["README.md"],
            chunking_strategy="file",
        )
        for f in result.files:
            assert f["chunk_count"] == 1

    def test_zero_matching_files(self, sample_dir):
        loader = CorpusLoader(block_size=16)
        result = loader.ingest(sample_dir, include_patterns=["*.xyz"])
        assert len(result.files) == 0
        assert result.total_docs == 0

    def test_non_utf8_skipped(self, sample_dir):
        loader = CorpusLoader(block_size=16)
        loader.ingest(sample_dir)
        td = tempfile.mkdtemp()
        try:
            p = Path(td) / "binary.bin"
            p.write_bytes(b"\xff\xfe\x00\x01")
            result2 = loader.ingest(td, include_patterns=["*.bin"])
            assert len(result2.files) == 0
        finally:
            import shutil

            shutil.rmtree(td)

    def test_max_files_limit(self, sample_dir):
        loader = CorpusLoader(block_size=16)
        result = loader.ingest(sample_dir, max_files=1)
        assert len(result.files) <= 1


class TestCorpusLoaderScan:
    def test_scan_basic(self, sample_dir):
        loader = CorpusLoader()
        result = loader.scan(sample_dir)
        assert result.file_count > 0
        assert result.total_bytes > 0
        assert len(result.sizes) == result.file_count

    def test_scan_empty_dir(self, tmp_path):
        loader = CorpusLoader()
        result = loader.scan(str(tmp_path))
        assert result.file_count == 0
        assert result.total_bytes == 0

    def test_scan_with_include(self, sample_dir):
        loader = CorpusLoader()
        result = loader.scan(sample_dir, include_patterns=["*.py"])
        assert result.file_count >= 2

    def test_scan_max_files(self, sample_dir):
        loader = CorpusLoader()
        result = loader.scan(sample_dir, max_files=1)
        assert result.file_count <= 1

    def test_scan_not_a_directory(self, sample_dir):
        loader = CorpusLoader()
        f = Path(sample_dir) / "main.py"
        import pytest
        with pytest.raises(NotADirectoryError):
            loader.scan(str(f))

    def test_scan_nonexistent(self, sample_dir):
        loader = CorpusLoader()
        import pytest
        with pytest.raises(NotADirectoryError):
            loader.scan("/nonexistent/path")


class TestCorpusLoaderEdgeCases:
    def test_make_chunker_invalid_strategy(self, sample_dir):
        loader = CorpusLoader()
        chunker = loader._make_chunker("windowed", 0.5)
        from anvil.services.chunking.window_chunker import FixedSizeWindowChunker
        assert isinstance(chunker, FixedSizeWindowChunker)

    def test_ingest_not_a_directory(self, tmp_path):
        loader = CorpusLoader()
        f = tmp_path / "file.txt"
        f.write_text("hello")
        import pytest
        with pytest.raises(NotADirectoryError):
            loader.ingest(str(f))
