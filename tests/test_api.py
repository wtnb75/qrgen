import unittest
from fastapi.testclient import TestClient
from qrgen.api import api


class TestAPI(unittest.TestCase):
    client = TestClient(api)

    def test_wifi0(self):
        res = self.client.get("/wifi")
        self.assertEqual(200, res.status_code)
        self.assertEqual("image/png", res.headers.get("Content-Type"))

    def test_wifi1(self):
        res = self.client.get("/wifi/html")
        self.assertEqual(200, res.status_code)
        self.assertEqual("text/html; charset=utf-8",
                         res.headers.get("Content-Type"))

    def test_wifi1_fmterr(self):
        res = self.client.get("/wifi/htmlx")
        self.assertEqual(422, res.status_code)
        self.assertEqual("application/json", res.headers.get("content-type"))
        self.assertIn("detail", res.json())

    def test_wifi1_argerr(self):
        res = self.client.get("/wifi", params={"hidden": "world"})
        self.assertEqual(422, res.status_code)
        self.assertEqual("application/json", res.headers.get("content-type"))
        self.assertIn("detail", res.json())

    def test_wifi1_argok(self):
        res = self.client.get("/wifi", params={"ssid": "SSID123"})
        self.assertEqual(200, res.status_code)
        self.assertEqual("image/png", res.headers.get("Content-Type"))
