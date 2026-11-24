import unittest

from chengxin import meal

ITEMS = [
    {"name": "米饭", "grams": 150, "confidence": "high", "note": "白碗一碗"},
    {"name": "西兰花", "grams": 100, "confidence": "medium", "note": ""},
    {"name": "烤鸡腿", "grams": 180, "confidence": "high", "note": ""},
]


class AnalyzeTest(unittest.TestCase):
    def test_total_energy(self):
        r = meal.analyze(ITEMS)
        expect = 150 * 116 / 100 + 100 * 36 / 100 + 180 * 181 / 100
        self.assertAlmostEqual(r["total_kcal"], round(expect, 1), places=1)

    def test_range_is_plus_minus_15(self):
        r = meal.analyze([{"name": "米饭", "grams": 100}])
        lo, hi = r["total_range"]
        self.assertAlmostEqual(lo, 116 * 0.85, places=1)
        self.assertAlmostEqual(hi, 116 * 1.15, places=1)

    def test_macros_summed(self):
        r = meal.analyze(ITEMS)
        self.assertGreater(r["macros"]["protein"], 20)
        self.assertGreater(r["macros"]["carb"], 30)

    def test_full_coverage(self):
        self.assertEqual(meal.analyze(ITEMS)["coverage"], 1.0)

    def test_unknown_food_not_counted(self):
        r = meal.analyze(ITEMS + [{"name": "松露鹅肝", "grams": 50}])
        self.assertEqual(r["unknown_count"], 1)
        self.assertLess(r["coverage"], 1.0)
        self.assertEqual([x["kcal"] for x in r["rows"] if x["name"] == "松露鹅肝"], [None])

    def test_unknown_has_suggestion(self):
        # 「牛排」不在库里（「牛肉」是另一条），但字面相近，应给出候选
        r = meal.analyze([{"name": "牛排", "grams": 120}])
        self.assertTrue(any(x["suggest"] for x in r["rows"]))

    def test_zero_grams_not_counted(self):
        r = meal.analyze([{"name": "米饭", "grams": 0}])
        self.assertEqual(r["total_kcal"], 0)
        self.assertEqual(r["rows"][0]["kcal"], None)
        self.assertIn("热量未计", r["rows"][0]["note"])

    def test_empty_plate(self):
        r = meal.analyze([])
        self.assertEqual(r["total_kcal"], 0)
        self.assertEqual(r["item_count"], 0)

    def test_matched_kind_kept(self):
        r = meal.analyze([{"name": "白米饭", "grams": 100}])
        self.assertEqual(r["rows"][0]["matched"], "alias")
        self.assertEqual(r["rows"][0]["raw_name"], "白米饭")


class VerdictTest(unittest.TestCase):
    def test_empty(self):
        self.assertIn("没认出", meal.verdict({"rows": [], "coverage": 0, "total_kcal": 0}))

    def test_low_coverage_is_honest(self):
        v = meal.verdict({"rows": [{"kcal": 100}], "coverage": 0.4, "total_kcal": 300})
        self.assertIn("实际会更高", v)

    def test_light(self):
        self.assertIn("偏轻", meal.verdict({"rows": [{"kcal": 1}], "coverage": 1, "total_kcal": 300}))

    def test_normal(self):
        self.assertIn("正常", meal.verdict({"rows": [{"kcal": 1}], "coverage": 1, "total_kcal": 600}))

    def test_heavy(self):
        self.assertIn("偏重", meal.verdict({"rows": [{"kcal": 1}], "coverage": 1, "total_kcal": 1200}))


class RenderTest(unittest.TestCase):
    def test_contains_lines(self):
        text = meal.render_text(meal.analyze(ITEMS))
        self.assertIn("米饭", text)
        self.assertIn("合计", text)
        self.assertIn("覆盖率", text)

    def test_unknown_marked(self):
        text = meal.render_text(meal.analyze([{"name": "松露鹅肝", "grams": 30}]))
        self.assertIn("没在营养库里", text)


if __name__ == "__main__":
    unittest.main()
