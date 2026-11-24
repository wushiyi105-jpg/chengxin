import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from chengxin import cli, nutrition, vision

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples", "meal-1.jpg")

FAKE = {
    "items": [
        {"name": "米饭", "grams": 150, "confidence": "high", "note": ""},
        {"name": "西兰花", "grams": 100, "confidence": "medium", "note": ""},
    ],
    "table_note": "家常午饭",
    "raw": "",
    "error": "",
}


def run(argv, db):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.main(["--db", db] + argv)
    return code, buf.getvalue()


class CliTest(unittest.TestCase):
    ORIGINAL = staticmethod(lambda *a, **k: None)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "cli.db")
        self._original = vision.recognize
        vision.recognize = lambda *a, **k: dict(FAKE, items=[dict(x) for x in FAKE["items"]])

    def tearDown(self):
        # 不恢复的话，后面所有 vision 测试都会被这个替身顶掉
        vision.recognize = self._original
        self.tmp.cleanup()

    def test_analyze_writes_record(self):
        code, out = run(["analyze", SAMPLE, "--name", "午饭"], self.db)
        self.assertEqual(code, 0)
        self.assertIn("米饭", out)
        self.assertIn("605" if "605" in out else "合计", out)
        code, listing = run(["list"], self.db)
        self.assertIn("午饭", listing)

    def test_analyze_missing_file(self):
        code, out = run(["analyze", "不存在.jpg"], self.db)
        self.assertEqual(code, 0)
        self.assertIn("找不到图片", out)

    def test_analyze_json(self):
        code, out = run(["analyze", SAMPLE, "--json"], self.db)
        self.assertEqual(code, 0)
        idx = out.find('{\n  "id"')
        self.assertGreater(idx, 0)
        data = json.loads(out[idx:])
        self.assertEqual(data["analysis"]["total_kcal"], 210.0)

    def test_analyze_unknown_food_shown(self):
        vision.recognize = lambda *a, **k: {
            "items": [{"name": "松露鹅肝", "grams": 40}], "table_note": "", "raw": "", "error": ""
        }
        code, out = run(["analyze", SAMPLE], self.db)
        self.assertIn("没在营养库里", out)

    def test_analyze_model_failure(self):
        vision.recognize = lambda *a, **k: {"items": [], "table_note": "", "raw": "", "error": "HTTP 401"}
        code, out = run(["analyze", SAMPLE], self.db)
        self.assertEqual(code, 0)
        self.assertIn("识别失败", out)

    def test_show(self):
        run(["analyze", SAMPLE, "--name", "午饭"], self.db)
        code, out = run(["show", "1"], self.db)
        self.assertEqual(code, 0)
        self.assertIn("午饭", out)
        self.assertIn("合计", out)

    def test_show_missing(self):
        code, out = run(["show", "9"], self.db)
        self.assertEqual(code, 1)
        self.assertIn("没有 id=9", out)

    def test_rm(self):
        run(["analyze", SAMPLE, "--name", "午饭"], self.db)
        code, out = run(["rm", "1"], self.db)
        self.assertEqual(code, 0)
        self.assertIn("已删除", out)

    def test_rm_missing(self):
        code, out = run(["rm", "9"], self.db)
        self.assertEqual(code, 1)

    def test_list_empty(self):
        code, out = run(["list"], self.db)
        self.assertIn("还没有记录", out)

    def test_stats(self):
        run(["analyze", SAMPLE], self.db)
        code, out = run(["stats"], self.db)
        self.assertIn("平均", out)

    def test_foods_search_hit(self):
        code, out = run(["foods", "--search", "米饭"], self.db)
        self.assertIn("116 千卡", out)

    def test_foods_search_miss(self):
        code, out = run(["foods", "--search", "鹅肝"], self.db)
        self.assertIn("库里没有", out)

    def test_foods_list(self):
        code, out = run(["foods"], self.db)
        self.assertIn("营养库共", out)
        self.assertGreater(len(out), 100)


if __name__ == "__main__":
    unittest.main()
