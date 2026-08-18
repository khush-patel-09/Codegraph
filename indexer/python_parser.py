import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileGraph:
    path: str
    functions: list[str] = field(default_factory=list)
    calls: list[tuple[str, str]] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


class _CallVisitor(ast.NodeVisitor):
    def __init__(self, owner: str, calls: list[tuple[str, str]]) -> None:
        self.owner = owner
        self.calls = calls

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name:
            self.calls.append((self.owner, name))
        self.generic_visit(node)


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _import_module(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        return node.names[0].name.split(".")[0]
    if isinstance(node, ast.ImportFrom) and node.module:
        return node.module.split(".")[0]
    return None


def parse_file(path: Path, root: Path) -> FileGraph:
    rel_path = path.relative_to(root).as_posix()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    graph = FileGraph(path=rel_path)

    for node in tree.body:
        module = _import_module(node)
        if module:
            graph.imports.append(module)

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            graph.functions.append(node.name)
            visitor = _CallVisitor(node.name, graph.calls)
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    visitor.visit(child)

    return graph
