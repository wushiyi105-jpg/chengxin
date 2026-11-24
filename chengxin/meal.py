"""把「模型看见了什么」翻译成「这一盘大概多少热量」。

三件事在这里做：
- 拿识别出的名字去本地营养库匹配，匹配不上的单独列出来，不硬凑热量
- 每样按 ±15% 的目测误差给一个区间，总量也给区间——目测克重本来就不该给一个精确数
- 算一个「覆盖率」：认得出来的食物占总克重的多少。太低就说明白：这张照片的结论不可靠
"""

from __future__ import annotations

from . import nutrition

GRAM_TOLERANCE = 0.15
LOW_COVERAGE = 0.7


def analyze(items: list[dict], table_note: str = "") -> dict:
    rows = []
    total = 0.0
    total_lo = 0.0
    total_hi = 0.0
    protein = fat = carb = 0.0
    known_grams = 0.0
    all_grams = 0.0

    for item in items:
        grams = float(item.get("grams") or 0)
        all_grams += grams
        hit = nutrition.lookup(item["name"])
        if not hit:
            rows.append({
                "name": item["name"],
                "grams": grams,
                "matched": None,
                "kcal": None,
                "kcal_range": None,
                "macros": None,
                "confidence": item.get("confidence", "medium"),
                "note": item.get("note", ""),
                "suggest": nutrition.suggest(item["name"]),
            })
            continue

        if grams <= 0:
            rows.append({
                "name": hit["name"],
                "raw_name": item["name"],
                "grams": 0,
                "matched": hit["matched"],
                "kcal": None,
                "kcal_range": None,
                "macros": None,
                "confidence": "low",
                "note": "模型没给出可信克重，热量未计",
                "suggest": [],
            })
            continue

        known_grams += grams
        kcal = nutrition.energy(grams, hit)
        lo = nutrition.energy(grams * (1 - GRAM_TOLERANCE), hit)
        hi = nutrition.energy(grams * (1 + GRAM_TOLERANCE), hit)
        m = nutrition.macros(grams, hit)
        total += kcal
        total_lo += lo
        total_hi += hi
        protein += m["protein"]
        fat += m["fat"]
        carb += m["carb"]
        rows.append({
            "name": hit["name"],
            "raw_name": item["name"],
            "grams": grams,
            "matched": hit["matched"],
            "kcal": kcal,
            "kcal_range": [lo, hi],
            "macros": m,
            "confidence": item.get("confidence", "medium"),
            "note": item.get("note", ""),
            "suggest": [],
        })

    coverage = (known_grams / all_grams) if all_grams > 0 else 0.0
    unknown = [r for r in rows if r["kcal"] is None]
    return {
        "rows": rows,
        "table_note": table_note,
        "total_kcal": round(total, 1),
        "total_range": [round(total_lo, 1), round(total_hi, 1)],
        "macros": {"protein": round(protein, 1), "fat": round(fat, 1), "carb": round(carb, 1)},
        "coverage": round(coverage, 2),
        "unknown_count": len(unknown),
        "item_count": len(rows),
    }


def verdict(result: dict) -> str:
    """一句人话结论。覆盖率低的时候必须认怂。"""
    if not result["rows"]:
        return "这张照片里没认出食物，换个角度再拍一张。"
    if result["coverage"] < LOW_COVERAGE:
        return (f"只认出 {result['coverage'] * 100:.0f}% 的份量，"
                f"这一盘的热量实际会更高，别拿 {result['total_kcal']:.0f} 千卡当准数。")
    kcal = result["total_kcal"]
    if kcal < 400:
        return f"大概 {kcal:.0f} 千卡，偏轻，一顿正餐的量不太够。"
    if kcal < 800:
        return f"大概 {kcal:.0f} 千卡，正常一顿饭的量。"
    return f"大概 {kcal:.0f} 千卡，这一盘偏重，想控热量可以少盛三分之一主食。"


def render_text(result: dict) -> str:
    """终端里的样子：每样一行，未知的标出来。"""
    lines = []
    if result["table_note"]:
        lines.append(f"场景：{result['table_note']}")
    for row in result["rows"]:
        if row["kcal"] is None:
            hint = f"（相近的有：{'、'.join(row['suggest'])}）" if row["suggest"] else ""
            lines.append(f"· {row['name']} —— 没在营养库里{hint}")
            continue
        lo, hi = row["kcal_range"]
        lines.append(
            f"· {row['name']} {row['grams']:.0f}g —— {row['kcal']:.0f} 千卡"
            f"（{lo:.0f}–{hi:.0f}）"
        )
    lines.append(
        f"合计：{result['total_kcal']:.0f} 千卡（区间 {result['total_range'][0]:.0f}–"
        f"{result['total_range'][1]:.0f}）"
    )
    m = result["macros"]
    lines.append(f"蛋白 {m['protein']:.1f}g · 脂肪 {m['fat']:.1f}g · 碳水 {m['carb']:.1f}g")
    lines.append(f"覆盖率 {result['coverage'] * 100:.0f}%，没算进去的 {result['unknown_count']} 样")
    lines.append(verdict(result))
    return "\n".join(lines)
