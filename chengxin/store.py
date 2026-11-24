"""SQLite：每顿饭一行，记着原图哈希、识别结果、算出来的热量。

同一张图重复分析就覆盖，不堆历史版本——你只是想看这一盘现在算多少。
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime

_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    image_sha TEXT NOT NULL,
    image_path TEXT NOT NULL,
    items TEXT NOT NULL DEFAULT '[]',
    analysis TEXT NOT NULL DEFAULT '{}',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_meals_sha ON meals(image_sha);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(path: str = "data/chengxin.db") -> sqlite3.Connection:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def file_sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def save_meal(conn, name: str, image_path: str, image_sha: str, items: list[dict],
              analysis: dict, note: str = "") -> int:
    with _LOCK:
        row = conn.execute("SELECT id FROM meals WHERE image_sha=?", (image_sha,)).fetchone()
        if row:
            conn.execute(
                "UPDATE meals SET name=?, items=?, analysis=?, note=?, image_path=?, created_at=? WHERE id=?",
                (name, json.dumps(items, ensure_ascii=False),
                 json.dumps(analysis, ensure_ascii=False), note, image_path, now(), row["id"]),
            )
            conn.commit()
            return row["id"]
        cur = conn.execute(
            """INSERT INTO meals(name, image_sha, image_path, items, analysis, note, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (name, image_sha, image_path, json.dumps(items, ensure_ascii=False),
             json.dumps(analysis, ensure_ascii=False), note, now()),
        )
        conn.commit()
        return cur.lastrowid


def list_meals(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM meals ORDER BY id DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        a = json.loads(d["analysis"] or "{}")
        d["analysis"] = a
        d["items"] = json.loads(d["items"] or "[]")
        out.append(d)
    return out


def get_meal(conn, meal_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM meals WHERE id=?", (meal_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["analysis"] = json.loads(d["analysis"] or "{}")
    d["items"] = json.loads(d["items"] or "[]")
    return d


def delete_meal(conn, meal_id: int) -> None:
    with _LOCK:
        conn.execute("DELETE FROM meals WHERE id=?", (meal_id,))
        conn.commit()


def stats(conn) -> dict:
    rows = conn.execute("SELECT analysis FROM meals").fetchall()
    total_kcal = 0.0
    for row in rows:
        try:
            total_kcal += float(json.loads(row["analysis"] or "{}").get("total_kcal") or 0)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return {
        "meals": len(rows),
        "avg_kcal": round(total_kcal / len(rows), 1) if rows else 0,
        "total_kcal": round(total_kcal, 1),
    }
