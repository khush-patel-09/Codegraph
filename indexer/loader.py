import subprocess
from pathlib import Path

from neo4j import Driver, GraphDatabase

from indexer.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from indexer.python_parser import FileGraph, discover_python_files, parse_file


def get_driver(
    uri: str = NEO4J_URI,
    user: str = NEO4J_USER,
    password: str = NEO4J_PASSWORD,
) -> Driver:
    return GraphDatabase.driver(uri, auth=(user, password))


def clear_graph(tx) -> None:
    tx.run("MATCH (n) DETACH DELETE n")


def setup_schema(tx) -> None:
    tx.run("CREATE CONSTRAINT file_path IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE")
    tx.run(
        "CREATE CONSTRAINT function_id IF NOT EXISTS "
        "FOR (fn:Function) REQUIRE (fn.name, fn.file) IS UNIQUE"
    )
    tx.run(
        "CREATE CONSTRAINT class_id IF NOT EXISTS "
        "FOR (c:Class) REQUIRE (c.name, c.file) IS UNIQUE"
    )


def get_git_churn(file_path: Path, root: Path) -> int:
    """Returns number of git commits affecting file_path, or 0 if not in git."""
    try:
        rel = file_path.relative_to(root).as_posix()
        res = subprocess.run(
            ["git", "log", "--oneline", "--", rel],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            lines = [l for l in res.stdout.strip().splitlines() if l.strip()]
            return len(lines)
    except Exception:
        pass
    return 0


def load_file(tx, graph: FileGraph, churn: int = 0) -> None:
    tx.run("MERGE (f:File {path: $path}) SET f.churn = $churn", path=graph.path, churn=churn)

    # Load functions first
    for fn in graph.functions:
        tx.run(
            """
            MERGE (fn:Function {name: $name, file: $path})
            SET fn.docstring = $docstring,
                fn.code_snippet = $snippet,
                fn.line_count = $line_count,
                fn.args = $args
            MERGE (f:File {path: $path})
            MERGE (f)-[:CONTAINS]->(fn)
            """,
            name=fn.name,
            path=graph.path,
            docstring=fn.docstring or "",
            snippet=fn.code_snippet or "",
            line_count=fn.line_count,
            args=fn.args,
        )

    # Load classes and relationships to functions & parent classes
    for cls in graph.classes:
        tx.run(
            """
            MERGE (c:Class {name: $name, file: $path})
            SET c.docstring = $docstring
            MERGE (f:File {path: $path})
            MERGE (f)-[:DEFINES_CLASS]->(c)
            """,
            name=cls.name,
            path=graph.path,
            docstring=cls.docstring or "",
        )
        for method in cls.methods:
            tx.run(
                """
                MATCH (c:Class {name: $cls_name, file: $path})
                MATCH (fn:Function {name: $method_name, file: $path})
                MERGE (c)-[:HAS_METHOD]->(fn)
                """,
                cls_name=cls.name,
                method_name=method,
                path=graph.path,
            )
        for base in cls.bases:
            tx.run(
                """
                MATCH (child:Class {name: $cls_name, file: $path})
                MERGE (parent:Class {name: $base_name})
                MERGE (child)-[:INHERITS_FROM]->(parent)
                """,
                cls_name=cls.name,
                path=graph.path,
                base_name=base,
            )

    for edge in graph.calls:
        callee_file = edge.callee_file or graph.path
        tx.run(
            """
            MATCH (a:Function {name: $caller, file: $path})
            MERGE (b:Function {name: $callee, file: $callee_file})
            MERGE (a)-[:CALLS]->(b)
            """,
            caller=edge.caller,
            callee=edge.callee,
            path=graph.path,
            callee_file=callee_file,
        )

    for module in graph.imports:
        target = f"{module}.py"
        tx.run(
            """
            MATCH (src:File {path: $path})
            MERGE (dst:File {path: $target})
            MERGE (src)-[:IMPORTS]->(dst)
            """,
            path=graph.path,
            target=target,
        )


def index_directory(
    root: Path,
    uri: str = NEO4J_URI,
    user: str = NEO4J_USER,
    password: str = NEO4J_PASSWORD,
    reset: bool = False,
) -> int:
    files = discover_python_files(root)
    if not files:
        raise SystemExit(f"No Python files found in {root}")

    driver = get_driver(uri, user, password)
    with driver.session() as session:
        session.execute_write(setup_schema)
        if reset:
            session.execute_write(clear_graph)

        for path in files:
            graph = parse_file(path, root)
            churn = get_git_churn(path, root)
            session.execute_write(load_file, graph, churn)
            print(f"Indexed {graph.path} ({len(graph.classes)} classes, {len(graph.functions)} functions, git churn: {churn})")

    driver.close()
    return len(files)
