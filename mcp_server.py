# standard imports
import json
import sys
from pathlib import Path
from typing import Any

from indexer.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from indexer.impact import class_hierarchy, file_impact, function_impact, stats
from indexer.loader import get_driver, index_directory
from indexer.ml import find_similar_functions
from indexer.risk import get_file_risk_scores, get_function_risk_scores

try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("Codegraph", description="Code intelligence graph and impact analysis MCP server")
except ImportError:
    mcp = None


def get_impact(function_name: str, file_path: str | None = None, max_depth: int = 10) -> str:
    """
    Trace what functions or files will be affected if a function or file is modified.
    """
    driver = get_driver()
    try:
        if file_path and not function_name:
            affected = file_impact(driver, file_path, max_depth=max_depth)
        else:
            affected = function_impact(driver, function_name, file=file_path, max_depth=max_depth)
        return json.dumps({"target": {"function": function_name, "file": file_path}, "affected": affected}, indent=2)
    finally:
        driver.close()


def find_similar(function_name: str, file_path: str | None = None, top_k: int = 5) -> str:
    """
    Find functions in the codebase that are semantically or structurally similar to the target function using ML embeddings.
    """
    driver = get_driver()
    try:
        similar = find_similar_functions(driver, function_name, file=file_path, top_k=top_k)
        return json.dumps({"target": function_name, "similar_functions": similar}, indent=2)
    finally:
        driver.close()


def get_risky_components(category: str = "functions", limit: int = 10) -> str:
    """
    Get the highest-risk functions or files in the codebase based on caller count, blast radius depth, lines of code, and git churn.
    category: 'functions' or 'files'
    """
    driver = get_driver()
    try:
        if category.lower() == "files":
            risky = get_file_risk_scores(driver, limit=limit)
        else:
            risky = get_function_risk_scores(driver, limit=limit)
        return json.dumps({"category": category, "risky_components": risky}, indent=2)
    finally:
        driver.close()


def get_class_details(class_name: str) -> str:
    """
    Get superclasses, subclasses, and methods for a given Python class name.
    """
    driver = get_driver()
    try:
        data = class_hierarchy(driver, class_name)
        return json.dumps(data, indent=2)
    finally:
        driver.close()


def query_graph(cypher_query: str) -> str:
    """
    Execute a custom read-only Cypher query against the Neo4j codebase graph database.
    """
    driver = get_driver()
    try:
        with driver.session() as session:
            result = session.run(cypher_query)
            records = [dict(r) for r in result]
            return json.dumps({"query": cypher_query, "results": records}, indent=2)
    except Exception as err:
        return json.dumps({"error": str(err)})
    finally:
        driver.close()


def index_codebase(path: str = "sample", reset: bool = True) -> str:
    """
    Parse a Python codebase directory and index its dependency graph into Neo4j.
    """
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        return json.dumps({"error": f"Not a directory: {root}"})

    count = index_directory(root, uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD, reset=reset)
    driver = get_driver()
    try:
        s = stats(driver)
        return json.dumps({"indexed_files": count, "stats": s, "path": str(root)}, indent=2)
    finally:
        driver.close()


if mcp is not None:
    mcp.tool()(get_impact)
    mcp.tool()(find_similar)
    mcp.tool()(get_risky_components)
    mcp.tool()(get_class_details)
    mcp.tool()(query_graph)
    mcp.tool()(index_codebase)


def run_mcp_server():
    if mcp is not None:
        mcp.run(transport="stdio")
    else:
        print("MCP SDK not installed. Run pip install mcp", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_mcp_server()
