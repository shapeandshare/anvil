# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Tests for chunking strategies."""

from anvil.services.chunking.file_chunker import FileAsDocChunker
from anvil.services.chunking.line_chunker import LineAsDocChunker
from anvil.services.chunking.window_chunker import FixedSizeWindowChunker


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

    def test_overlap_zero_disjoint(self):
        c = FixedSizeWindowChunker(block_size=4, overlap=0.0)
        result = c.chunk("abcdefghijkl")
        assert result == ["abcd", "efgh", "ijkl"]

    def test_exact_stride_boundary(self):
        c = FixedSizeWindowChunker(block_size=4, overlap=0.5)
        result = c.chunk("abcdefghij")
        # stride=2, 10-char text => start positions 0,2,4,6,8 = 5 chunks
        assert len(result) == 5
        assert result[0] == "abcd"
        assert result[-1] == "ij"

    def test_partial_final_chunk(self):
        c = FixedSizeWindowChunker(block_size=4, overlap=0.5)
        result = c.chunk("abcdefghi")
        # stride=2, 9-char text => start positions 0,2,4,6,8 = 5 chunks
        assert len(result) == 5
        assert result[0] == "abcd"
        assert result[-1] == "i"
        assert len(result[-2]) < 4
        assert len(result[-1]) < 4

    def test_large_overlap_many_chunks(self):
        c = FixedSizeWindowChunker(block_size=4, overlap=0.9)
        result = c.chunk("abcdefghij")
        assert len(result) == 10
        for chunk in result:
            assert len(chunk) <= 4

    def test_block_size_one(self):
        c = FixedSizeWindowChunker(block_size=1, overlap=0.0)
        result = c.chunk("abcde")
        assert result == ["a", "b", "c", "d", "e"]

    def test_long_text_correct_chunk_count(self):
        c = FixedSizeWindowChunker(block_size=100, overlap=0.5)
        result = c.chunk("x" * 500)
        assert len(result) == 10

    def test_chunks_within_block_size(self):
        c = FixedSizeWindowChunker(block_size=7, overlap=0.3)
        result = c.chunk("hello world this is a test of the chunker")
        for chunk in result:
            assert len(chunk) <= 7

    def test_stride_bottoms_at_one(self):
        c = FixedSizeWindowChunker(block_size=5, overlap=0.99)
        text = "abcdefghij"
        result = c.chunk(text)
        # stride = max(1, int(5*0.01)) = max(1,0) = 1 => 10 chunks from 10-char text
        assert len(result) == 10
        assert len(result[0]) == 5
        assert len(result[-1]) == 1


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
