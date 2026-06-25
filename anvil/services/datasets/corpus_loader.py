# Copyright © 2026 Josh Burt
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""Directory walker and document chunker for training corpora.

Provides the ``CorpusLoader`` class which walks a directory tree,
filters files by include/exclude patterns, and chunks text content
using pluggable chunking strategies (line, file, or fixed-size window).
"""

from pathlib import Path
from typing import Any

from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from ..chunking.base import Chunker
from ..chunking.file_chunker import FileAsDocChunker
from ..chunking.line_chunker import LineAsDocChunker
from ..chunking.window_chunker import FixedSizeWindowChunker
from .chunking_strategy import ChunkingStrategy
from .corpus_load_result import CorpusLoadResult
from .corpus_scan_result import CorpusScanResult

# Default glob patterns for files to always exclude from ingestion.
DEFAULT_EXCLUDE_PATTERNS: list[str] = [
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

# Default glob patterns for files to include during ingestion.
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

# Mapping from file extension to human-readable language label.
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
    """Detect the programming language of a file from its extension.

    Parameters
    ----------
    file_path : str
        Path to the file (extension is extracted for lookup).

    Returns
    -------
    str or None
        The language label (e.g. ``"Python"``) or ``None`` if the
        extension is not recognised.
    """
    ext = Path(file_path).suffix.lower()
    return _LANGUAGE_MAP.get(ext)


def _build_spec(
    include_patterns: list[str] | None,
    exclude_patterns: list[str] | None,
) -> PathSpec:
    """Build a ``PathSpec`` from include/exclude glob patterns.

    Merges caller-provided patterns with sensible defaults. Exclude
    patterns are negated so that any file matching an exclude pattern
    will be filtered out.

    Parameters
    ----------
    include_patterns : list[str] or None
        Override patterns for files to include. ``None`` uses
        ``DEFAULT_INCLUDE_PATTERNS``.
    exclude_patterns : list[str] or None
        Additional patterns for files to exclude. ``None`` uses
        ``DEFAULT_EXCLUDE_PATTERNS`` only.

    Returns
    -------
    PathSpec
        Compiled specification ready for ``match_file`` calls.
    """
    patterns = list(DEFAULT_INCLUDE_PATTERNS)
    if include_patterns:
        patterns = include_patterns
    exclude = list(DEFAULT_EXCLUDE_PATTERNS)
    if exclude_patterns:
        exclude.extend(exclude_patterns)
    negated = [f"!{p}" for p in exclude]
    return PathSpec.from_lines(GitWildMatchPattern, patterns + negated)


class CorpusLoader:
    """Walks a directory tree, filters files, and chunks text for training.

    Uses ``pathspec`` for gitignore-style pattern matching and supports
    three chunking strategies: line-based, file-as-document, and
    fixed-size sliding window.
    """

    def __init__(self, block_size: int = 16):
        """Initialise the loader with a default block size.

        Parameters
        ----------
        block_size : int
            Default block size for windowed chunking. Defaults to ``16``.
        """
        self._block_size = block_size

    def _make_chunker(
        self,
        strategy: ChunkingStrategy | str,
        overlap: float,
        block_size: int | None = None,
    ) -> Chunker:
        """Factory method returning a chunker for the given strategy.

        Parameters
        ----------
        strategy : ChunkingStrategy or str
            Chunking strategy enum member or string value.
        overlap : float
            Overlap fraction for windowed chunking.
        block_size : int, optional
            Block size override. Falls back to ``self._block_size``.

        Returns
        -------
        Chunker
            An instance of the requested chunker.

        Raises
        ------
        ValueError
            If ``strategy`` is not recognised (fallback to windowed).
        """
        if isinstance(strategy, str):
            strategy = ChunkingStrategy(strategy)
        if strategy == ChunkingStrategy.LINE:
            return LineAsDocChunker()
        if strategy == ChunkingStrategy.FILE:
            return FileAsDocChunker()
        return FixedSizeWindowChunker(
            block_size=block_size or self._block_size, overlap=overlap
        )

    def ingest(
        self,
        root_path: str,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        chunking_strategy: ChunkingStrategy | str = ChunkingStrategy.WINDOWED,
        chunk_overlap: float = 0.5,
        max_files: int = 10000,
        block_size: int | None = None,
    ) -> CorpusLoadResult:
        """Walk a directory, ingest files, and return chunked document metadata.

        Recursively walks ``root_path``, filters files using the include/
        exclude patterns, reads text content, and chunks it using the
        selected strategy.

        Parameters
        ----------
        root_path : str
            Absolute path to the root directory to ingest.
        include_patterns : list[str], optional
            Override glob patterns for inclusion. ``None`` uses defaults.
        exclude_patterns : list[str], optional
            Additional glob patterns for exclusion.
        chunking_strategy : ChunkingStrategy or str
            Chunking strategy enum member or string value. Defaults to
            ``ChunkingStrategy.WINDOWED``.
        chunk_overlap : float
            Overlap fraction for windowed chunking. Defaults to ``0.5``.
        max_files : int
            Maximum number of files to process. Defaults to ``10000``.
        block_size : int, optional
            Block size override for windowed chunking. Falls back to
            ``self._block_size`` if not provided.

        Returns
        -------
        CorpusLoadResult
            Metadata about ingested files, total chunk count, language
            distribution, and any errors encountered.

        Raises
        ------
        NotADirectoryError
            If ``root_path`` does not exist or is not a directory.
        """
        root = Path(root_path).resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {root_path}")

        spec = _build_spec(include_patterns, exclude_patterns)
        chunker = self._make_chunker(chunking_strategy, chunk_overlap, block_size)

        files: list[dict[str, Any]] = []
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
                errors.append(f"Reached max file limit ({max_files}), stopping walk")
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

    def scan(
        self,
        root_path: str,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        max_files: int = 100000,
    ) -> CorpusScanResult:
        """Walk a directory and return file statistics without reading contents.

        Recursively walks ``root_path``, filters files using the
        include/exclude patterns, and collects file sizes and language
        distribution metadata. Does not read file contents.

        Parameters
        ----------
        root_path : str
            Absolute path to the root directory to scan.
        include_patterns : list[str], optional
            Override glob patterns for inclusion. ``None`` uses defaults.
        exclude_patterns : list[str], optional
            Additional glob patterns for exclusion.
        max_files : int
            Maximum number of files to process. Defaults to ``100000``.

        Returns
        -------
        CorpusScanResult
            File count, total bytes, individual sizes, and language
            distribution.

        Raises
        ------
        NotADirectoryError
            If ``root_path`` does not exist or is not a directory.
        """
        root = Path(root_path).resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {root_path}")

        spec = _build_spec(include_patterns, exclude_patterns)
        sizes: list[int] = []
        language_map: dict[str, int] = {}
        language_sizes: dict[str, list[int]] = {}
        file_count = 0

        for abs_path in root.rglob("*"):
            if not abs_path.is_file():
                continue
            rel = str(abs_path.relative_to(root))
            if not spec.match_file(rel):
                continue
            if file_count >= max_files:
                break

            stat = abs_path.stat()
            sizes.append(stat.st_size)
            lang = detect_language(rel)
            if lang:
                language_map[lang] = language_map.get(lang, 0) + 1
                if lang not in language_sizes:
                    language_sizes[lang] = []
                language_sizes[lang].append(stat.st_size)
            file_count += 1

        return CorpusScanResult(
            file_count=file_count,
            total_bytes=sum(sizes),
            sizes=sizes,
            language_map=language_map,
            language_sizes=language_sizes,
        )
