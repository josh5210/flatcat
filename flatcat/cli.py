from __future__ import annotations
import argparse
from pathlib import Path

from .config import Config, DEFAULT_CONFIG
from .stitcher import write_markdown


def write_example_config(dest: Path):
    example = """# flatcat config (TOML)
    
    root = "."
    output = "flatcat.md"
    include_tree = true
    tree_depth = 0
    respect_gitignore = true
    ignore_extensions = [".png", ".jpg", ".jpeg", ".gif", ".mp4", ".exe", ".zip", ".pdf", ".woff", ".woff2", ".ttf", ".sqlite"]
    
    [filters]
    include = []    # e.g. ["src/**", "*.py"]
    exclude = [
        "**/__pycache__/**", "__pycache__", 
        "venv/**", "venv", ".venv/**", ".venv",
        ".git/**", ".git", 
        "build/**", "build", "dist/**", "dist",
        "node_modules/**", "node_modules", 
        "*.egg-info/**", "*.egg-info",
        ".next/**", ".next", ".nuxt/**", ".nuxt", "out/**", "coverage/**",
        "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
        ".cache/**", ".tmp/**", "tmp/**", ".DS_Store", "Thumbs.db",
        ".vscode/**", ".idea/**",
        ".turbo/**", ".vercel/**", ".netlify/**"
    ]
    
    [format]
    heading = "### {path}"
    fence_language_from_extension = true
    """

    dest.write_text(example, encoding="utf-8")


def next_free_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    i = 1
    while True:
        candidate = path.with_name(f"{stem}-{i}{suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="flatcat", description="Flatten text files in a repo into a single Markdown file.")

    sub = p.add_subparsers(dest="cmd", help="Available commands")

    init_p = sub.add_parser("init", help="Write a starter flatcat.toml")
    init_p.add_argument("path", nargs="?", default=DEFAULT_CONFIG, type=Path, help="Config file path")

    p.add_argument("directory", nargs="?", type=Path, help="Directory to flatten (default: current directory)")
    p.add_argument("-c", "--config", type=Path, default=Path(DEFAULT_CONFIG), help="Path to TOML config")
    p.add_argument("--out", type=Path, default=None, help="Output file path (default: ./<dir>md, auto-incremented)")
    p.add_argument("--no-tree", action="store_true", help="Disable directory tree in output")

    return p


def main(argv=None):
    # Avoid subparser conflicts
    if argv is None:
        import sys
        argv = sys.argv[1:]
    
    # If first argument is 'init', handle as subcommand
    if argv and argv[0] == "init":
        parser = build_parser()
        args = parser.parse_args(argv)

        path: Path = args.path
        if path.exists():
            print(f"Error: {path} already exists")
            return 1
        write_example_config(path)
        print(f"Wrote {path}")
        return 0
    
    # Otherwise, handle as main command (ignore subparsers)
    parser = argparse.ArgumentParser(prog="flatcat", description="Flatten text files in a repo into a single Markdown file.")
    parser.add_argument("directory", nargs="?", help="Directory to flatten (default: current directory)")
    parser.add_argument("-c", "--config", type=Path, default=Path(DEFAULT_CONFIG), help="Path to TOML config")
    parser.add_argument("--out", type=Path, default=None, help="Output file path (default: ./<dir>.md, auto-incremented)")
    parser.add_argument("--no-tree", action="store_true", help="Disable directory tree in output")

    args = parser.parse_args(argv)

    # Default: run
    directory = Path(args.directory) if args.directory else Path.cwd()
    if not directory.exists():
        parser.error(f"Directory not found: {directory}")
        return 1

    cfg = Config.load(args.config)
    cfg.root = directory.resolve()

    # Compute output default ./<basename(dir)>-flatcat.md and auto-increment
    default_out = Path.cwd() / f"{cfg.root.name}-flatcat.md"
    cfg.output = next_free_path(args.out or default_out)

    if args.no_tree:
        cfg.include_tree = False
    
    write_markdown(cfg)
    print(f"Wrote {cfg.output}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
