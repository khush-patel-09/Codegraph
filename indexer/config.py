import os
from pathlib import Path

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".pytest_cache",
    "site-packages",
    "dist",
    "build",
}

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "codegraph123")


def should_skip(path: Path) -> bool:
    return any(part in DEFAULT_IGNORE_DIRS for part in path.parts)
