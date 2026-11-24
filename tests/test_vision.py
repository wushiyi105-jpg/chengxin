import base64
import os
import tempfile
import unittest

from chengxin import llm, vision

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples", "meal-1.jpg")

TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


class EncodeTest(unittest.TestCase):
    def test_data_url_prefix(self):
        url = vision.encode_image(SAMPLE)
        self.assertTrue(url.startswith("data:image/jpeg;base64,"))
        self.assertGreater(len(url), 1000)

    def test_big_image_is_shrunk(self):
        self.assertGreater(os.path.getsize(SAMPLE), vision.MAX_BYTES)
        url = vision.encode_image(SAMPLE)
        # 压缩后不该还是 4MB 级别的字符串
        self.assertLess(len(url), vision.MAX_BYTES * 1.6)

    def test_small_image_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "dot.png")
            with open(path, "wb") as f:
                f.write(TINY_PNG)
            url = vision.encode_image(path)
            self.assertTrue(url.startswith("data:image/png;base64,"))

    def test_png_mime(self):
        url = vision.encode_image(SAMPLE)
        self.assertNotIn("data:image/jpg", url)


class ConfigTest(unittest.TestCase):
    def test_prefers_vision_vars(self):
        os.environ["VISION_API_KEY"] = "vk"
        os.environ["VISION_BASE_URL"] = "https://example.com/v4"
        os.environ["VISION_MODEL"] = "glm-4.6v-flashx"
        cfg = vision.vision_config()
        self.assertEqual(cfg["api_key"], "vk")
        self.assertEqual(cfg["model"], "glm-4.6v-flashx")

    def test_falls_back_to_llm_vars(self):
        # 空串而不是 pop：vision_config 会重新读 .env，pop 掉的键又会被填回来
        os.environ["VISION_API_KEY"] = ""
        os.environ["LLM_API_KEY"] = "lk"
        self.assertEqual(vision.vision_config()["api_key"], "lk")


BODY = {"choices": [{"message": {"content": ""}}]}


class RecognizeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.image = os.path.join(self.tmp.name, "m.jpg")
        with open(self.image, "wb") as f:
            f.write(TINY_PNG)

    def tearDown(self):
        self.tmp.cleanup()

    def _patch_post(self, content):
        original = vision._post

        def fake(url, payload, key, timeout=120):
            self.captured = payload
            return {"choices": [{"message": {"content": content}}]}

        vision._post = fake
        return original

    def test_missing_key(self):
        os.environ.pop("VISION_API_KEY", None)
        os.environ.pop("LLM_API_KEY", None)
        out = vision.recognize(self.image, config={"api_key": ""})
        self.assertIn("VISION_API_KEY", out["error"])

    def test_missing_file(self):
        out = vision.recognize("不存在.jpg")
        self.assertIn("找不到图片", out["error"])

    def test_parses_items(self):
        payload = '{"items":[{"name":"米饭","grams":150,"confidence":"high","note":"一碗"}],"table_note":"午饭"}'
        original = self._patch_post(payload)
        try:
            out = vision.recognize(self.image, config={"api_key": "k"})
        finally:
            vision._post = original
        self.assertEqual(out["error"], "")
        self.assertEqual(out["items"][0]["grams"], 150)
        self.assertEqual(out["items"][0]["confidence"], "high")
        self.assertEqual(out["table_note"], "午饭")

    def test_prompt_forbids_calories(self):
        payload = '{"items":[],"table_note":""}'
        original = self._patch_post(payload)
        try:
            vision.recognize(self.image, config={"api_key": "k"})
            msgs = self.captured["messages"]
        finally:
            vision._post = original
        joined = " ".join(str(m["content"]) for m in msgs)
        self.assertIn("不要计算热量", joined)

    def test_image_url_in_payload(self):
        payload = '{"items":[],"table_note":""}'
        original = self._patch_post(payload)
        try:
            vision.recognize(self.image, config={"api_key": "k"})
        finally:
            vision._post = original
        content = self.captured["messages"][1]["content"]
        self.assertEqual(content[1]["type"], "image_url")
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/"))

    def test_bad_grams_zeroed(self):
        payload = '{"items":[{"name":"米饭","grams":3000},{"name":"青菜","grams":0}],"table_note":""}'
        original = self._patch_post(payload)
        try:
            out = vision.recognize(self.image, config={"api_key": "k"})
        finally:
            vision._post = original
        self.assertEqual([x["grams"] for x in out["items"]], [0.0, 0.0])

    def test_bad_confidence_defaults(self):
        payload = '{"items":[{"name":"米饭","grams":100,"confidence":"很准"}],"table_note":""}'
        original = self._patch_post(payload)
        try:
            out = vision.recognize(self.image, config={"api_key": "k"})
        finally:
            vision._post = original
        self.assertEqual(out["items"][0]["confidence"], "medium")

    def test_empty_content(self):
        original = self._patch_post("")
        try:
            out = vision.recognize(self.image, config={"api_key": "k"})
        finally:
            vision._post = original
        self.assertIn("空正文", out["error"])

    def test_non_json_content(self):
        original = self._patch_post("盘子里有米饭和鸡腿，大概 700 千卡")
        try:
            out = vision.recognize(self.image, config={"api_key": "k"})
        finally:
            vision._post = original
        self.assertIn("解析 JSON", out["error"])
        self.assertIn("700 千卡", out["raw"])

    def test_http_error_wrapped(self):
        def boom(*a, **k):
            raise llm.LLMError("视觉接口返回 429: rate limited")
        original = vision._post
        vision._post = boom
        try:
            out = vision.recognize(self.image, config={"api_key": "k"})
        finally:
            vision._post = original
        self.assertIn("429", out["error"])

    def test_empty_items_list(self):
        payload = '{"items":[],"table_note":"空盘"}'
        original = self._patch_post(payload)
        try:
            out = vision.recognize(self.image, config={"api_key": "k"})
        finally:
            vision._post = original
        self.assertEqual(out["items"], [])
        self.assertEqual(out["table_note"], "空盘")


if __name__ == "__main__":
    unittest.main()
