from neo4j import Driver

from indexer.loader import get_driver


def function_impact(
    driver: Driver,
    name: str,
    file: str | None = None,
    max_depth: int = 10,
) -> list[dict]:
    depth = max(1, min(max_depth, 20))
    query = f"""
    MATCH (target:Function)
    WHERE target.name = $name
      AND ($file IS NULL OR target.file = $file)
    MATCH path = (dependent:Function)-[:CALLS*1..{depth}]->(target)
    WITH dependent, min(length(path)) AS depth
    RETURN dependent.name AS function, dependent.file AS file, depth
    ORDER BY depth, file, function
    """
    with driver.session() as session:
        result = session.run(query, name=name, file=file)
        return [dict(record) for record in result]


def file_impact(driver: Driver, path: str, max_depth: int = 5) -> list[dict]:
    depth = max(1, min(max_depth, 20))
    query = f"""
    MATCH (target:File {{path: $path}})
    MATCH path = (importer:File)-[:IMPORTS*1..{depth}]->(target)
    WITH importer, min(length(path)) AS depth
    RETURN importer.path AS file, depth
    ORDER BY depth, file
    """
    with driver.session() as session:
        result = session.run(query, path=path)
        return [dict(record) for record in result]


def search_functions(driver: Driver, query_text: str, limit: int = 20) -> list[dict]:
    query = """
    MATCH (fn:Function)
    WHERE toLower(fn.name) CONTAINS toLower($q)
       OR toLower(fn.file) CONTAINS toLower($q)
    RETURN fn.name AS name, fn.file AS file
    ORDER BY fn.file, fn.name
    LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, q=query_text, limit=limit)
        return [dict(record) for record in result]


def graph_snapshot(driver: Driver, limit: int = 200) -> dict:
    nodes_query = """
    MATCH (n)
    WHERE n:File OR n:Function
    RETURN
        CASE WHEN n:File THEN n.path ELSE n.name END AS label,
        CASE WHEN n:File THEN 'File' ELSE 'Function' END AS type,
        n.path AS file,
        n.name AS name,
        id(n) AS id
    LIMIT $limit
    """
    edges_query = """
    MATCH (a)-[r]->(b)
    WHERE (a:File OR a:Function) AND (b:File OR b:Function)
    RETURN id(a) AS source, id(b) AS target, type(r) AS rel
    LIMIT $limit
    """
    with driver.session() as session:
        nodes = [dict(r) for r in session.run(nodes_query, limit=limit)]
        edges = [dict(r) for r in session.run(edges_query, limit=limit)]
    return {"nodes": nodes, "edges": edges}


def stats(driver: Driver) -> dict:
    query = """
    MATCH (f:File) WITH count(f) AS files
    MATCH (fn:Function) WITH files, count(fn) AS functions
    MATCH ()-[c:CALLS]->() WITH files, functions, count(c) AS calls
    MATCH ()-[i:IMPORTS]->() RETURN files, functions, calls, count(i) AS imports
    """
    with driver.session() as session:
        record = session.run(query).single()
        return dict(record) if record else {"files": 0, "functions": 0, "calls": 0, "imports": 0}
