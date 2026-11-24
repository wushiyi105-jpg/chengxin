"""看图：让视觉模型说出盘子里有什么、大概多重。

关键约束：不许它算热量。它只负责「这是什么、多少克」，
热量交给本地营养库乘——这样每个数都能追到出处，而不是模型随口一个 850 千卡。
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

from . import llm

DEFAULT_PROMPT = """看这张餐盘照片，列出你能看见的食物。

要求：
- 只列看得见的，看不清的不要补
- 每样给一个克数估计（整数），按盘子大小和常见份量估
- 不要计算热量、蛋白质、脂肪，一个字都不要提「千卡」
- 拿不准的写 low，别硬编

只输出 JSON：
{"items": [{"name": "", "grams": 0, "confidence": "high|medium|low", "note": ""}],
 "table_note": "一句话：这是什么场景的餐，比如家常午饭"}"""

MAX_BYTES = 900_000


def vision_config() -> dict:
    """视觉通道单独一套环境变量，没配就退回通用 LLM 配置。"""
    llm.load_dotenv()
    key = os.environ.get("VISION_API_KEY") or os.environ.get("LLM_API_KEY")
    base = os.environ.get("VISION_BASE_URL") or os.environ.get("LLM_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4"
    model = os.environ.get("VISION_MODEL") or "glm-4.6v-flashx"
    return {"api_key": key, "base_url": base, "model": model}


def encode_image(path: str) -> str:
    """读图并转成 data URL。太大的图先用 Pillow 缩一下（Pillow 是可选依赖）。"""
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) > MAX_BYTES:
        try:
            from PIL import Image
        except ImportError:
            Image = None
        if Image is not None:
            import io

            img = Image.open(io.BytesIO(raw)).convert("RGB")
            scale = (MAX_BYTES / len(raw)) ** 0.5
            size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
            img = img.resize(size)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=82)
            raw = buf.getvalue()
            ext = "jpeg"
        else:
            ext = os.path.splitext(path)[1].lstrip(".").lower() or "jpeg"
    else:
        ext = os.path.splitext(path)[1].lstrip(".").lower() or "jpeg"
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64," + base64.b64encode(raw).decode("ascii")


def _post(url: str, payload: dict, key: str, timeout: int = 120) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
            "User-Agent": "chengxin/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:  # noqa: BLE001
            pass
        raise llm.LLMError(f"视觉接口返回 {e.code}: {detail or e.reason}") from e
    except urllib.error.URLError as e:
        raise llm.LLMError(f"连不上视觉接口 {url}: {e.reason}") from e


def recognize(image_path: str, prompt: str = DEFAULT_PROMPT, config: dict | None = None,
              timeout: int = 120) -> dict:
    """返回 {items, table_note, raw, error}。失败不抛，把 error 带回去。"""
    cfg = {**vision_config(), **(config or {})}
    if not cfg.get("api_key"):
        return {"items": [], "table_note": "", "raw": "", "error": "未配置 VISION_API_KEY"}
    if not os.path.isfile(image_path):
        return {"items": [], "table_note": "", "raw": "", "error": f"找不到图片：{image_path}"}

    data_url = encode_image(image_path)
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": "你是营养师，只描述照片里看得见的食物，不推测、不算热量。"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
    }
    try:
        body = _post(cfg["base_url"].rstrip("/") + "/chat/completions", payload, cfg["api_key"], timeout)
        content = (body["choices"][0]["message"].get("content") or "").strip()
    except (llm.LLMError, KeyError, IndexError, TypeError) as e:
        return {"items": [], "table_note": "", "raw": "", "error": str(e)}

    if not content:
        return {"items": [], "table_note": "", "raw": "", "error": "模型返回空正文"}
    try:
        parsed = llm.extract_json(content)
    except llm.LLMError as e:
        return {"items": [], "table_note": "", "raw": content, "error": str(e)}

    if not isinstance(parsed, dict):
        return {"items": [], "table_note": "", "raw": content, "error": "返回不是对象"}

    items = []
    for row in parsed.get("items") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        try:
            grams = float(row.get("grams") or 0)
        except (TypeError, ValueError):
            grams = 0.0
        if grams <= 0 or grams > 2000:
            grams = 0.0  # 明显不合理的克重当没估出来，交给下游标不确定
        conf = row.get("confidence") if row.get("confidence") in ("high", "medium", "low") else "medium"
        items.append({
            "name": name,
            "grams": round(grams, 1),
            "confidence": conf,
            "note": str(row.get("note") or "")[:80],
        })
    table_note = str(parsed.get("table_note") or "").strip()
    # 模型爱在字段里再抄一遍提示词的标签：「一句话：这是家常午饭」
    for prefix in ("一句话：", "一句话:", "场景：", "场景:"):
        if table_note.startswith(prefix):
            table_note = table_note[len(prefix):].strip()

    return {
        "items": items,
        "table_note": table_note[:120],
        "raw": content,
        "error": "",
    }
