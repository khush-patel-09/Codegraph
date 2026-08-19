# Codegraph

Big computer programs are made of tiny pieces that all talk to each other, like friends passing notes. My project draws a big map of all those friends and notes, so people can see who's connected to who. Then it warns you: "hey, if you change this friend, these other friends will get confused too."

## Quick start

### 1. Start Neo4j

```bash
docker compose up -d
```

Browser: http://localhost:7474  
Login: `neo4j` / `codegraph123`

### 2. Install Python deps

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Index the sample project

```bash
python -m indexer sample --reset
```

### 4. Explore in Neo4j Browser

Run the query in `queries/impact.cypher` to see what breaks if you change `connect()`.

Or visualize everything:

```cypher
MATCH (n)-[r]->(m) RETURN n, r, m;
```

## Graph model

| Node | Meaning |
|------|---------|
| `File` | A source file |
| `Function` | A function inside a file |

| Relationship | Meaning |
|--------------|---------|
| `CONTAINS` | File has a function |
| `CALLS` | Function calls another function |
| `IMPORTS` | File imports another file |

## Project layout

```
sample/          # tiny Python project to index
indexer/         # parser + Neo4j loader
queries/         # useful Cypher queries
docker-compose.yml
```

## Environment variables

| Variable | Default |
|----------|---------|
| `NEO4J_URI` | `bolt://localhost:7687` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | `codegraph123` |
