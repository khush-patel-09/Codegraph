import ast
from dataclasses import dataclass, field
from pathlib import Path

from indexer.config import should_skip


@dataclass
class CallEdge:
    caller: str
    callee: str
    callee_file: str | None = None


@dataclass
class FunctionInfo:
    name: str
    docstring: str | None = None
    code_snippet: str | None = None
    line_count: int = 0
    start_line: int = 0
    end_line: int = 0
    args: list[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    name: str
    bases: list[str] = field(default_factory=list)
    docstring: str | None = None
    methods: list[str] = field(default_factory=list)
    start_line: int = 0
    end_line: int = 0


@dataclass
class FileGraph:
    path: str
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    calls: list[CallEdge] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


@dataclass
class _ImportBinding:
    local_name: str
    module: str
    symbol: str | None = None


class _FunctionAnalyzer(ast.NodeVisitor):
    def __init__(
        self,
        file_path: str,
        bindings: dict[str, _ImportBinding],
        local_functions: set[str],
        graph: FileGraph,
        owner: str,
    ) -> None:
        self.file_path = file_path
        self.bindings = bindings
        self.local_functions = local_functions
        self.graph = graph
        self.owner = owner

    def visit_Call(self, node: ast.Call) -> None:
        callee_name, callee_file = _resolve_call(node.func, self.bindings, self.file_path)
        if callee_name:
            if callee_file is None and callee_name in self.local_functions:
                callee_file = self.file_path
            self.graph.calls.append(
                CallEdge(caller=self.owner, callee=callee_name, callee_file=callee_file)
            )
        self.generic_visit(node)


def _module_path(module: str) -> str:
    return f"{module.replace('.', '/')}.py"


def _collect_bindings(tree: ast.AST) -> dict[str, _ImportBinding]:
    bindings: dict[str, _ImportBinding] = {}

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                bindings[local] = _ImportBinding(local, alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.split(".")[0]
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                bindings[local] = _ImportBinding(local, module, alias.name)

    return bindings


def _resolve_call(
    node: ast.AST,
    bindings: dict[str, _ImportBinding],
    current_file: str,
) -> tuple[str | None, str | None]:
    if isinstance(node, ast.Name):
        binding = bindings.get(node.id)
        if binding and binding.symbol:
            return binding.symbol, _module_path(binding.module)
        if binding:
            return binding.local_name, _module_path(binding.module)
        return node.id, None

    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name):
            binding = bindings.get(node.value.id)
            if binding:
                return node.attr, _module_path(binding.module)
        return node.attr, None

    return None, None


def _function_name(node: ast.FunctionDef | ast.AsyncFunctionDef, class_name: str | None) -> str:
    if class_name:
        return f"{class_name}.{node.name}"
    return node.name


def _extract_function_info(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
    source_lines: list[str],
) -> FunctionInfo:
    docstring = ast.get_docstring(node)
    start_line = getattr(node, "lineno", 1)
    end_line = getattr(node, "end_lineno", start_line)
    snippet_lines = source_lines[start_line - 1 : end_line]
    snippet = "\n".join(snippet_lines) if snippet_lines else None
    line_count = (end_line - start_line + 1) if snippet_lines else 1
    args = [a.arg for a in node.args.args if a.arg != "self"]

    return FunctionInfo(
        name=name,
        docstring=docstring,
        code_snippet=snippet,
        line_count=line_count,
        start_line=start_line,
        end_line=end_line,
        args=args,
    )


def _analyze_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    class_name: str | None,
    file_path: str,
    bindings: dict[str, _ImportBinding],
    local_functions: set[str],
    graph: FileGraph,
    source_lines: list[str],
) -> None:
    name = _function_name(node, class_name)
    fn_info = _extract_function_info(node, name, source_lines)
    graph.functions.append(fn_info)
    analyzer = _FunctionAnalyzer(file_path, bindings, local_functions, graph, name)
    analyzer.visit(node)


def _analyze_class(
    node: ast.ClassDef,
    file_path: str,
    bindings: dict[str, _ImportBinding],
    local_functions: set[str],
    graph: FileGraph,
    source_lines: list[str],
) -> None:
    bases = []
    for b in node.bases:
        if isinstance(b, ast.Name):
            bases.append(b.id)
        elif isinstance(b, ast.Attribute):
            bases.append(b.attr)

    docstring = ast.get_docstring(node)
    start_line = getattr(node, "lineno", 1)
    end_line = getattr(node, "end_lineno", start_line)
    methods = []

    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_name = f"{node.name}.{item.name}"
            methods.append(method_name)
            _analyze_function(item, node.name, file_path, bindings, local_functions, graph, source_lines)

    cls_info = ClassInfo(
        name=node.name,
        bases=bases,
        docstring=docstring,
        methods=methods,
        start_line=start_line,
        end_line=end_line,
    )
    graph.classes.append(cls_info)


def parse_file(path: Path, root: Path) -> FileGraph:
    rel_path = path.relative_to(root).as_posix()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    source_lines = source.splitlines()

    graph = FileGraph(path=rel_path)
    bindings = _collect_bindings(tree)

    for node in tree.body:
        module = None
        if isinstance(node, ast.Import):
            module = node.names[0].name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.split(".")[0]
        if module:
            graph.imports.append(module)

    local_functions: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            local_functions.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    local_functions.add(f"{node.name}.{item.name}")

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _analyze_function(node, None, rel_path, bindings, local_functions, graph, source_lines)
        elif isinstance(node, ast.ClassDef):
            _analyze_class(node, rel_path, bindings, local_functions, graph, source_lines)

    return graph


def discover_python_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*.py")):
        if should_skip(path.relative_to(root)):
            continue
        files.append(path)
    return files
