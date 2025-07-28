from __future__ import annotations
from pathlib import Path
from typing import Callable, Optional


def build_ascii_tree(root: Path, max_depth: int = 0, is_dir_ignored: Optional[Callable[[Path], bool]] = None) -> str:
    lines = [str(root)]
    prefix_stack: list[str] = []

    def walk(dir_path: Path, depth: int):
        if max_depth and depth > max_depth:
            return
        try:
            entries = sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            branch = "└── " if is_last else "├── "
            ignored = entry.is_dir() and is_dir_ignored and is_dir_ignored(entry)
            label = entry.name + (" *" if ignored else "")
            lines.append("".join(prefix_stack) + branch + label)

            if entry.is_dir() and not ignored:
                prefix_stack.append("    " if is_last else "│   ")
                walk(entry, depth + 1)
                prefix_stack.pop()
    
    walk(root, 1)
    return "\n".join(lines)