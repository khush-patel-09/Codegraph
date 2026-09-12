from neo4j import Driver


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


def class_hierarchy(driver: Driver, class_name: str) -> dict:
    query_subclasses = """
    MATCH (sub:Class)-[:INHERITS_FROM*1..5]->(target:Class)
    WHERE target.name = $name
    RETURN sub.name AS subclass, sub.file AS file
    """
    query_superclasses = """
    MATCH (target:Class)-[:INHERITS_FROM*1..5]->(parent:Class)
    WHERE target.name = $name
    RETURN parent.name AS superclass, parent.file AS file
    """
    query_methods = """
    MATCH (c:Class {name: $name})-[r:HAS_METHOD]->(m:Function)
    RETURN m.name AS method, m.file AS file, m.docstring AS docstring
    """
    with driver.session() as session:
        subclasses = [dict(r) for r in session.run(query_subclasses, name=class_name)]
        superclasses = [dict(r) for r in session.run(query_superclasses, name=class_name)]
        methods = [dict(r) for r in session.run(query_methods, name=class_name)]

    return {
        "class": class_name,
        "subclasses": subclasses,
        "superclasses": superclasses,
        "methods": methods,
    }


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


def graph_snapshot(driver: Driver, limit: int = 300) -> dict:
    nodes_query = """
    MATCH (n)
    WHERE n:File OR n:Function OR n:Class
    OPTIONAL MATCH (caller:Function)-[:CALLS]->(n)
    OPTIONAL MATCH (importer:File)-[:IMPORTS]->(n)
    WITH n, 
         CASE 
           WHEN n:Function THEN count(DISTINCT caller)
           WHEN n:File THEN count(DISTINCT importer)
           ELSE 0
         END AS in_degree
    RETURN
        CASE 
          WHEN n:File THEN n.path 
          WHEN n:Class THEN n.name 
          ELSE n.name 
        END AS label,
        CASE 
          WHEN n:File THEN 'File' 
          WHEN n:Class THEN 'Class' 
          ELSE 'Function' 
        END AS type,
        n.path AS file,
        n.name AS name,
        n.docstring AS docstring,
        n.line_count AS line_count,
        n.churn AS churn,
        n.args AS args,
        in_degree,
        id(n) AS id
    LIMIT $limit
    """
    edges_query = """
    MATCH (a)-[r]->(b)
    WHERE (a:File OR a:Function OR a:Class) AND (b:File OR b:Function OR b:Class)
    RETURN id(a) AS source, id(b) AS target, type(r) AS rel
    LIMIT $limit
    """
    with driver.session() as session:
        nodes = [dict(r) for r in session.run(nodes_query, limit=limit)]
        edges = [dict(r) for r in session.run(edges_query, limit=limit)]
    return {"nodes": nodes, "edges": edges}


def node_details(driver: Driver, node_id: int | None = None, name: str | None = None, file: str | None = None) -> dict:
    query = """
    MATCH (n)
    WHERE ($id IS NOT NULL AND id(n) = $id)
       OR ($name IS NOT NULL AND n.name = $name AND ($file IS NULL OR n.file = $file))
       OR ($file IS NOT NULL AND n.path = $file)
    WITH n LIMIT 1
    
    OPTIONAL MATCH (caller:Function)-[:CALLS]->(n)
    WITH n, collect(DISTINCT {name: caller.name, file: caller.file}) AS callers
    
    OPTIONAL MATCH (n)-[:CALLS]->(callee:Function)
    WITH n, callers, collect(DISTINCT {name: callee.name, file: callee.file}) AS callees
    
    OPTIONAL MATCH (f:File)-[:CONTAINS]->(n)
    WITH n, callers, callees, f.path AS containing_file
    
    OPTIONAL MATCH (importer:File)-[:IMPORTS]->(n)
    WITH n, callers, callees, containing_file, collect(DISTINCT importer.path) AS importers
    
    OPTIONAL MATCH (n)-[:IMPORTS]->(imported:File)
    WITH n, callers, callees, containing_file, importers, collect(DISTINCT imported.path) AS imported_files
    
    RETURN {
        id: id(n),
        labels: labels(n),
        name: n.name,
        file: coalesce(n.file, n.path, containing_file),
        docstring: n.docstring,
        snippet: n.code_snippet,
        line_count: n.line_count,
        args: n.args,
        churn: n.churn,
        callers: callers,
        callees: callees,
        importers: importers,
        imported_files: imported_files
    } AS details
    """
    with driver.session() as session:
        rec = session.run(query, id=node_id, name=name, file=file).single()
        return rec["details"] if rec and rec["details"] else {}


def stats(driver: Driver) -> dict:
    query = """
    MATCH (f:File) WITH count(f) AS files
    MATCH (fn:Function) WITH files, count(fn) AS functions
    MATCH (c:Class) WITH files, functions, count(c) AS classes
    MATCH ()-[cl:CALLS]->() WITH files, functions, classes, count(cl) AS calls
    MATCH ()-[i:IMPORTS]->() RETURN files, functions, classes, calls, count(i) AS imports
    """
    with driver.session() as session:
        record = session.run(query).single()
        return dict(record) if record else {"files": 0, "functions": 0, "classes": 0, "calls": 0, "imports": 0}
