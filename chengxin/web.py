"""Web 端：选一张图传上来，右边出结果。

上传走 JSON + base64，不解析 multipart——http.server 里手撸 multipart 边界太容易出错，
而浏览器读文件转 base64 本来就是一行 FileReader 的事。
"""

from __future__ import annotations

import base64
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import meal, store, vision

UPLOAD_DIR = "data/uploads"
MAX_BODY = 12 * 1024 * 1024

PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>秤心 · 这盘多少热量</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0b0f14;color:#c9d1d9;font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
header{padding:16px 24px;border-bottom:1px solid #21262d;display:flex;gap:12px;align-items:baseline}
h1{margin:0;font-size:18px;color:#7ee787}
.sub{color:#8b949e;font-size:13px}
main{display:grid;grid-template-columns:340px 1fr;gap:0;min-height:calc(100vh - 60px)}
aside{border-right:1px solid #21262d;padding:18px}
section{padding:20px 24px}
input{width:100%;background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:8px;padding:8px 10px;margin-bottom:10px;font:14px inherit}
button{background:#238636;color:#fff;border:0;border-radius:6px;padding:8px 14px;font:14px inherit;cursor:pointer}
button:disabled{opacity:.6;cursor:wait}
.drop{border:1px dashed #30363d;border-radius:10px;padding:22px;text-align:center;color:#8b949e;font-size:13px;margin-bottom:12px}
.drop.has{border-color:#7ee787;color:#7ee787}
.kcal{font-size:34px;font-weight:600;color:#7ee787}
.k{color:#8b949e;font-size:13px}
.row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #161b22}
.bar{height:6px;background:#21262d;border-radius:3px;overflow:hidden;margin:10px 0}
.bar i{display:block;height:100%;background:#7ee787}
.item{padding:10px;border:1px solid #21262d;border-radius:8px;margin-bottom:8px}
.item b{font-weight:600}
.warn{color:#e3b341}
h2{font-size:15px;margin:22px 0 8px;color:#c9d1d9}
</style></head><body>
<header><h1>秤心</h1><span class="sub">模型只认食物和克重，热量由本地营养库乘出来</span></header>
<main>
<aside>
  <div class="drop" id="drop">点这里选一张餐盘照片<br><span class="k">jpg / png，越正对盘子越准</span></div>
  <input type="file" id="file" accept="image/*" style="display:none">
  <input id="name" placeholder="这顿叫什么，比如 周三午饭">
  <input id="note" placeholder="备注（比如：公司食堂，饭只吃了一半）">
  <button id="go" disabled>算热量</button>
  <p class="k" id="status"></p>
  <h2>以前的</h2>
  <div id="list"></div>
</aside>
<section id="out"><p class="k">上传一张照片，右边出这一盘的热量。</p></section>
</main>
<script>
const $ = s => document.querySelector(s);
const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let picked = null;

$('#drop').onclick = () => $('#file').click();
$('#file').onchange = e => {
  const f = e.target.files[0]; if(!f) return;
  picked = f;
  $('#drop').textContent = f.name;
  $('#drop').classList.add('has');
  $('#go').disabled = false;
  if(!$('#name').value) $('#name').value = f.name.replace(/\\.[^.]+$/, '');
};

$('#go').onclick = () => {
  if(!picked) return;
  const reader = new FileReader();
  reader.onload = async () => {
    $('#go').disabled = true;
    $('#status').textContent = '正在看图，模型要跑十几秒…';
    const b64 = reader.result.split(',')[1];
    const r = await fetch('/api/analyze', {method:'POST', body: JSON.stringify({
      name: $('#name').value, note: $('#note').value,
      filename: picked.name, image_b64: b64
    })});
    const d = await r.json();
    $('#go').disabled = false;
    if(d.error){ $('#status').textContent = ''; alert(d.error); return; }
    $('#status').textContent = '';
    render(d.meal);
    loadList();
  };
  reader.readAsDataURL(picked);
};

function render(m){
  const a = m.analysis;
  const lo = a.total_range[0], hi = a.total_range[1];
  let html = `<div class="kcal">${Math.round(a.total_kcal)} <span class="k">千卡</span></div>
    <div class="k">区间 ${Math.round(lo)}–${Math.round(hi)} · 覆盖率 ${Math.round(a.coverage*100)}% ·
    蛋白 ${a.macros.protein}g / 脂肪 ${a.macros.fat}g / 碳水 ${a.macros.carb}g</div>
    <div class="bar"><i style="width:${Math.min(100, a.coverage*100)}%"></i></div>`;
  html += a.rows.map(r => r.kcal === null
    ? `<div class="row"><span>${esc(r.name)}</span><span class="warn">没在库里${r.suggest.length? '（'+esc(r.suggest.join('、'))+'）':''}</span></div>`
    : `<div class="row"><span>${esc(r.name)} <span class="k">${r.grams}g · ${esc(r.confidence)}</span></span>
       <span>${Math.round(r.kcal)} 千卡</span></div>`).join('');
  html += `<p class="k">${esc(esc(m.note) || esc(a.table_note))}</p>`;
  $('#out').innerHTML = html;
}

async function loadList(){
  const r = await fetch('/api/meals');
  const items = (await r.json()).items;
  $('#list').innerHTML = items.map(m => `<div class="item" data-id="${m.id}">
    <b>${esc(m.name)}</b> <span class="k">${Math.round(m.total_kcal)} 千卡</span>
    <div class="k">${esc(m.created_at)}</div></div>`).join('') || '<p class="k">还没有</p>';
  document.querySelectorAll('.item').forEach(el => el.onclick = async () => {
    const r = await fetch('/api/meal?id=' + el.dataset.id);
    render((await r.json()).meal);
  });
}
loadList();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    conn = None

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/meals":
            rows = store.list_meals(self.conn)
            self._json({"items": [{
                "id": r["id"], "name": r["name"],
                "total_kcal": r["analysis"].get("total_kcal", 0),
                "created_at": r["created_at"],
            } for r in rows]})
            return
        if parsed.path == "/api/meal":
            try:
                mid = int(qs.get("id", ["0"])[0])
            except ValueError:
                self._json({"error": "id 不合法"}, 400)
                return
            row = store.get_meal(self.conn, mid)
            if not row:
                self._json({"error": "没有这一餐"}, 404)
                return
            self._json({"meal": row})
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/analyze":
            self._json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._json({"error": "图片太大了，超过 12MB"}, 413)
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "请求体不是合法 JSON"}, 400)
            return

        image_b64 = body.get("image_b64") or ""
        if not image_b64:
            self._json({"error": "没有图片"}, 400)
            return
        try:
            raw = base64.b64decode(image_b64, validate=True)
        except (ValueError, TypeError):
            self._json({"error": "图片 base64 解不开"}, 400)
            return
        if len(raw) < 24:
            # base64 模块对非法字符是「尽力而为」，不校验就解出一个空串来
            self._json({"error": "图片内容为空或太短"}, 400)
            return

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        filename = os.path.basename(body.get("filename") or "upload.jpg")
        ext = os.path.splitext(filename)[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            ext = ".jpg"
        digest = __import__("hashlib").sha256(raw).hexdigest()[:16]
        path = os.path.join(UPLOAD_DIR, f"{digest}{ext}")
        with open(path, "wb") as f:
            f.write(raw)

        seen = vision.recognize(path)
        if seen["error"] and not seen["items"]:
            self._json({"error": seen["error"]}, 502)
            return

        result = meal.analyze(seen["items"], seen["table_note"])
        name = (body.get("name") or "").strip() or filename
        mid = store.save_meal(self.conn, name, os.path.abspath(path), digest,
                              seen["items"], result, note=(body.get("note") or "").strip())
        row = store.get_meal(self.conn, mid)
        self._json({"meal": row, "warning": seen["error"]})


def make_server(conn, host: str = "127.0.0.1", port: int = 8771) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"conn": conn})
    return ThreadingHTTPServer((host, port), handler)


def serve(conn, host: str = "127.0.0.1", port: int = 8771):
    httpd = make_server(conn, host, port)
    print(f"秤心已起：http://{host}:{port}  （Ctrl+C 退出）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n再见。")
    finally:
        httpd.server_close()
