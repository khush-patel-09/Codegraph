import argparse
import json
import sys
from pathlib import Path

from indexer.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from indexer.impact import class_hierarchy, file_impact, function_impact, stats
from indexer.loader import get_driver, index_directory
from indexer.ml import find_similar_functions
from indexer.risk import get_codebase_risk_summary, get_file_risk_scores, get_function_risk_scores


def cmd_index(args: argparse.Namespace) -> None:
    root = Path(args.path).resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    count = index_directory(
        root,
        uri=args.uri,
        user=args.user,
        password=args.password,
        reset=args.reset,
    )
    print(f"Done. Indexed {count} file(s). Open http://localhost:8000 or Neo4j Browser.")


def cmd_impact(args: argparse.Namespace) -> None:
    driver = get_driver(args.uri, args.user, args.password)
    try:
        if args.file and args.name:
            rows = function_impact(driver, args.name, file=args.file)
            label = f"{args.file}::{args.name}"
        elif args.name:
            rows = function_impact(driver, args.name)
            label = args.name
        elif args.file:
            rows = file_impact(driver, args.file)
            label = args.file
            if not rows:
                print(f"No importers found for file '{args.file}'.")
                return
            print(f"Changing file '{label}' may affect these importers:\n")
            for row in rows:
                depth = row["depth"]
                print(f"  {'  ' * (depth - 1)}- {row['file']} (hop {depth})")
            return
        else:
            raise SystemExit("Provide a function name and/or --file")

        if not rows:
            print(f"No callers found for '{label}'.")
            return

        print(f"Changing '{label}' may affect:\n")
        for row in rows:
            depth = row["depth"]
            indent = "  " * (depth - 1)
            print(f"  {indent}- {row['function']} in {row['file']} (hop {depth})")
    finally:
        driver.close()


def cmd_class(args: argparse.Namespace) -> None:
    driver = get_driver(args.uri, args.user, args.password)
    try:
        data = class_hierarchy(driver, args.name)
        print(json.dumps(data, indent=2))
    finally:
        driver.close()


def cmd_risk(args: argparse.Namespace) -> None:
    driver = get_driver(args.uri, args.user, args.password)
    try:
        if args.category == "files":
            items = get_file_risk_scores(driver, limit=args.limit)
        else:
            items = get_function_risk_scores(driver, limit=args.limit)
        print(json.dumps(items, indent=2))
    finally:
        driver.close()


def cmd_similar(args: argparse.Namespace) -> None:
    driver = get_driver(args.uri, args.user, args.password)
    try:
        results = find_similar_functions(driver, args.name, file=args.file, top_k=args.limit)
        print(json.dumps(results, indent=2))
    finally:
        driver.close()


def cmd_watch(args: argparse.Namespace) -> None:
    from indexer.watcher import watch_directory

    root = Path(args.path).resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")
    watch_directory(root)


def cmd_stats(args: argparse.Namespace) -> None:
    driver = get_driver(args.uri, args.user, args.password)
    try:
        data = stats(driver)
        print(json.dumps(data, indent=2))
    finally:
        driver.close()


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run(
        "web.app:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


def cmd_mcp(args: argparse.Namespace) -> None:
    from mcp_server import run_mcp_server

    run_mcp_server()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codegraph",
        description="Map Python code dependencies in Neo4j, compute risk, similarity, and expose MCP tools.",
    )
    parser.add_argument("--uri", default=NEO4J_URI)
    parser.add_argument("--user", default=NEO4J_USER)
    parser.add_argument("--password", default=NEO4J_PASSWORD)

    sub = parser.add_subparsers(dest="command", required=True)

    index_parser = sub.add_parser("index", help="Index a Python project folder")
    index_parser.add_argument("path", nargs="?", default="sample")
    index_parser.add_argument("--reset", action="store_true", help="Clear graph before indexing")
    index_parser.set_defaults(func=cmd_index)

    impact_parser = sub.add_parser("impact", help="Show what breaks if you change a function or file")
    impact_parser.add_argument("name", nargs="?", help="Function name")
    impact_parser.add_argument("--file", help="File path (e.g. db.py or auth.py)")
    impact_parser.set_defaults(func=cmd_impact)

    class_parser = sub.add_parser("class", help="Show class hierarchy and methods")
    class_parser.add_argument("name", help="Class name")
    class_parser.set_defaults(func=cmd_class)

    risk_parser = sub.add_parser("risk", help="Find high-risk functions or files")
    risk_parser.add_argument("--category", choices=["functions", "files"], default="functions")
    risk_parser.add_argument("--limit", type=int, default=10)
    risk_parser.set_defaults(func=cmd_risk)

    similar_parser = sub.add_parser("similar", help="Find functions similar to a given function")
    similar_parser.add_argument("name", help="Function name")
    similar_parser.add_argument("--file", help="Optional file path filter")
    similar_parser.add_argument("--limit", type=int, default=5)
    similar_parser.set_defaults(func=cmd_similar)

    watch_parser = sub.add_parser("watch", help="Watch codebase for live incremental updates on file save")
    watch_parser.add_argument("path", nargs="?", default="sample")
    watch_parser.set_defaults(func=cmd_watch)

    stats_parser = sub.add_parser("stats", help="Show graph statistics")
    stats_parser.set_defaults(func=cmd_stats)

    serve_parser = sub.add_parser("serve", help="Start the web dashboard")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.set_defaults(func=cmd_serve)

    mcp_parser = sub.add_parser("mcp", help="Start the MCP server (stdio transport)")
    mcp_parser.set_defaults(func=cmd_mcp)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
