"""本地食物营养库。

热量不让模型算。模型看图能说的只有「这是什么、大概多少克」，热量由这张表乘出来。
表里的数取自中国食物成分表的常见条目，取整到个位，够日常估算用，不是医学建议。

烹饪方式差别很大，所以「鸡腿」和「炸鸡腿」是两条，别指望一条覆盖。
"""

from __future__ import annotations

import re

# kcal / 蛋白质 g / 脂肪 g / 碳水 g，都是每 100 克
FOODS: dict[str, dict] = {
    "米饭": {"kcal": 116, "p": 2.6, "f": 0.3, "c": 25.9, "aliases": ["白米饭", "蒸米饭", "大米饭", "白饭"]},
    "炒饭": {"kcal": 186, "p": 5.0, "f": 6.5, "c": 27.0, "aliases": ["蛋炒饭", "扬州炒饭"]},
    "粥": {"kcal": 46, "p": 1.1, "f": 0.3, "c": 9.9, "aliases": ["白粥", "大米粥", "小米粥"]},
    "馒头": {"kcal": 223, "p": 7.0, "f": 1.1, "c": 47.0, "aliases": ["白馒头"]},
    "面条": {"kcal": 110, "p": 3.9, "f": 0.4, "c": 22.8, "aliases": ["煮面", "挂面", "阳春面"]},
    "拉面": {"kcal": 130, "p": 5.5, "f": 3.5, "c": 20.0, "aliases": ["牛肉面", "兰州拉面"]},
    "面包": {"kcal": 312, "p": 8.3, "f": 5.1, "c": 58.6, "aliases": ["白面包", "吐司"]},
    "全麦面包": {"kcal": 246, "p": 8.5, "f": 3.5, "c": 45.0, "aliases": ["全麦吐司"]},
    "饺子": {"kcal": 240, "p": 9.0, "f": 11.0, "c": 26.0, "aliases": ["水饺", "猪肉饺子"]},
    "包子": {"kcal": 227, "p": 8.0, "f": 8.5, "c": 29.0, "aliases": ["肉包", "肉包子"]},
    "馄饨": {"kcal": 220, "p": 9.0, "f": 9.0, "c": 25.0, "aliases": ["云吞"]},
    "油条": {"kcal": 388, "p": 6.9, "f": 17.6, "c": 51.0, "aliases": ["炸油条"]},
    "煎饼": {"kcal": 333, "p": 7.6, "f": 10.0, "c": 53.0, "aliases": ["煎饼果子"]},
    "鸡蛋": {"kcal": 144, "p": 13.3, "f": 8.8, "c": 2.8, "aliases": ["煮鸡蛋", "白煮蛋", "水煮蛋", "煎蛋", "荷包蛋"]},
    "鸡胸肉": {"kcal": 133, "p": 19.4, "f": 5.0, "c": 2.5, "aliases": ["鸡胸", "水煮鸡胸"]},
    "鸡腿": {"kcal": 181, "p": 16.0, "f": 13.0, "c": 0.0, "aliases": ["烤鸡腿", "鸡腿肉", "琵琶腿"]},
    "炸鸡": {"kcal": 279, "p": 17.0, "f": 19.0, "c": 9.0, "aliases": ["炸鸡腿", "鸡翅", "炸鸡翅", "鸡块"]},
    "猪里脊": {"kcal": 155, "p": 20.2, "f": 6.2, "c": 1.5, "aliases": ["里脊", "瘦肉", "猪瘦肉"]},
    "红烧肉": {"kcal": 472, "p": 9.0, "f": 44.0, "c": 8.0, "aliases": ["五花肉", "扣肉"]},
    "排骨": {"kcal": 278, "p": 16.7, "f": 23.1, "c": 0.7, "aliases": ["猪排骨", "糖醋排骨"]},
    "牛肉": {"kcal": 106, "p": 20.2, "f": 2.3, "c": 1.2, "aliases": ["瘦牛肉", "牛里脊", "炒牛肉"]},
    "羊肉": {"kcal": 203, "p": 19.0, "f": 14.1, "c": 0.0, "aliases": ["羊排", "烤羊肉"]},
    "鸭肉": {"kcal": 240, "p": 15.5, "f": 19.7, "c": 0.2, "aliases": ["烤鸭", "鸭腿"]},
    "培根": {"kcal": 181, "p": 22.3, "f": 9.0, "c": 0.0, "aliases": []},
    "火腿肠": {"kcal": 212, "p": 14.0, "f": 10.4, "c": 15.6, "aliases": ["火腿"]},
    "三文鱼": {"kcal": 139, "p": 17.2, "f": 7.8, "c": 0.0, "aliases": ["鲑鱼"]},
    "鱼": {"kcal": 104, "p": 17.6, "f": 4.0, "c": 0.0, "aliases": ["清蒸鱼", "鱼肉", "鲈鱼"]},
    "带鱼": {"kcal": 127, "p": 17.7, "f": 4.9, "c": 3.1, "aliases": []},
    "虾": {"kcal": 93, "p": 18.6, "f": 0.8, "c": 2.8, "aliases": ["虾仁", "白虾", "基围虾"]},
    "豆腐": {"kcal": 82, "p": 8.1, "f": 3.7, "c": 4.2, "aliases": ["嫩豆腐", "老豆腐", "家常豆腐"]},
    "豆浆": {"kcal": 16, "p": 1.8, "f": 0.7, "c": 1.1, "aliases": ["无糖豆浆"]},
    "西兰花": {"kcal": 36, "p": 4.1, "f": 0.6, "c": 4.3, "aliases": ["绿花菜", "西蓝花"]},
    "青菜": {"kcal": 15, "p": 1.5, "f": 0.3, "c": 2.7, "aliases": ["小白菜", "油菜", "菠菜", "生菜", "油麦菜", "菜心"]},
    "黄瓜": {"kcal": 16, "p": 0.8, "f": 0.2, "c": 2.9, "aliases": ["青瓜"]},
    "番茄": {"kcal": 20, "p": 0.9, "f": 0.2, "c": 4.0, "aliases": ["西红柿"]},
    "青椒": {"kcal": 22, "p": 1.0, "f": 0.2, "c": 5.4, "aliases": ["尖椒", "彩椒"]},
    "茄子": {"kcal": 23, "p": 1.1, "f": 0.2, "c": 4.9, "aliases": ["长茄"]},
    "土豆": {"kcal": 81, "p": 2.6, "f": 0.2, "c": 17.8, "aliases": ["马铃薯", "土豆丝", "炒土豆"]},
    "红薯": {"kcal": 102, "p": 1.1, "f": 0.2, "c": 24.7, "aliases": ["地瓜", "烤红薯"]},
    "玉米": {"kcal": 112, "p": 4.0, "f": 1.2, "c": 22.8, "aliases": ["玉米棒", "甜玉米"]},
    "胡萝卜": {"kcal": 39, "p": 1.0, "f": 0.2, "c": 8.8, "aliases": []},
    "蘑菇": {"kcal": 24, "p": 2.7, "f": 0.1, "c": 4.1, "aliases": ["香菇", "菌菇", "口蘑"]},
    "木耳": {"kcal": 27, "p": 1.5, "f": 0.2, "c": 6.0, "aliases": ["黑木耳"]},
    "豆角": {"kcal": 31, "p": 2.5, "f": 0.2, "c": 5.7, "aliases": ["四季豆", "豇豆"]},
    "苹果": {"kcal": 53, "p": 0.2, "f": 0.2, "c": 13.5, "aliases": []},
    "香蕉": {"kcal": 93, "p": 1.4, "f": 0.2, "c": 22.0, "aliases": []},
    "橙子": {"kcal": 48, "p": 0.8, "f": 0.2, "c": 11.1, "aliases": ["橘子", "柑橘"]},
    "牛奶": {"kcal": 54, "p": 3.0, "f": 3.2, "c": 3.4, "aliases": ["纯牛奶", "全脂牛奶"]},
    "酸奶": {"kcal": 72, "p": 2.5, "f": 2.7, "c": 9.3, "aliases": ["原味酸奶"]},
    "奶酪": {"kcal": 328, "p": 25.7, "f": 23.5, "c": 3.5, "aliases": ["芝士", "起司"]},
    "薯条": {"kcal": 298, "p": 3.5, "f": 15.0, "c": 38.0, "aliases": ["薯片"]},
    "汉堡": {"kcal": 250, "p": 12.0, "f": 11.0, "c": 26.0, "aliases": ["汉堡包"]},
    "披萨": {"kcal": 235, "p": 11.0, "f": 9.0, "c": 28.0, "aliases": ["比萨"]},
    "蛋糕": {"kcal": 347, "p": 5.0, "f": 15.0, "c": 48.0, "aliases": ["奶油蛋糕", "甜点"]},
    "巧克力": {"kcal": 586, "p": 4.3, "f": 40.1, "c": 51.9, "aliases": []},
    "花生": {"kcal": 574, "p": 24.8, "f": 44.3, "c": 21.7, "aliases": ["花生米"]},
    "核桃": {"kcal": 646, "p": 14.9, "f": 58.8, "c": 19.1, "aliases": []},
    "瓜子": {"kcal": 606, "p": 22.6, "f": 52.8, "c": 12.5, "aliases": ["葵花籽"]},
    "食用油": {"kcal": 899, "p": 0.0, "f": 99.9, "c": 0.0, "aliases": ["植物油", "花生油", "菜籽油", "油"]},
    "沙拉酱": {"kcal": 724, "p": 1.0, "f": 78.0, "c": 5.0, "aliases": ["蛋黄酱", "千岛酱"]},
    "可乐": {"kcal": 43, "p": 0.0, "f": 0.0, "c": 10.8, "aliases": ["汽水", "碳酸饮料"]},
    "啤酒": {"kcal": 32, "p": 0.4, "f": 0.0, "c": 3.1, "aliases": []},
}

