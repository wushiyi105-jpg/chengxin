import unittest

from chengxin import nutrition


class NormalizeTest(unittest.TestCase):
    def test_strips_space_and_punct(self):
        self.assertEqual(nutrition.normalize(" 米饭、 "), "米饭")

    def test_strips_quantity_words(self):
        self.assertEqual(nutrition.normalize("一份米饭"), "米饭")

    def test_strips_parentheses(self):
        self.assertEqual(nutrition.normalize("鸡腿（烤）"), "鸡腿")

    def test_empty(self):
        self.assertEqual(nutrition.normalize(""), "")
        self.assertEqual(nutrition.normalize(None), "")


class LookupTest(unittest.TestCase):
    def test_exact(self):
        hit = nutrition.lookup("米饭")
        self.assertEqual(hit["name"], "米饭")
        self.assertEqual(hit["matched"], "exact")
        self.assertEqual(hit["kcal"], 116)

    def test_alias(self):
        hit = nutrition.lookup("白米饭")
        self.assertEqual(hit["name"], "米饭")
        self.assertEqual(hit["matched"], "alias")

    def test_fuzzy_prefix(self):
        hit = nutrition.lookup("清炒西兰花")
        self.assertEqual(hit["name"], "西兰花")

    def test_cooked_chicken_leg(self):
        hit = nutrition.lookup("烤鸡腿")
        self.assertEqual(hit["name"], "鸡腿")

    def test_fried_chicken_leg(self):
        hit = nutrition.lookup("炸鸡腿")
        self.assertEqual(hit["name"], "炸鸡")
        self.assertGreater(hit["kcal"], 200)

    def test_longest_match_wins(self):
        # 「红烧肉」比「肉」更具体，不能被短词抢走
        self.assertEqual(nutrition.lookup("一盘红烧肉")["name"], "红烧肉")

    def test_unknown(self):
        self.assertIsNone(nutrition.lookup("松露鹅肝"))

    def test_empty(self):
        self.assertIsNone(nutrition.lookup(""))

    def test_quantity_prefix(self):
        self.assertEqual(nutrition.lookup("一碗米饭")["name"], "米饭")


class SuggestTest(unittest.TestCase):
    def test_suggests_similar(self):
        self.assertTrue(nutrition.suggest("鸡胸肉饼"))

    def test_limit(self):
        self.assertLessEqual(len(nutrition.suggest("鸡", limit=2)), 2)

    def test_empty(self):
        self.assertEqual(nutrition.suggest(""), [])


class EnergyTest(unittest.TestCase):
    def test_hundred_grams(self):
        self.assertEqual(nutrition.energy(100, nutrition.FOODS["米饭"]), 116.0)

    def test_half_portion(self):
        self.assertEqual(nutrition.energy(150, nutrition.FOODS["米饭"]), 174.0)

    def test_macros(self):
        m = nutrition.macros(100, nutrition.FOODS["鸡蛋"])
        self.assertEqual(m["protein"], 13.3)
        self.assertEqual(m["fat"], 8.8)

    def test_table_size(self):
        self.assertGreaterEqual(len(nutrition.FOODS), 40)


if __name__ == "__main__":
    unittest.main()
