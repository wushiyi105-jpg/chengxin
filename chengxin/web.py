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
<title>秤心 · 这一餐吃了什么</title>
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

:root{--maxw:1060px;--bg:#f7f7f2;--card:#fffef9;--ink:#252923;--text:#252923;--dim:#6e766c;--line:#d5dbd2;--accent:#5b7f58;--muted:#6e766c}
.wrap{max-width:1060px}
body{background:#f7f7f2;color:#252923;font-family:"PingFang SC","Microsoft YaHei",sans-serif}
h1{color:#252923}
header{max-width:1060px;margin:0 auto}
input,textarea,select{background:#fff;color:#252923;border-color:#d5dbd2;border-radius:2px}
button:not(.ghost):not(.tab){background:#5b7f58;color:#fff;border-radius:2px}
button.ghost{background:transparent!important;color:#5b7f58!important;border:1px solid #d5dbd2!important}
h2,h3{color:#5b7f58}
pre{background:#fafaf6;color:#252923;border-color:#d5dbd2}
.item,.card{border-color:#d5dbd2;background:#fffef9}
.k,.empty,.hint{color:#6e766c}

h1{font-size:clamp(31px,5vw,39px);line-height:1.26}
.prod{display:block;font-size:11px;line-height:1.4;letter-spacing:.18em;font-weight:650;margin-bottom:8px;opacity:.72}
.lede,.sub{max-width:62ch;line-height:1.75}
.route{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1px;margin:16px auto 20px;border:1px solid var(--line);background:var(--line);max-width:var(--maxw)}
.route span{padding:11px 13px;background:var(--card);font-size:12px;line-height:1.5}
.route b{display:block;font-size:10px;letter-spacing:.1em;margin-bottom:3px;opacity:.66}
button{min-height:46px}
input,select{min-height:44px}
pre{white-space:pre-wrap}
@media(max-width:680px){
  .wrap{padding:20px 16px 56px}
  .route{grid-template-columns:1fr}
  h1{font-size:30px!important}
  .row>div{min-width:100%!important}
  button{width:100%}
}

body{background:#f7f7f2;color:#252923}
header{display:block!important;max-width:1060px;margin:0 auto;padding:24px 20px 0;border:0;background:transparent}
header h1{color:#252923;font-size:38px;line-height:1.25;letter-spacing:-.02em}
header .sub{display:block;color:#6e766c;font-size:14px;margin-top:6px}
main{max-width:1060px;margin:0 auto;border-left:1px solid #d5dbd2;border-right:1px solid #d5dbd2;background:#fffef9;min-height:calc(100vh - 140px)}
aside{background:#f2f4ef;border-right:1px solid #d5dbd2;padding:20px}
section{background:#fffef9;padding:22px}
input,textarea,select{background:#fff;color:#252923;border-color:#d2d9d0;border-radius:2px}
input:focus,textarea:focus,select:focus{border-color:#5b7f58;box-shadow:0 0 0 2px #dce7da}
button{background:#5b7f58;border-radius:2px;color:#fff}
button:disabled{opacity:.5}
.drop{border:2px dashed #b9c8b6;background:#fff;color:#5f6e5d;border-radius:2px}
.drop:hover{border-color:#5b7f58;color:#252923}
h2{color:#405a3e;font-size:14px;letter-spacing:.06em}
.k,.empty{color:#6e766c}
.item{border-color:#d5dbd2;background:#fff}


/* mobile-32 */
input[type=text],input[type=number],input[type=email]{background:#fff;color:#252923;border-color:#d5dbd2}

@media(max-width:760px){
  main{grid-template-columns:1fr!important}
  aside{border-right:0!important;border-bottom:1px solid #d5dbd2;width:auto!important}
  section{padding:16px!important}
  .row{flex-wrap:wrap!important}
  .row>div{min-width:100%!important}
  h1{font-size:30px!important}
  .route{grid-template-columns:1fr!important}
  button{min-height:48px}
  pre{overflow-x:auto}
}

/* mobile-height */
@media(max-width:760px){main{min-height:auto!important}aside{min-height:0!important}}

/* mobile-sticky-cta */
.mobile-cta{display:none}
@media(max-width:760px){
  body{padding-bottom:88px}
  .route{grid-template-columns:repeat(3,minmax(0,1fr))!important}
  .route span{padding:8px 8px!important;font-size:11px!important;line-height:1.35!important}
  .route b{font-size:9px!important;margin-bottom:1px!important}
  .mobile-cta{position:fixed;left:12px;right:12px;bottom:12px;z-index:80;display:flex;
    padding:8px;border:1px solid rgba(0,0,0,.08);border-radius:12px;
    background:rgba(255,255,255,.94);backdrop-filter:blur(10px);
    box-shadow:0 10px 28px rgba(16,24,40,.18)}
  .mobile-cta button{width:100%;min-height:52px;margin:0!important;font-size:15px}
}
</style></head><body>
<header><h1><span class="prod">秤心</span>这一餐，实际吃了什么</h1><p class="lede">给只想回看日常饮食的人：拍一餐后逐项确认食物和估计份量，看不清就给可编辑区间或留空；修正后按营养表重算，并显示数据出处。</p></header>
  <div class="route" aria-label="任务步骤"><span><b>01</b>拍一张餐盘</span><span><b>02</b>逐项确认食物</span><span><b>03</b>改份量后重算</span></div>

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
</script>
<script>
(function(){
  var want = "算热量";
  function norm(t){ return String(t||'').replace(/\s+/g,''); }
  var all=[].slice.call(document.querySelectorAll('button'));
  var src=null, fallback=null;
  for(var i=0;i<all.length;i++){
    var b=all[i];
    if(b.offsetParent===null||b.disabled) continue;
    if(!fallback) fallback=b;
    if(norm(b.textContent).indexOf(norm(want))>=0){ src=b; break; }
  }
  if(!src) src=fallback;
  if(!src) return;
  var bar=document.createElement('div'); bar.className='mobile-cta';
  var btn=src.cloneNode(true); btn.removeAttribute('id'); btn.type='button';
  btn.addEventListener('click',function(e){e.preventDefault(); src.click();});
  bar.appendChild(btn); document.body.appendChild(bar);
})();
</script>
</body></html>"""


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
