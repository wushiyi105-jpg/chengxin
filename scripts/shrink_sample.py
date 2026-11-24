"""把样例图压到能进仓库的尺寸：长边 1100，JPEG 质量 82。

只跑一次，产物覆盖 samples/meal-1.jpg——原图 3.2MB，README 里挂不动。
"""

from __future__ import annotations

import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "samples", "meal-1.jpg")
MAX_SIDE = 1100


def main() -> None:
    before = os.path.getsize(TARGET)
    img = Image.open(TARGET).convert("RGB")
    if max(img.size) > MAX_SIDE:
        ratio = MAX_SIDE / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)))
    img.save(TARGET, format="JPEG", quality=82, optimize=True)
    after = os.path.getsize(TARGET)
    print(f"{img.size[0]}×{img.size[1]}  {before / 1024:.0f} KB -> {after / 1024:.0f} KB")


if __name__ == "__main__":
    main()
