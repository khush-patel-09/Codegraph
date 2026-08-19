# Codegraph

Big computer programs are made of tiny pieces that all talk to each other, like friends passing notes. Codegraph draws a map of all those friends and notes in **Neo4j**, calculates structural risk scores, finds similar functions with **ML vector search**, and exposes these intelligence capabilities to **AI Assistants via MCP (Model Context Protocol)**.

---

## Key Features

1. **Python AST Dependency Parser**: Parses Python files, functions, docstrings, lines of code, call graphs, and file imports.
2. **Impact Blast Radius Analysis**: Predicts what functions or files will break if a target component is modified.
3. **Risk Scoring Engine**: Calculates composite risk scores based on caller count (in-degree), blast radius depth, lines of code, and Git commit churn.
4. **ML Code Similarity Search**: Uses TF-IDF and AST feature vector representations to find semantically and structurally similar functions.
5. **MCP Server Integration**: Exposes graph queries, impact analysis, risk scores, and similarity search as standardized tools for AI assistants like Claude Desktop, Cursor, or Antigravity.
6. **Interactive Web Dashboard**: FastAPI backend with Vis.js interactive dependency graph visualization, Risk Heatmaps, and ML Similarity Explorer.

---

## Quick Start

### 1. Start Neo4j Database

```bash
docker compose up -d
```

- **Browser**: http://localhost:7474  
- **Credentials**: `neo4j` / `codegraph123`

### 2. Install Dependencies

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Index Codebase

```bash
python -m indexer index sample --reset
```

### 4. CLI Intelligence Commands

- **Impact Analysis** (What breaks if I change `connect`?):
  ```bash
  python -m indexer impact connect
  ```

- **Risk Scoring** (Which components are riskiest to touch?):
  ```bash
  python -m indexer risk --category functions
  ```

- **ML Similarity Search** (What functions are similar to `login`?):
  ```bash
  python -m indexer similar login
  ```

- **Start Web Dashboard**:
  ```bash
  python -m indexer serve
  ```
  Open http://localhost:8000 in your browser.

- **Start MCP Server**:
  ```bash
  python -m indexer mcp
  ```

---

## MCP Server Configuration (Claude Desktop / Cursor)

Add Codegraph as an MCP server in your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "python",
      "args": ["-m", "indexer", "mcp"],
      "cwd": "C:/path/to/Codegraph"
    }
  }
}
```

Now you can ask your AI assistant questions like:
- *"What breaks if I modify `connect()` in db.py?"*
- *"Find functions similar to `login` in my codebase."*
- *"Which parts of this codebase are highest risk to touch?"*

---

## Graph Model Schema

| Node | Attributes | Meaning |
|------|------------|---------|
| `File` | `path`, `churn` | A Python source file and its git commit frequency |
| `Function` | `name`, `file`, `docstring`, `code_snippet`, `line_count`, `args` | A function or method |

| Relationship | Meaning |
|--------------|---------|
| `CONTAINS` | File contains a Function |
| `CALLS` | Function calls another Function |
| `IMPORTS` | File imports another File |

---

## Project Structure

```
Codegraph/
├── indexer/
│   ├── python_parser.py   # Python AST parser & docstring/snippet extractor
│   ├── loader.py          # Neo4j schema & batch loader with Git churn tracking
│   ├── impact.py          # Cypher impact & blast radius queries
│   ├── risk.py            # Risk scoring engine (centrality + churn + complexity)
│   ├── ml.py              # ML vector embedding & cosine similarity engine
│   ├── config.py          # Configuration defaults
│   └── __main__.py        # CLI interface
├── web/
│   ├── app.py             # FastAPI REST endpoints
│   └── static/            # Vis.js graph UI, Risk Heatmap, Similarity Explorer
├── mcp_server.py          # Model Context Protocol stdio server
├── tests/                 # Unit and integration test suite
├── docker-compose.yml     # Neo4j database definition
└── requirements.txt
```
