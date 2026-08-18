import argparse
import os
from pathlib import Path

from neo4j import GraphDatabase

from indexer.python_parser import parse_file


def clear_graph(tx):
    tx.run("MATCH (n) DETACH DELETE n")


def load_file(tx, graph):
    tx.run("MERGE (f:File {path: $path})", path=graph.path)

    for name in graph.functions:
        tx.run(
            """
            MERGE (fn:Function {name: $name, file: $path})
            MERGE (f:File {path: $path})
            MERGE (f)-[:CONTAINS]->(fn)
            """,
            name=name,
            path=graph.path,
        )

    for caller, callee in graph.calls:
        tx.run(
            """
            MATCH (a:Function {name: $caller, file: $path})
            MERGE (b:Function {name: $callee})
            MERGE (a)-[:CALLS]->(b)
            """,
            caller=caller,
            callee=callee,
            path=graph.path,
        )

    for module in graph.imports:
        tx.run(
            """
            MATCH (src:File {path: $path})
            MERGE (dst:File {path: $module})
            MERGE (src)-[:IMPORTS]->(dst)
            """,
            path=graph.path,
            module=f"{module}.py",
        )


def index_directory(root: Path, uri: str, user: str, password: str, reset: bool) -> None:
    files = sorted(root.rglob("*.py"))
    if not files:
        raise SystemExit(f"No Python files found in {root}")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        if reset:
            session.execute_write(clear_graph)

        for path in files:
            graph = parse_file(path, root)
            session.execute_write(load_file, graph)
            print(f"Indexed {graph.path} ({len(graph.functions)} functions)")

    driver.close()
    print(f"Done. Indexed {len(files)} file(s). Open http://localhost:7474 to explore.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Python code into Neo4j")
    parser.add_argument("path", nargs="?", default="sample", help="Folder to index")
    parser.add_argument("--reset", action="store_true", help="Clear the graph before indexing")
    args = parser.parse_args()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "codegraph123")

    index_directory(Path(args.path).resolve(), uri, user, password, args.reset)


if __name__ == "__main__":
    main()
