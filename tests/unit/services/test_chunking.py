"""Tests for chunking strategies."""

from microgpt.services.chunking.line_chunker import LineAsDocChunker
from microgpt.services.chunking.window_chunker import FixedSizeWindowChunker
from microgpt.services.chunking.file_chunker import FileAsDocChunker


class TestLineAsDocChunker:
    def test_empty(self):
        c = LineAsDocChunker()
        assert c.chunk("") == []

    def test_single_line(self):
        c = LineAsDocChunker()
        assert c.chunk("hello") == ["hello"]

    def test_multiple_lines(self):
        c = LineAsDocChunker()
        assert c.chunk("a\nb\nc") == ["a", "b", "c"]

    def test_skips_blank_lines(self):
        c = LineAsDocChunker()
        assert c.chunk("a\n\n\nb") == ["a", "b"]

    def test_strips_whitespace(self):
        c = LineAsDocChunker()
        assert c.chunk("  a  \n  b  ") == ["a", "b"]


class TestFixedSizeWindowChunker:
    def test_empty(self):
        c = FixedSizeWindowChunker(block_size=4)
        assert c.chunk("") == []

    def test_shorter_than_block(self):
        c = FixedSizeWindowChunker(block_size=10)
        result = c.chunk("hi")
        assert result == ["hi"]

    def test_exact_block(self):
        c = FixedSizeWindowChunker(block_size=4, overlap=0)
        result = c.chunk("abcdefgh")
        assert result == ["abcd", "efgh"]

    def test_with_overlap(self):
        c = FixedSizeWindowChunker(block_size=4, overlap=0.5)
        result = c.chunk("abcdefgh")
        assert len(result) > 1
        assert "abcd" in result
        assert "cdef" in result or "efgh" in result

    def test_invalid_overlap_raises(self):
        import pytest
        with pytest.raises(ValueError):
            FixedSizeWindowChunker(block_size=4, overlap=1.0)
        with pytest.raises(ValueError):
            FixedSizeWindowChunker(block_size=4, overlap=-0.1)

    def test_invalid_block_size_raises(self):
        import pytest
        with pytest.raises(ValueError):
            FixedSizeWindowChunker(block_size=0)


class TestFileAsDocChunker:
    def test_empty(self):
        c = FileAsDocChunker()
        assert c.chunk("") == []

    def test_single_doc(self):
        c = FileAsDocChunker()
        result = c.chunk("hello\nworld")
        assert result == ["hello\nworld"]

    def test_preserves_newlines(self):
        c = FileAsDocChunker()
        result = c.chunk("line1\nline2\nline3")
        assert result == ["line1\nline2\nline3"]