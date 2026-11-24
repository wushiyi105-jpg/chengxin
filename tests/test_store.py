import os
import tempfile
import unittest

from chengxin import meal, store


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = store.connect(os.path.join(self.tmp.name, "c.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_save_and_get(self):
        analysis = meal.analyze([{"name": "米饭", "grams": 100}])
        mid = store.save_meal(self.conn, "午饭", "a.jpg", "sha1", [{"name": "米饭"}], analysis)
        row = store.get_meal(self.conn, mid)
        self.assertEqual(row["name"], "午饭")
        self.assertEqual(row["analysis"]["total_kcal"], 116.0)

    def test_same_image_overwrites(self):
        analysis = meal.analyze([{"name": "米饭", "grams": 100}])
        first = store.save_meal(self.conn, "午饭", "a.jpg", "sha1", [], analysis)
        second = store.save_meal(self.conn, "午饭（重算）", "a.jpg", "sha1", [], analysis)
        self.assertEqual(first, second)
        self.assertEqual(store.get_meal(self.conn, first)["name"], "午饭（重算）")
        self.assertEqual(store.stats(self.conn)["meals"], 1)

    def test_list_newest_first(self):
        analysis = meal.analyze([])
        one = store.save_meal(self.conn, "早", "a.jpg", "s1", [], analysis)
        two = store.save_meal(self.conn, "午", "b.jpg", "s2", [], analysis)
        self.assertEqual([r["id"] for r in store.list_meals(self.conn)], [two, one])

    def test_get_missing(self):
        self.assertIsNone(store.get_meal(self.conn, 99))

    def test_delete(self):
        analysis = meal.analyze([])
        mid = store.save_meal(self.conn, "晚饭", "c.jpg", "s3", [], analysis)
        store.delete_meal(self.conn, mid)
        self.assertIsNone(store.get_meal(self.conn, mid))

    def test_stats_average(self):
        a1 = meal.analyze([{"name": "米饭", "grams": 100}])
        a2 = meal.analyze([{"name": "米饭", "grams": 300}])
        store.save_meal(self.conn, "一", "a.jpg", "h1", [], a1)
        store.save_meal(self.conn, "二", "b.jpg", "h2", [], a2)
        s = store.stats(self.conn)
        self.assertEqual(s["meals"], 2)
        self.assertAlmostEqual(s["avg_kcal"], (116 + 348) / 2, places=1)

    def test_stats_empty(self):
        self.assertEqual(store.stats(self.conn)["meals"], 0)
        self.assertEqual(store.stats(self.conn)["avg_kcal"], 0)

    def test_file_sha_stable(self):
        path = os.path.join(self.tmp.name, "x.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("hey")
        self.assertEqual(store.file_sha(path), store.file_sha(path))
        self.assertEqual(len(store.file_sha(path)), 16)

    def test_creates_parent_dir(self):
        path = os.path.join(self.tmp.name, "deep", "n", "c.db")
        store.connect(path).close()
        self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