# 匹配前先剥掉的口头量词和括号注释
_NOISE = re.compile(r"(一份|一盘|一碗|一小碗|一大碗|少许|适量|左右|大概|约|若干|一些|\(.*?\)|（.*?）)")
_SPACE = re.compile(r"[\s·、,，。]+")


def normalize(name: str) -> str:
    text = _SPACE.sub("", name or "")
    text = _NOISE.sub("", text)
    return text.strip()


def lookup(name: str) -> dict | None:
    """按「完全名 → 别名 → 包含」三级匹配，返回带名称的条目。"""
    key_text = normalize(name)
    if not key_text:
        return None
    if key_text in FOODS:
        return {"name": key_text, **FOODS[key_text], "matched": "exact"}

    for key, item in FOODS.items():
        for alias in item["aliases"]:
            if key_text == normalize(alias):
                return {"name": key, **item, "matched": "alias"}

    best: tuple[int, str] | None = None
    for key, item in FOODS.items():
        for candidate in [key] + list(item["aliases"]):
            cand = normalize(candidate)
            if cand and (cand in key_text or key_text in cand):
                if best is None or len(cand) > best[0]:
                    best = (len(cand), key)
    if best:
        return {"name": best[1], **FOODS[best[1]], "matched": "fuzzy"}
    return None


def suggest(name: str, limit: int = 3) -> list[str]:
    """没匹配上时，给几个字面相近的候选，让人自己选。"""
    text = normalize(name)
    if not text:
        return []
    scored = []
    for key in FOODS:
        common = len(set(text) & set(key))
        if common:
            scored.append((common, key))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [k for _, k in scored[:limit]]


def energy(grams: float, per_100g: dict) -> float:
    return round(grams * per_100g["kcal"] / 100, 1)


def macros(grams: float, per_100g: dict) -> dict:
    return {
        "protein": round(grams * per_100g["p"] / 100, 1),
        "fat": round(grams * per_100g["f"] / 100, 1),
        "carb": round(grams * per_100g["c"] / 100, 1),
    }
