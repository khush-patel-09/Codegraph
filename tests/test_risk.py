import unittest
from unittest.mock import MagicMock
from indexer.risk import get_function_risk_scores


class TestRiskScoring(unittest.TestCase):
    def test_function_risk_scores_mock(self):
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_session.run.return_value = [
            {"name": "connect", "file": "db.py", "in_degree": 5, "blast_radius": 10, "line_count": 50, "churn": 12, "risk_score": 51.5},
        ]

        items = get_function_risk_scores(mock_driver, limit=5)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "connect")
        self.assertEqual(items[0]["level"], "HIGH")


if __name__ == "__main__":
    unittest.main()
