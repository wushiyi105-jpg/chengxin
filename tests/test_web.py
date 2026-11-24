import base64
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from chengxin import store, vision, web

TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

FAKE = {
    "items": [{"name": "米饭", "grams": 150, "confidence": "high", "note": ""}],
    "table_note": "午饭",
    "raw": "",
    "error": "",
}


class WebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.conn = store.connect(os.path.join(cls.tmp.name, "web.db"))
        cls.httpd = web.make_server(cls.conn, port=0)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.conn.close()
        cls.tmp.cleanup()

    def setUp(self):
        self._original = vision.recognize
        vision.recognize = lambda *a, **k: dict(FAKE, items=[dict(x) for x in FAKE["items"]])

    def tearDown(self):
        vision.recognize = self._original

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as r:
            return r.status, r.read().decode("utf-8")

    def _post(self, path, payload):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    def test_index(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("秤心", body)
        self.assertIn("算热量", body)

    def test_meals_empty(self):
        status, body = self._get("/api/meals")
        self.assertEqual(status, 200)
        self.assertIn("items", json.loads(body))

    def test_analyze_upload(self):
        status, data = self._post("/api/analyze", {
            "name": "测试午饭", "note": "", "filename": "dot.png", "image_b64": TINY_PNG_B64,
        })
        meal = data["meal"]
        self.assertEqual(meal["name"], "测试午饭")
        self.assertEqual(meal["analysis"]["total_kcal"], 174.0)
        self.assertIn("warning", data)

    def test_analyze_without_image(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/analyze", {"name": "空"})
        self.assertEqual(ctx.exception.code, 400)

    def test_analyze_bad_base64(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/analyze", {"image_b64": "###"})
        self.assertEqual(ctx.exception.code, 400)

    def test_analyze_vision_failure(self):
        vision.recognize = lambda *a, **k: {"items": [], "table_note": "", "raw": "", "error": "HTTP 429"}
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._post("/api/analyze", {"image_b64": TINY_PNG_B64})
        self.assertEqual(ctx.exception.code, 502)

    def test_meal_detail(self):
        _, data = self._post("/api/analyze", {"name": "明细", "image_b64": TINY_PNG_B64})
        mid = data["meal"]["id"]
        status, body = self._get(f"/api/meal?id={mid}")
        self.assertEqual(json.loads(body)["meal"]["name"], "明细")

    def test_meal_missing(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/api/meal?id=9999")
        self.assertEqual(ctx.exception.code, 404)

    def test_unknown_route(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/api/nope")
        self.assertEqual(ctx.exception.code, 404)

    def test_upload_file_saved(self):
        self._post("/api/analyze", {"filename": "tiny.png", "image_b64": TINY_PNG_B64})
        self.assertTrue(os.path.isdir(web.UPLOAD_DIR))


if __name__ == "__main__":
    unittest.main()
