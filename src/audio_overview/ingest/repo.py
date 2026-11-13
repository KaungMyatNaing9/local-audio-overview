"""Summarize a local directory: README, a file tree, and excerpts of key files.

The script is grounded on this summary. Facts that live only in files we did
not open are outside the episode on purpose.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from audio_overview.errors import AudioOverviewError
from audio_overview.ingest.document import parse_markdown, render_document
from audio_overview.types import Document, Section

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "site-packages",
    "models",
    ".cache",
}
README_NAMES = ("README.md", "README.rst", "README.txt", "README")
MANIFESTS = {
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "setup.py",
    "setup.cfg",
    "composer.json",
}
PRIORITY_NAMES = {
    "main.py",
    "__main__.py",
    "app.py",
    "cli.py",
    "main.ts",
    "index.ts",
    "lib.rs",
    "main.go",
    "main.rs",
}
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".rs",
    ".go",
    ".java",
    ".rb",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".md",
    ".markdown",
    ".rst",
    ".txt",
    ".toml",
    ".json",
    ".yml",
    ".yaml",
}
_PY_DEF = re.compile(r"^(?:async\s+def|def|class)\s+\w+", re.MULTILINE)
_PY_DOC = re.compile(r'^"""(.*?)"""', re.DOTALL)
_MAX_FILE_BYTES = 200_000
_EXCERPT_CHARS = 4_000
_README_CHARS = 12_000
_MAX_CODE_FILES = 8
_MAX_TREE = 200


def ingest_repo(path: Path) -> Document:
    root = path.resolve()
    if not root.is_dir():
        raise AudioOverviewError(f"{path} is not a directory.")
    files = _list_files(root)
    readme_path = _find_readme(root, files)
    readme_text = _read(readme_path) if readme_path else ""
    title = root.name
    readme_body = ""
    if readme_text:
        parsed_title, _sections = parse_markdown(readme_text)
        title = parsed_title or title
        readme_body = readme_text.strip()[:_README_CHARS]
    sections: list[Section] = [Section("File tree", _tree(root, files), 2)]
    if readme_body:
        sections.append(Section("README", readme_body, 2))
    for manifest in _manifests(root, files):
        body = _read(manifest)
        if body.strip():
            rel = manifest.relative_to(root).as_posix()
            sections.append(Section(rel, body.strip()[:_EXCERPT_CHARS], 2))
    used = {readme_path, *_manifests(root, files)}
    for code_path in _key_code(root, files)[:_MAX_CODE_FILES]:
        if code_path in used:
            continue
        excerpt = _excerpt(code_path)
        if not excerpt:
            continue
        rel = code_path.relative_to(root).as_posix()
        sections.append(Section(rel, excerpt, 2))
    body_sections = [section for section in sections if section.text.strip()]
    if len(body_sections) <= 1 and not readme_body:
        raise AudioOverviewError(
            f"No README or source files to summarize in {path}. "
            "V1 skips dependency folders, hidden files, and binaries."
        )
    git = "yes" if (root / ".git").exists() else "no"
    return Document(
        title=title,
        text=render_document(title, body_sections),
        source=str(root),
        kind="repo",
        sections=tuple(body_sections),
        metadata={"git": git, "files_seen": str(len(files))},
    )


def _list_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS and not name.startswith("."))
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            found.append(Path(dirpath) / name)
    return found


def _find_readme(root: Path, files: list[Path]) -> Path | None:
    by_name = {path.relative_to(root).as_posix(): path for path in files}
    for name in README_NAMES:
        if name in by_name:
            return by_name[name]
    return None


def _manifests(root: Path, files: list[Path]) -> list[Path]:
    found = [path for path in files if path.name in MANIFESTS and len(path.relative_to(root).parts) <= 2]
    return sorted(found, key=lambda path: path.name)


def _key_code(root: Path, files: list[Path]) -> list[Path]:
    code = [
        path
        for path in files
        if path.suffix.lower() in TEXT_SUFFIXES
        and path.name not in MANIFESTS
        and path.name not in README_NAMES
    ]

    def rank(path: Path) -> tuple[int, int, str]:
        rel = path.relative_to(root).as_posix()
        priority = 0 if path.name in PRIORITY_NAMES else 1
        return (priority, len(path.relative_to(root).parts), rel)

    return sorted(code, key=rank)


def _tree(root: Path, files: list[Path]) -> str:
    lines = [path.relative_to(root).as_posix() for path in files]
    if len(lines) > _MAX_TREE:
        extra = len(lines) - _MAX_TREE
        lines = lines[:_MAX_TREE]
        lines.append(f"further files omitted: {extra}")
    return "\n".join(lines) if lines else "(no files)"


def _read(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in README_NAMES:
        return ""
    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return ""
        data = path.read_bytes()
    except OSError:
        return ""
    if b"\x00" in data:
        return ""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return ""


def _excerpt(path: Path) -> str:
    text = _read(path)
    if not text.strip():
        return ""
    if path.suffix.lower() == ".py":
        summary = _python_summary(text)
        if summary:
            return summary[:_EXCERPT_CHARS]
    return text.strip()[:_EXCERPT_CHARS]


def _python_summary(text: str) -> str:
    parts: list[str] = []
    doc = _PY_DOC.search(text.lstrip())
    if doc and doc.group(1).strip():
        parts.append(doc.group(1).strip())
    defs = _PY_DEF.findall(text)
    if defs:
        parts.append("\n".join(defs))
    if parts:
        return "\n\n".join(parts)
    return ""
