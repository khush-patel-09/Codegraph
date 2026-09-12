from neo4j import Driver


def get_function_risk_scores(driver: Driver, limit: int = 20) -> list[dict]:
    """
    Computes risk scores for functions in the codebase.
    Risk factors:
    - Callers count (in-degree): High caller count = high blast radius.
    - Downstream dependent count: Multi-hop callers.
    - Line count: Complexity proxy.
    - File git churn: Frequency of modification.
    """
    query = """
    MATCH (fn:Function)
    OPTIONAL MATCH (caller:Function)-[:CALLS]->(fn)
    WITH fn, count(DISTINCT caller) AS in_degree
    OPTIONAL MATCH path = (dependent:Function)-[:CALLS*1..5]->(fn)
    WITH fn, in_degree, count(DISTINCT dependent) AS blast_radius
    OPTIONAL MATCH (f:File {path: fn.file})
    WITH fn, in_degree, blast_radius, coalesce(f.churn, 0) AS churn
    
    WITH fn, in_degree, blast_radius, churn,
         (in_degree * 2.5) + (blast_radius * 1.5) + (coalesce(fn.line_count, 10) * 0.05) + (churn * 2.0) AS risk_score
    
    RETURN fn.name AS name,
           fn.file AS file,
           in_degree,
           blast_radius,
           coalesce(fn.line_count, 0) AS line_count,
           churn,
           round(risk_score, 2) AS risk_score
    ORDER BY risk_score DESC, name ASC
    LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        items = [dict(record) for record in result]
        for item in items:
            score = item["risk_score"]
            if score > 15:
                item["level"] = "HIGH"
            elif score > 5:
                item["level"] = "MEDIUM"
            else:
                item["level"] = "LOW"
        return items


def get_file_risk_scores(driver: Driver, limit: int = 20) -> list[dict]:
    """
    Computes risk scores for files in the codebase.
    Risk factors:
    - Importers count: Files importing this file.
    - Function count: Number of functions defined.
    - Git churn: Modification history.
    """
    query = """
    MATCH (f:File)
    OPTIONAL MATCH (importer:File)-[:IMPORTS]->(f)
    WITH f, count(DISTINCT importer) AS importers_count
    OPTIONAL MATCH (f)-[:CONTAINS]->(fn:Function)
    WITH f, importers_count, count(DISTINCT fn) AS function_count
    WITH f, importers_count, function_count, coalesce(f.churn, 0) AS churn,
         (importers_count * 3.0) + (function_count * 1.0) + (coalesce(f.churn, 0) * 2.5) AS risk_score
    
    RETURN f.path AS path,
           importers_count,
           function_count,
           churn,
           round(risk_score, 2) AS risk_score
    ORDER BY risk_score DESC, path ASC
    LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        items = [dict(record) for record in result]
        for item in items:
            score = item["risk_score"]
            if score > 15:
                item["level"] = "HIGH"
            elif score > 5:
                item["level"] = "MEDIUM"
            else:
                item["level"] = "LOW"
        return items


def get_codebase_risk_summary(driver: Driver) -> dict:
    top_functions = get_function_risk_scores(driver, limit=5)
    top_files = get_file_risk_scores(driver, limit=5)
    return {
        "top_risky_functions": top_functions,
        "top_risky_files": top_files,
    }
