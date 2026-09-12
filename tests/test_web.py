import unittest
from fastapi.testclient import TestClient
from web.app import app


class TestWebApp(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_home_and_info(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/studio")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/debug")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/api/mcp/info")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(len(data["tools"]), 6)


if __name__ == "__main__":
    unittest.main()

