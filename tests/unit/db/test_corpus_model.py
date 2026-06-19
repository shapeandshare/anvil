"""Tests for Corpus ORM model."""

import pytest

from anvil.db.models.corpus import Corpus
from anvil.db.models.corpus_file import CorpusFile


class TestCorpusModel:
    def test_corpus_defaults(self):
        c = Corpus(
            name="test-corpus",
            root_path="/tmp/test",
            chunking_strategy="windowed",
            chunk_overlap=0.5,
            file_count=0,
            document_count=0,
        )
        assert c.name == "test-corpus"
        assert c.root_path == "/tmp/test"
        assert c.chunking_strategy == "windowed"
        assert c.chunk_overlap == 0.5
        assert c.file_count == 0
        assert c.document_count == 0
        assert c.include_patterns is None
        assert c.exclude_patterns is None
        assert c.language_map is None

    def test_corpus_custom_values(self):
        c = Corpus(
            name="custom",
            root_path="/tmp",
            chunking_strategy="line",
            chunk_overlap=0.0,
            include_patterns='["*.py"]',
        )
        assert c.chunking_strategy == "line"
        assert c.chunk_overlap == 0.0
        assert c.include_patterns == '["*.py"]'

    def test_corpus_relationships(self):
        c = Corpus(name="rel-test", root_path="/tmp",
                    chunking_strategy="line", chunk_overlap=0.0)
        cf = CorpusFile(
            corpus=c,
            relative_path="src/main.py",
            language="Python",
        )
        assert cf in c.files
        assert cf.corpus is c


class TestCorpusFileModel:
    def test_corpus_file_defaults(self):
        cf = CorpusFile(
            corpus_id=1,
            relative_path="test.py",
        )
        assert cf.corpus_id == 1
        assert cf.relative_path == "test.py"
        assert cf.language is None
        assert cf.line_count is None

    def test_corpus_file_with_stats(self):
        cf = CorpusFile(
            corpus_id=1,
            relative_path="utils.py",
            language="Python",
            line_count=50,
            char_count=1200,
            chunk_count=5,
            encoding="utf-8",
            size_bytes=1400,
        )
        assert cf.language == "Python"
        assert cf.line_count == 50
        assert cf.chunk_count == 5