from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Set

from .config import Config
from .tree import build_ascii_tree

try:
    import pathspec
except Exception:
    pathspec = None


def is_text_file(path: Path, blocksize: int = 8192) -> bool:
    try:
        with path.open("rb") as f:
            return b"\0" not in f.read(blocksize)
    except OSError:
        return False


def lang_from_suffix(path: Path) -> str:
    return path.suffix[1:] or "text"


def is_ignored_path(path: Path, cfg: Config, allowed_by_git: Optional[set[Path]], pspec) -> bool:
    rel = path.relative_to(cfg.root)

    if cfg.respect_gitignore:
        if allowed_by_git is not None and path.is_file():
            return path not in allowed_by_git
        if pspec is not None:
            if pspec.match_file(rel.as_posix()):
                return True
    
    # directories / files excluded by patterns
    for pat in cfg.filters.exclude:
        if rel.match(pat):
            return True
    
    # include list: if present, anything not matched is "ignored"
    if cfg.filters.include:
        if path.is_dir():
            # leave dirs alone; we decide by children/files later,
            # but to mark the dir in tree we can treat it as ignored if it doesn't match any include.
            if not any(rel.match(p) for p in cfg.filters.include):
                return True
        else:
            if not any(rel.match(p) for p in cfg.filters.include):
                return True
            
    if path.suffix in cfg.ignore_extensions:
        return True
    
    return False


def _git_non_ignored_files(root: Path) -> Optional[set[Path]]:
    """Return the set of files NOT ignored by .gitignore using git itself, or None if not available."""
    if not (root / ".git").exists():
        return None
    if shutil.which("git") is None:
        return None
    try:
        # List tracked (-c) and others (-o) but exclude standard ignores:
        out = subprocess.check_output(
            ["git", "ls-files", "-co", "--exclude-standard"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return {root / line.strip() for line in out.splitlines() if line.strip()}
    except Exception:
        return None


def _pathspec_from_gitignore(root: Path):
    if pathspec is None:
        return None
    gi = root / ".gitignore"
    if not gi.exists():
        return None
    with gi.open("r", encoding="utf-8", errors="ignore") as f:
        return pathspec.PathSpec.from_lines("gitwildmatch", f.readlines())


def should_include(path: Path, cfg: Config, allowed_by_git: Optional[Set[Path]], pspec) -> bool:
    """
    Inclusion decision for FILES. Directories are handled by the tree builder.
    """
    return not is_ignored_path(path, cfg, allowed_by_git, pspec)


def write_markdown(cfg: Config) -> None:
    cfg.root = cfg.root.resolve()
    cfg.output = cfg.output.resolve()

    allowed_by_git = _git_non_ignored_files(cfg.root) if cfg.respect_gitignore else None
    pspec = _pathspec_from_gitignore(cfg.root) if (allowed_by_git is None and cfg.respect_gitignore) else None


    def is_dir_ignored(p: Path) -> bool:
        return is_ignored_path(p, cfg, allowed_by_git, pspec)

    with cfg.output.open("w", encoding="utf-8") as out:
        out.write(cfg.format.preamble.format(root=cfg.root))
        out.write(f"# Flattened view of `{cfg.root}`\n\n")

        if cfg.include_tree:
            out.write("## Directory tree\n\n```\n")
            out.write(build_ascii_tree(cfg.root, cfg.tree_depth, is_dir_ignored=is_dir_ignored))
            out.write("\n```\n\n")
            out.write("_* = ignored directory (contents not listed)_\n\n")

        for dirpath, _, filenames in os.walk(cfg.root):
            for name in sorted(filenames):
                p = Path(dirpath, name)
                if not is_text_file(p):
                    continue
                if not should_include(p, cfg, allowed_by_git, pspec):
                    continue

                rel = p.relative_to(cfg.root)
                heading = cfg.format.heading.format(path=rel.as_posix())
                out.write(f"{heading}\n")
                lang = lang_from_suffix(p) if cfg.format.fence_language_from_extension else ""
                out.write(f"```{lang}\n")
                out.write(p.read_text(encoding="utf-8", errors="ignore"))
                out.write("\n```\n\n")
