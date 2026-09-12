import time
from pathlib import Path

from codegraph.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from codegraph.core.parser import discover_python_files, parse_file
from codegraph.storage.loader import get_git_churn, load_file
from codegraph.storage.neo4j_client import get_driver


def watch_directory(root: Path, poll_interval: float = 2.0) -> None:
    """
    Monitors a Python codebase directory for file modifications and incrementally updates Neo4j in real-time.
    """
    print(f"Watching {root} for Python file changes (Press Ctrl+C to stop)...")
    mtimes: dict[Path, float] = {}
    driver = get_driver(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    # Initial mtime population
    files = discover_python_files(root)
    for p in files:
        try:
            mtimes[p] = p.stat().st_mtime
        except OSError:
            pass

    try:
        while True:
            current_files = discover_python_files(root)
            for path in current_files:
                try:
                    current_mtime = path.stat().st_mtime
                    if path not in mtimes:
                        mtimes[path] = current_mtime
                        print(f"[LIVE UPDATE] New file detected: {path.relative_to(root)}")
                        graph = parse_file(path, root)
                        churn = get_git_churn(path, root)
                        with driver.session() as session:
                            session.execute_write(load_file, graph, churn)
                    elif current_mtime > mtimes[path]:
                        mtimes[path] = current_mtime
                        print(f"[LIVE UPDATE] Re-indexing modified file: {path.relative_to(root)}")
                        graph = parse_file(path, root)
                        churn = get_git_churn(path, root)
                        with driver.session() as session:
                            session.execute_write(load_file, graph, churn)
                except Exception as err:
                    print(f"Error checking {path}: {err}")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nStopped watcher.")
    finally:
        driver.close()
