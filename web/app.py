from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from indexer.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from indexer.impact import file_impact, function_impact, graph_snapshot, search_functions, stats
from indexer.loader import get_driver, index_directory
from indexer.ml import find_similar_functions
from indexer.risk import get_file_risk_scores, get_function_risk_scores

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Codegraph", description="Code dependency map, risk scoring, ML similarity, and MCP server")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class IndexRequest(BaseModel):
    path: str
    reset: bool = True


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    driver = get_driver()
    try:
        driver.verify_connectivity()
        return {"status": "ok", "neo4j": NEO4J_URI}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        driver.close()


@app.get("/api/stats")
def api_stats():
    driver = get_driver()
    try:
        return stats(driver)
    finally:
        driver.close()


@app.get("/api/search")
def api_search(q: str = Query(min_length=1)):
    driver = get_driver()
    try:
        return search_functions(driver, q)
    finally:
        driver.close()


@app.get("/api/graph")
def api_graph(limit: int = Query(default=200, le=500)):
    driver = get_driver()
    try:
        return graph_snapshot(driver, limit=limit)
    finally:
        driver.close()


@app.get("/api/impact/function")
def api_function_impact(
    name: str = Query(min_length=1),
    file: str | None = None,
    depth: int = Query(default=10, le=20),
):
    driver = get_driver()
    try:
        rows = function_impact(driver, name, file=file, max_depth=depth)
        return {"target": {"name": name, "file": file}, "affected": rows}
    finally:
        driver.close()


@app.get("/api/impact/file")
def api_file_impact(path: str = Query(min_length=1), depth: int = Query(default=5, le=20)):
    driver = get_driver()
    try:
        rows = file_impact(driver, path, max_depth=depth)
        return {"target": {"path": path}, "affected": rows}
    finally:
        driver.close()


@app.get("/api/risk/functions")
def api_risk_functions(limit: int = Query(default=10, le=50)):
    driver = get_driver()
    try:
        return get_function_risk_scores(driver, limit=limit)
    finally:
        driver.close()


@app.get("/api/risk/files")
def api_risk_files(limit: int = Query(default=10, le=50)):
    driver = get_driver()
    try:
        return get_file_risk_scores(driver, limit=limit)
    finally:
        driver.close()


@app.get("/api/similar")
def api_similar(name: str = Query(min_length=1), file: str | None = None, top_k: int = Query(default=5, le=20)):
    driver = get_driver()
    try:
        results = find_similar_functions(driver, name, file=file, top_k=top_k)
        return {"target": name, "similar": results}
    finally:
        driver.close()


@app.get("/api/mcp/info")
def api_mcp_info():
    return {
        "status": "ready",
        "command": "python -m indexer mcp",
        "tools": [
            {"name": "tool_get_impact", "description": "Trace downstream call/import blast radius"},
            {"name": "tool_find_similar_functions", "description": "Find semantically/structurally similar code"},
            {"name": "tool_get_risky_components", "description": "Rank highest risk functions or files"},
            {"name": "tool_query_graph", "description": "Run custom Cypher queries"},
            {"name": "tool_index_codebase", "description": "Re-index Python project directory"},
        ],
    }


@app.post("/api/index")
def api_index(body: IndexRequest):
    root = Path(body.path).expanduser().resolve()
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {root}")

    try:
        count = index_directory(
            root,
            uri=NEO4J_URI,
            user=NEO4J_USER,
            password=NEO4J_PASSWORD,
            reset=body.reset,
        )
        driver = get_driver()
        try:
            summary = stats(driver)
        finally:
            driver.close()
        return {"indexed_files": count, "stats": summary, "path": str(root)}
    except SystemExit as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
