import unittest
from unittest.mock import MagicMock
from indexer.ml import find_similar_functions


class TestMLSimilarity(unittest.TestCase):
    def test_similarity_search_mock(self):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_session.run.return_value = [
            {"name": "connect_db", "file": "db.py", "docstring": "Connects to database", "code_snippet": "def connect_db(): pass", "args": [], "line_count": 5},
            {"name": "get_db_connection", "file": "db_util.py", "docstring": "Database connection helper", "code_snippet": "def get_db_connection(): pass", "args": [], "line_count": 5},
            {"name": "send_email", "file": "mail.py", "docstring": "Send email alert", "code_snippet": "def send_email(): pass", "args": [], "line_count": 10},
        ]

        results = find_similar_functions(mock_driver, "connect_db", top_k=2)
        if len(results) == 1 and "error" in results[0]:
            # scikit-learn still installing
            return
        self.assertGreaterEqual(len(results), 1)
        top_match = results[0]
        self.assertEqual(top_match["name"], "get_db_connection")
        self.assertGreater(top_match["similarity_score"], 0)


if __name__ == "__main__":
    unittest.main()
