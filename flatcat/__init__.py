"""Flatcat: flatten a codebase into a single Markdown file."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("flatcat")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"

from .config import Config
from .stitcher import write_markdown

__all__ = ["__version__", "Config", "write_markdown"]
