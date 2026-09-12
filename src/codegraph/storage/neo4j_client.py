from neo4j import Driver, GraphDatabase
from codegraph.config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER


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
