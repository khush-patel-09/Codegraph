import tempfile
import unittest
from pathlib import Path

from indexer.python_parser import parse_file


class TestParser(unittest.TestCase):
    def test_parse_sample_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            code = '''
def helper(x):
    """Helper function docstring."""
    return x * 2

def main():
    """Main entrypoint."""
    res = helper(10)
    print(res)
'''
            py_file = tmp_path / "sample_mod.py"
            py_file.write_text(code, encoding="utf-8")

            graph = parse_file(py_file, tmp_path)
            self.assertEqual(graph.path, "sample_mod.py")
            self.assertEqual(len(graph.functions), 2)

            fn_names = [f.name for f in graph.functions]
            self.assertIn("helper", fn_names)
            self.assertIn("main", fn_names)

            main_fn = next(f for f in graph.functions if f.name == "main")
            self.assertEqual(main_fn.docstring, "Main entrypoint.")
            self.assertGreater(main_fn.line_count, 0)
            self.assertIn("helper", [c.callee for c in graph.calls])

    def test_parse_class_inheritance(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            code = '''
class BaseService:
    """Base service class."""
    def run(self):
        pass

class AuthService(BaseService):
    """Auth service implementation."""
    def login(self, username, password):
        self.run()
'''
            py_file = tmp_path / "services.py"
            py_file.write_text(code, encoding="utf-8")

            graph = parse_file(py_file, tmp_path)
            self.assertEqual(len(graph.classes), 2)

            auth_cls = next(c for c in graph.classes if c.name == "AuthService")
            self.assertIn("BaseService", auth_cls.bases)
            self.assertEqual(auth_cls.docstring, "Auth service implementation.")
            self.assertIn("AuthService.login", auth_cls.methods)


if __name__ == "__main__":
    unittest.main()
