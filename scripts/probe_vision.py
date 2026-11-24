"""探测：本地两张 key 到底能不能看图。

用法：python scripts/probe_vision.py <图片路径>
"""

import base64
import json
import os
import sys
import urllib.error
import urllib.request

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")


def load_env():
    env = {}
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def call(base, key, model, image_b64, label):
    url = base.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是营养师。只看图片，不要猜图外的东西。"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "这张餐盘里有哪些食物？每样大概多少克？只列清单，不要计算热量。"},
                    {"type": "image_url", "image_url": {"url": image_b64}},
                ],
            },
        ],
        "temperature": 0.2,
        "max_tokens": 800,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
            "User-Agent": "chengxin-probe/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
        content = data["choices"][0]["message"].get("content") or ""
        print(f"\n===== {label} ({model}) =====")
        print(content.strip() or "(空正文)")
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        print(f"\n===== {label} ({model}) 失败 =====")
        print(f"HTTP {e.code}: {body}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"\n===== {label} ({model}) 异常 =====")
        print(repr(e))
        return False


def main():
    if len(sys.argv) < 2:
        raise SystemExit("用法：python scripts/probe_vision.py <图片路径>")
    path = sys.argv[1]
    with open(path, "rb") as f:
        raw = f.read()
    b64 = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    env = load_env()

    call(
        env["LLM_BASE_URL"],
        env["LLM_API_KEY"],
        env.get("LLM_MODEL", "deepseek-flash"),
        b64,
        "DeepSeek",
    )
    if env.get("VISION_API_KEY"):
        call(
            env["VISION_BASE_URL"],
            env["VISION_API_KEY"],
            env.get("VISION_MODEL", "glm-4.6v-flash"),
            b64,
            "智谱",
        )


if __name__ == "__main__":
    main()
