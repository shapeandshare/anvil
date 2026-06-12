"""Directory walker and document chunker for training corpora."""

from __future__ import annotations

import os
from pathlib import Path

from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from microgpt.services.chunking import (
    Chunker,
    FileAsDocChunker,
    FixedSizeWindowChunker,
    LineAsDocChunker,
)

DEFAULT_EXCLUDE_PATTERNS = [
    ".git/",
    "__pycache__/",
    "node_modules/",
    "venv/",
    ".venv/",
    ".env/",
    ".hg/",
    ".svn/",
    "build/",
    "dist/",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dll",
    "*.dylib",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.woff",
    "*.ttf",
    "*.exe",
    ".DS_Store",
]

DEFAULT_INCLUDE_PATTERNS = [
    "*.py",
    "*.js",
    "*.ts",
    "*.go",
    "*.rs",
    "*.java",
    "*.md",
    "*.txt",
    "*.yaml",
    "*.yml",
    "*.json",
    "*.css",
    "*.html",
    "*.sh",
    "*.rb",
    "*.c",
    "*.cpp",
    "*.h",
    "*.hpp",
]

_LANGUAGE_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".md": "Markdown",
    ".txt": "Text",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".css": "CSS",
    ".html": "HTML",
    ".sh": "Shell",
    ".rb": "Ruby",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C",
    ".hpp": "C++",
}


def detect_language(file_path: str) -> str | None:
    ext = Path(file_path).suffix.lower()
    return _LANGUAGE_MAP.get(ext)


def _build_spec(
    include_patterns: list[str] | None,
    exclude_patterns: list[str] | None,
) -> PathSpec:
    patterns = list(DEFAULT_INCLUDE_PATTERNS)
    if include_patterns:
        patterns = include_patterns
    exclude = list(DEFAULT_EXCLUDE_PATTERNS)
    if exclude_patterns:
        exclude.extend(exclude_patterns)
    negated = [f"!{p}" for p in exclude]
    return PathSpec.from_lines(GitWildMatchPattern, patterns + negated)


class CorpusLoadResult:
    def __init__(
        self,
        files: list[dict],
        total_docs: int,
        language_map: dict[str, int],
        errors: list[str],
    ):
        self.files = files
        self.total_docs = total_docs
        self.language_map = language_map
        self.errors = errors


class CorpusLoader:
    def __init__(self, block_size: int = 16):
        self._block_size = block_size

    def _make_chunker(self, strategy: str, overlap: float) -> Chunker:
        if strategy == "line":
            return LineAsDocChunker()
        if strategy == "file":
            return FileAsDocChunker()
        return FixedSizeWindowChunker(
            block_size=self._block_size, overlap=overlap
        )

    def ingest(
        self,
        root_path: str,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        chunking_strategy: str = "windowed",
        chunk_overlap: float = 0.5,
        max_files: int = 10000,
    ) -> CorpusLoadResult:
        root = Path(root_path).resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {root_path}")

        spec = _build_spec(include_patterns, exclude_patterns)
        chunker = self._make_chunker(chunking_strategy, chunk_overlap)

        files: list[dict] = []
        total_docs = 0
        language_map: dict[str, int] = {}
        errors: list[str] = []
        file_count = 0

        for abs_path in root.rglob("*"):
            if not abs_path.is_file():
                continue

            rel = str(abs_path.relative_to(root))

            if not spec.match_file(rel):
                continue

            if file_count >= max_files:
                errors.append(
                    f"Reached max file limit ({max_files}), stopping walk"
                )
                break

            stat = abs_path.stat()

            try:
                text = abs_path.read_text("utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                errors.append(f"Skipped {rel}: {exc}")
                continue

            chunks = chunker.chunk(text)
            lang = detect_language(rel)
            if lang:
                language_map[lang] = language_map.get(lang, 0) + 1

            files.append(
                {
                    "relative_path": rel,
                    "language": lang,
                    "line_count": len(text.splitlines()),
                    "char_count": len(text),
                    "chunk_count": len(chunks),
                    "encoding": "utf-8",
                    "size_bytes": stat.st_size,
                    "last_modified": stat.st_mtime,
                }
            )
            total_docs += len(chunks)
            file_count += 1

        return CorpusLoadResult(
            files=files,
            total_docs=total_docs,
            language_map=language_map,
            errors=errors,
        )