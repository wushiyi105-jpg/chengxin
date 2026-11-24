"""命令行入口。"""

from __future__ import annotations

import argparse
import base64
import json
import os

from . import llm, meal, nutrition, store, vision

_OPENED: list = []


def _open(args):
    conn = store.connect(args.db)
    _OPENED.append(conn)
    return conn


def cmd_analyze(args) -> int:
    conn = _open(args)
    cfg = None
    if args.api_key or args.base_url or args.model:
        cfg = {}
        if args.api_key:
            cfg["api_key"] = args.api_key
        if args.base_url:
            cfg["base_url"] = args.base_url
        if args.model:
            cfg["model"] = args.model

    for path in args.images:
        if not os.path.isfile(path):
            print(f"✗ 找不到图片：{path}")
            continue
        print(f"· 看图：{os.path.basename(path)}（模型要跑十几秒）", flush=True)
        seen = vision.recognize(path, config=cfg)
        if seen["error"] and not seen["items"]:
            print(f"✗ 识别失败：{seen['error']}")
            continue
        if seen["error"]:
            print(f"! 模型输出没解析完：{seen['error']}（看不全就少算，下面按识别到的算）")

        result = meal.analyze(seen["items"], seen["table_note"])
        name = args.name or os.path.splitext(os.path.basename(path))[0]
        mid = store.save_meal(conn, name, os.path.abspath(path), store.file_sha(path),
                              seen["items"], result, note=args.note or "")

        print(f"\n=== 餐 [{mid}] {name} · {len(seen['items'])} 样 ===")
        if seen["table_note"]:
            print(f"场景：{seen['table_note']}")
        for row in result["rows"]:
            if row["kcal"] is None:
                hint = f"（相近的有：{'、'.join(row['suggest'])}）" if row["suggest"] else ""
                print(f"· {row['name']} —— 没在营养库里{hint}")
                continue
            lo, hi = row["kcal_range"]
            print(f"· {row['name']} {row['grams']:.0f}g（{row['matched']}） —— "
                  f"{row['kcal']:.0f} 千卡（{lo:.0f}–{hi:.0f}，把握 {row['confidence']}）")
        print(f"合计 {result['total_kcal']:.0f} 千卡，区间 "
              f"{result['total_range'][0]:.0f}–{result['total_range'][1]:.0f}；"
              f"覆盖率 {result['coverage'] * 100:.0f}%")
        print(meal.verdict(result))
        if args.json:
            print(json.dumps({"id": mid, "recognized": seen, "analysis": result},
                             ensure_ascii=False, indent=2))
    return 0


def cmd_list(args) -> int:
    conn = _open(args)
    rows = store.list_meals(conn)
    if not rows:
        print("还没有记录。先 python -m chengxin analyze samples/meal-1.jpg")
        return 0
    print(f"{'ID':<4}{'千卡':<8}{'覆盖率':<8}{'时间':<20}名字")
    for r in rows:
        a = r["analysis"]
        print(f"{r['id']:<4}{a.get('total_kcal', 0):<8}{a.get('coverage', 0):<8}"
              f"{r['created_at']:<20}{r['name']}")
    return 0


def cmd_show(args) -> int:
    conn = _open(args)
    row = store.get_meal(conn, args.id)
    if not row:
        print(f"✗ 没有 id={args.id} 的餐")
        return 1
    result = row["analysis"]
    print(f"=== 餐 [{row['id']}] {row['name']} · {row['created_at']} ===")
    print(f"图片：{row['image_path']}")
    if row["note"]:
        print(f"备注：{row['note']}")
    print(meal.render_text({**result, "table_note": row["note"] or result.get("table_note", "")}))
    if args.json:
        print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


def cmd_rm(args) -> int:
    conn = _open(args)
    if not store.get_meal(conn, args.id):
        print(f"✗ 没有 id={args.id} 的餐")
        return 1
    store.delete_meal(conn, args.id)
    print(f"· 餐 [{args.id}] 已删除")
    return 0


def cmd_stats(args) -> int:
    conn = _open(args)
    s = store.stats(conn)
    print(f"记录 {s['meals']} 餐，平均 {s['avg_kcal']:.0f} 千卡，累计 {s['total_kcal']:.0f} 千卡")
    return 0


def cmd_foods(args) -> int:
    if args.search:
        hit = nutrition.lookup(args.search)
        if hit:
            print(f"{hit['name']}：{hit['kcal']} 千卡/100g（蛋白 {hit['p']}g，脂肪 {hit['f']}g，"
                  f"碳水 {hit['c']}g）")
        else:
            print(f"库里没有「{args.search}」，相近的：{'、'.join(nutrition.suggest(args.search))}")
        return 0
    print(f"营养库共 {len(nutrition.FOODS)} 条：")
    for i, (name, item) in enumerate(sorted(nutrition.FOODS.items()), 1):
        print(f"{i:>3}. {name} {item['kcal']} 千卡/100g", end="\n" if i % 3 == 0 else "    ")
    print()
    return 0


def cmd_serve(args) -> int:
    from . import web

    conn = _open(args)
    web.serve(conn, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="chengxin", description="看盘子算热量：模型认食物，本地表算热量。")
    p.add_argument("--db", default="data/chengxin.db")
    p.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    p.add_argument("--api-key")
    p.add_argument("--base-url")
    p.add_argument("--model")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="分析一张或几张餐盘照片")
    a.add_argument("images", nargs="+")
    a.add_argument("--name")
    a.add_argument("--note")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_analyze)

    sub.add_parser("list", help="记录列表").set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="看某一餐的明细")
    s.add_argument("id", type=int)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_show)

    r = sub.add_parser("rm", help="删一餐")
    r.add_argument("id", type=int)
    r.set_defaults(func=cmd_rm)

    sub.add_parser("stats", help="统计").set_defaults(func=cmd_stats)

    f = sub.add_parser("foods", help="查营养库")
    f.add_argument("--search")
    f.set_defaults(func=cmd_foods)

    sv = sub.add_parser("serve", help="起 Web")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8771)
    sv.set_defaults(func=cmd_serve)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    finally:
        while _OPENED:
            try:
                _OPENED.pop().close()
            except Exception:  # noqa: BLE001
                pass
