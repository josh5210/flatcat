from __future__ import annotations
from pathlib import Path
from typing import List, Optional

from .config import Config

try:
    import pathspec
except Exception:
    pathspec = None


def is_text_file(path: Path) -> bool:
    """
    Check if a file is likely text.
    """
    try:
        # Skip very large files (>10MB) early
        if path.stat().st_size > 10 * 1024 * 1024:  # 10MB limit
            return False
        
        # An empty file is considered text
        if path.stat().st_size == 0:
            return True
        
        with path.open("rb") as f:
            # Read a small chunk to check for null bytes (indicates binary)
            chunk = f.read(1024)
            if b'\0' in chunk:
                return False
    except (OSError, PermissionError):
        return False
    
    # If it looks like text, try decoding a small sample
    try:
        path.open("r", encoding="utf-8").read(1024)
        return True
    except UnicodeDecodeError:
        return False
    except (OSError, PermissionError):
        return False


def lang_from_suffix(path: Path) -> str:
    return path.suffix[1:] or "text"


def get_gitignore_spec(root: Path) -> Optional[pathspec.PathSpec]:
    """
    Load and parse .gitignore files, returning a PathSpec object
    """
    if pathspec is None:
        return None
    
    gitignore_file = root / ".gitignore"
    if not gitignore_file.exists():
        return None
    
    try:
        with gitignore_file.open("r", encoding="utf-8") as f:
            return pathspec.PathSpec.from_lines("gitwildmatch", f)
    except Exception:
        return None
    
    
def write_markdown(cfg: Config) -> None:
    if pathspec is None:
        raise ImportError("Please install 'pathspec' for full functionality: pip install pathspec")
    
    cfg.root = cfg.root.resolve()
    cfg.output = cfg.output.resolve()

    # Pathspec compilation
    # Compile include/exclude patterns from the config for efficient matching.
    include_spec = pathspec.PathSpec.from_lines("gitwildmatch", cfg.filters.include)
    exclude_spec = pathspec.PathSpec.from_lines("gitwildmatch", cfg.filters.exclude)
    gitignore_spec = get_gitignore_spec(cfg.root) if cfg.respect_gitignore else None

    files_to_render: List[Path] = []
    tree_lines: List[str] = [str(cfg.root)]

    # Single Recursive Directory Walk
    # This function walks the tree once, collecting files and building the tree string.
    def walk(dir_path: Path, depth: int, prefix_stack: List[str]):
        if cfg.tree_depth > 0 and depth >= cfg.tree_depth:
            return
        
        try:
            # Sort entries to ensure consistent order. Directories come first.
            entries = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        except (OSError, PermissionError):
            return
        
        for i, entry in enumerate(entries):
            rel_path = entry.relative_to(cfg.root)
            rel_posix = rel_path.as_posix()

            # Ignore logic
            is_ignored = False
            if exclude_spec.match_file(rel_posix):
                is_ignored = True
            if gitignore_spec and gitignore_spec.match_file(rel_posix):
                is_ignored = True
            if cfg.filters.include and not include_spec.match_file(rel_posix):
                # IF an include list exists, non-matching files are ignored
                is_ignored = True
            
            # Tree Building
            if cfg.include_tree:
                is_last = i == len(entries) - 1
                branch = "└── " if is_last else "├── "
                label = entry.name + (" *" if is_ignored and entry.is_dir() else "")
                tree_lines.append("".join(prefix_stack) + branch + label)

            if is_ignored:
                continue

            # Files and Directory Handling
            if entry.is_dir():
                if cfg.include_tree:
                    prefix_stack.append("    " if is_last else "│   ")
                walk(entry, depth + 1, prefix_stack)
                if cfg.include_tree:
                    prefix_stack.pop()
            elif entry.is_file():
                if entry.suffix in cfg.ignore_extensions:
                    continue
                if not is_text_file(entry):
                    continue
                files_to_render.append(entry)

    walk(cfg.root, 0, [])

    # Writing output file
    with cfg.output.open("w", encoding="utf-8", errors="replace") as out:
        out.write(cfg.format.preamble.format(root=cfg.root.name))
        out.write(f"\n\n# Flattened view of `{cfg.root.name}`\n\n")

        if cfg.include_tree:
            out.write("## Directory tree\n\n")
            out.write("```\n")
            out.write("\n".join(tree_lines))
            out.write("\n```\n\n")
            out.write("_Directories marked with '*' are ignored._\n\n")

        out.write("## File Contents\n\n")
        for p in sorted(files_to_render):
            rel = p.relative_to(cfg.root)
            heading = cfg.format.heading.format(path=rel.as_posix())
            out.write(f"{heading}\n")

            lang = lang_from_suffix(p) if cfg.format.fence_language_from_extension else ""
            out.write(f"```{lang}\n")

            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                # Truncate very long files to prevent overwhelming the output.
                if len(content) > 150000:   # 150k char limit
                    content = content[:150000] + "\n\n... (file truncated)"
                out.write(content.strip())
            except (OSError, PermissionError):
                out.write("(Error reading file)")
            
            out.write("\n```\n\n")
                
    
