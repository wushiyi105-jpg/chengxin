"""生成 assets/demo.gif：960×600 的终端风演示动图。

只用 Pillow（开发期依赖，不进 requirements）。跑法：
    python scripts/make_demo_gif.py

画面里的数字是真跑出来的：4 样食物、605 千卡、覆盖率 100%。
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

W, H = 960, 600
BG = "#0b0f14"
BAR = "#161b22"
LINE = "#21262d"
GREEN = "#7ee787"
TEXT = "#c9d1d9"
DIM = "#8b949e"
BLUE = "#79c0ff"
YELLOW = "#e3b341"
RED = "#ff7b72"

FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"

LINE_H = 25
MAX_W = W - 56

COLORS = {"cmd": GREEN, "out": TEXT, "dim": DIM, "cite": BLUE, "warn": YELLOW, "bad": RED}


def font(size: int):
    return ImageFont.truetype(FONT_PATH, size)


_MEASURE = ImageDraw.Draw(Image.new("RGB", (1, 1)))


def clip(text: str, size: int = 16) -> str:
    f = font(size)
    if _MEASURE.textlength(text, font=f) <= MAX_W:
        return text
    while text and _MEASURE.textlength(text + "…", font=f) > MAX_W:
        text = text[:-1]
    return text + "…"


def render(rows, cursor_row=None):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 36], fill=BAR)
    for i, color in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        d.ellipse([16 + i * 22, 12, 28 + i * 22, 24], fill=color)
    d.text((92, 9), "chengxin — 模型认食物，本地表算热量", font=font(15), fill=DIM)
    d.line([0, 36, W, 36], fill=LINE)

    y = 54
    for idx, (style, text) in enumerate(rows):
        shown = clip(text)
        d.text((26, y), shown, font=font(16), fill=COLORS[style])
        if cursor_row == idx:
            w = _MEASURE.textlength(shown, font=font(16))
            d.rectangle([26 + w + 4, y + 2, 26 + w + 12, y + 19], fill=GREEN)
        y += LINE_H
        if y > H - 16:
            break
    return img


SCRIPT = [
    ("cmd", "> python -m chengxin analyze samples/meal-1.jpg"),
    ("dim", "· 看图：meal-1.jpg（模型要跑十几秒）"),
    ("out", "=== 餐 [1] 周三午饭 · 4 样 ==="),
    ("dim", "场景：这是一份家常午餐的餐盘"),
    ("out", "· 米饭 150g（alias） —— 174 千卡（148–200，把握 high）"),
    ("out", "· 西兰花 100g（exact） —— 36 千卡（31–41，把握 high）"),
    ("dim", "· 青椒 150g（fuzzy） —— 33 千卡（28–38，把握 high）"),
    ("out", "· 鸡腿 200g（alias） —— 362 千卡（308–416，把握 high）"),
    ("cite", "合计 605 千卡，区间 514–696；覆盖率 100%"),
    ("out", "大概 605 千卡，正常一顿饭的量。"),
    ("cmd", "> python -m chengxin list"),
    ("out", "ID  千卡      覆盖率     时间                  名字"),
    ("dim", "1   605.0   1.0     2026-11-25 02:43:07 周三午饭"),
    ("cmd", "> python -m chengxin foods --search 鸡腿"),
    ("out", "鸡腿：181 千卡/100g（蛋白 16.0g，脂肪 13.0g，碳水 0.0g）"),
]
TAIL = [
    ("dim", "模型只报「有什么、多少克」；每个千卡都是本地表乘出来的。"),
    ("warn", "它把「青椒炒肉」只认成青椒 —— 肉那部分热量没算进去。"),
]


def build():
    frames, shown = [], []
    for style, text in SCRIPT:
        if style == "cmd":
            for i in range(6, len(text) + 1, 6):
                frames.append(render(shown + [("cmd", text[:i])], cursor_row=len(shown)))
        shown = shown + [(style, text)]
        frames.append(render(shown))
    for _ in range(12):
        frames.append(render(shown + TAIL))

    frames = [f.quantize(colors=20, method=Image.MEDIANCUT) for f in frames]
    os.makedirs("assets", exist_ok=True)
    out = os.path.join("assets", "demo.gif")
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=140, loop=0, optimize=True)
    print(f"ok -> {out}  {len(frames)} 帧  {os.path.getsize(out) / 1024:.1f} KB")


if __name__ == "__main__":
    build()
