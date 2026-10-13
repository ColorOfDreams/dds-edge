"""Local browser demo for the distracted-driver classifier.

Run from the repository root::

    python -m dds_edge.dl.web_demo --run effl0_clean --runs-dir dds-edge-runs

The server binds to localhost by default. Images are decoded and classified in
memory only; this small demo deliberately does not write uploads to disk.
"""
import argparse
import base64
import io
import json
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import torch
from PIL import Image, UnidentifiedImageError

from dds_edge.dl.common import build_model, build_transform


LABELS = {
    "normal": ("Lái xe bình thường", "Không phát hiện hành vi gây xao nhãng."),
    "phone": ("Dùng điện thoại", "Có dấu hiệu nhắn tin hoặc cầm điện thoại."),
    "device_ops": ("Thao tác thiết bị", "Có dấu hiệu thao tác radio hoặc thiết bị trong xe."),
    "eat_drink": ("Ăn hoặc uống", "Có dấu hiệu ăn, uống trong khi lái xe."),
    "reach_grooming": ("Với tay / chỉnh trang", "Có dấu hiệu với tay, chải tóc hoặc trang điểm."),
    "talk_passenger": ("Nói chuyện với hành khách", "Có dấu hiệu quay sang nói chuyện với hành khách."),
}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


PAGE = r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DDS-Edge · Driver Focus Monitor</title><style>
:root{--ink:#eaf0ff;--muted:#9aa8c7;--line:#2a3654;--panel:#101a30;--bg:#07101f;--blue:#64b5ff;--green:#4fdfaf;--amber:#ffc861;--red:#ff7183}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 15% 5%,#183769 0,transparent 32rem),var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{width:min(1080px,calc(100% - 32px));margin:auto;padding:48px 0 56px}.eyebrow{color:var(--blue);font-weight:700;font-size:.78rem;letter-spacing:.13em;text-transform:uppercase}h1{font-size:clamp(2.15rem,6vw,4.7rem);letter-spacing:-.055em;line-height:.98;margin:14px 0 18px;max-width:780px}header p{color:var(--muted);max-width:680px;line-height:1.6;margin:0 0 36px}.grid{display:grid;grid-template-columns:1.18fr .82fr;gap:20px}.card{border:1px solid var(--line);border-radius:22px;background:linear-gradient(145deg,rgba(21,36,66,.94),rgba(11,20,39,.94));box-shadow:0 20px 60px rgba(0,0,0,.25)}
#drop{min-height:420px;display:grid;place-items:center;overflow:hidden;position:relative;padding:24px;border:1.5px dashed #4c628f;cursor:pointer;transition:.2s}#drop.hover{border-color:var(--blue);background:#14284b}#drop img{display:none;width:100%;max-height:510px;object-fit:contain;border-radius:13px}#prompt{text-align:center;color:var(--muted)}#prompt strong{display:block;color:var(--ink);font-size:1.2rem;margin:12px 0 5px}input{display:none}.icon{width:56px;height:56px;border-radius:18px;background:#223b68;display:grid;place-items:center;margin:auto;color:var(--blue);font-size:1.75rem}
.result{padding:28px;display:flex;flex-direction:column;min-height:420px}.state{color:var(--muted);margin:auto;text-align:center;line-height:1.6}.badge{font-size:.78rem;letter-spacing:.1em;text-transform:uppercase;font-weight:750;color:var(--blue);margin-bottom:15px}.label{font-size:2rem;font-weight:760;letter-spacing:-.04em;line-height:1.05}.description{color:var(--muted);line-height:1.55;margin:12px 0 25px}.meter{height:9px;background:#283450;border-radius:10px;overflow:hidden}.meter span{height:100%;display:block;background:linear-gradient(90deg,var(--blue),var(--green));border-radius:inherit}.confidence{display:flex;justify-content:space-between;align-items:baseline;margin:10px 0 7px;color:var(--muted)}.confidence b{font-size:1.25rem;color:var(--ink)}.rows{margin-top:26px;border-top:1px solid var(--line)}.row{padding:13px 0;border-bottom:1px solid var(--line);display:grid;grid-template-columns:1fr auto;gap:16px;color:var(--muted)}.row b{color:var(--ink)}.meta{margin-top:auto;color:var(--muted);font-size:.86rem}.error{color:var(--red)}footer{display:flex;gap:9px;align-items:flex-start;color:var(--muted);font-size:.84rem;line-height:1.5;margin-top:22px}footer span{color:var(--amber)}@media(max-width:760px){main{padding-top:30px}.grid{grid-template-columns:1fr}#drop{min-height:300px}.result{min-height:330px}}
</style></head><body><main><header><div class="eyebrow">DDS-Edge · on-device research demo</div><h1>Driver focus, checked in one frame.</h1><p>Tải lên một ảnh từ camera trong cabin. Mô hình EfficientNet-Lite0 sẽ phân loại hành vi lái xe trong 6 nhóm.</p></header><section class="grid"><label id="drop" class="card" for="file"><input id="file" type="file" accept="image/jpeg,image/png,image/webp"><div id="prompt"><div class="icon">↑</div><strong>Thả ảnh vào đây</strong><small>hoặc chọn ảnh · JPG, PNG, WebP · tối đa 8 MB</small></div><img id="preview" alt="Ảnh đã chọn"></label><article class="card result"><div id="empty" class="state">Chọn một khung hình để bắt đầu<br>phân tích hành vi lái xe.</div><div id="loading" class="state" hidden>Đang chạy mô hình…</div><div id="output" hidden><div class="badge">Kết quả phân loại</div><div id="label" class="label"></div><p id="desc" class="description"></p><div class="confidence"><span>Độ tin cậy</span><b id="confidence"></b></div><div class="meter"><span id="bar"></span></div><div id="rows" class="rows"></div></div><div id="meta" class="meta"></div></article></section><footer><span>●</span><div>Ảnh chỉ được xử lý trong bộ nhớ của máy đang chạy demo, không được lưu. Đây là công cụ nghiên cứu hỗ trợ quan sát, không phải hệ thống cảnh báo an toàn.</div></footer></main><script>
const file=document.querySelector('#file'),drop=document.querySelector('#drop'),preview=document.querySelector('#preview'),prompt=document.querySelector('#prompt');
const empty=document.querySelector('#empty'),loading=document.querySelector('#loading'),output=document.querySelector('#output'),meta=document.querySelector('#meta');
function show(id,on){document.querySelector(id).hidden=!on} function displayError(msg){show('#empty',true);empty.innerHTML='<span class="error">'+msg+'</span>';show('#loading',false);show('#output',false);meta.textContent=''}
async function run(f){if(!f)return;if(!f.type.startsWith('image/'))return displayError('Vui lòng chọn một tệp hình ảnh.');if(f.size>8*1024*1024)return displayError('Ảnh lớn hơn giới hạn 8 MB.');preview.src=URL.createObjectURL(f);preview.style.display='block';prompt.style.display='none';show('#empty',false);show('#output',false);show('#loading',true);meta.textContent='';try{const data=await new Promise((ok,bad)=>{const r=new FileReader;r.onload=()=>ok(r.result);r.onerror=bad;r.readAsDataURL(f)});const res=await fetch('/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:data})});const out=await res.json();if(!res.ok)throw Error(out.error||'Không thể phân tích ảnh.');document.querySelector('#label').textContent=out.label_vi;document.querySelector('#desc').textContent=out.description;document.querySelector('#confidence').textContent=Math.round(out.confidence*100)+'%';document.querySelector('#bar').style.width=(out.confidence*100)+'%';document.querySelector('#rows').innerHTML=out.top3.map((x,i)=>'<div class="row"><span>'+(i+1)+'. '+x.label_vi+'</span><b>'+Math.round(x.confidence*100)+'%</b></div>').join('');meta.textContent='Suy luận CPU: '+out.latency_ms.toFixed(1)+' ms · '+out.model;show('#loading',false);show('#output',true)}catch(e){displayError(e.message)}}
file.onchange=e=>run(e.target.files[0]);['dragenter','dragover'].forEach(n=>drop.addEventListener(n,e=>{e.preventDefault();drop.classList.add('hover')}));['dragleave','drop'].forEach(n=>drop.addEventListener(n,e=>{e.preventDefault();drop.classList.remove('hover')}));drop.addEventListener('drop',e=>run(e.dataTransfer.files[0]));
</script></body></html>"""


class Predictor:
    def __init__(self, checkpoint: Path):
        if not checkpoint.is_file():
            raise FileNotFoundError(f"Không tìm thấy checkpoint: {checkpoint}")
        ck = torch.load(checkpoint, map_location="cpu", weights_only=False)
        self.names = ck["class_names"]
        self.model = build_model(ck["arch"], len(self.names), pretrained=False)
        self.model.load_state_dict(ck["state_dict"])
        self.model.eval()
        self.transform = build_transform(ck["img_size"], train=False, aug=False)
        self.model_name = ck["arch"].replace("_", " ").title()
        self.lock = threading.Lock()

    @torch.inference_mode()
    def predict(self, raw: bytes) -> dict:
        try:
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("Tệp ảnh không hợp lệ hoặc bị hỏng.") from exc
        x = self.transform(image).unsqueeze(0)
        with self.lock:
            started = time.perf_counter()
            probabilities = self.model(x).softmax(1)[0].cpu().numpy()
            latency_ms = (time.perf_counter() - started) * 1000
        order = np.argsort(probabilities)[::-1]
        best = int(order[0])
        label, description = LABELS.get(self.names[best], (self.names[best], ""))
        return {
            "label": self.names[best], "label_vi": label, "description": description,
            "confidence": float(probabilities[best]), "latency_ms": latency_ms,
            "model": self.model_name,
            "top3": [
                {"label": self.names[int(i)], "label_vi": LABELS.get(self.names[int(i)], (self.names[int(i)], ""))[0],
                 "confidence": float(probabilities[int(i)])}
                for i in order[:3]
            ],
        }


def make_handler(predictor: Predictor):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, body, content_type="application/json; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path != "/":
                self.respond(HTTPStatus.NOT_FOUND, b'{"error":"Not found"}')
                return
            self.respond(HTTPStatus.OK, PAGE.encode("utf-8"), "text/html; charset=utf-8")

        def do_POST(self):
            if self.path != "/predict":
                self.respond(HTTPStatus.NOT_FOUND, b'{"error":"Not found"}')
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_UPLOAD_BYTES * 2:
                    raise ValueError("Ảnh vượt quá giới hạn 8 MB.")
                payload = json.loads(self.rfile.read(length))
                source = payload.get("image", "")
                if not isinstance(source, str) or not source.startswith("data:image/") or "," not in source:
                    raise ValueError("Dữ liệu ảnh không hợp lệ.")
                raw = base64.b64decode(source.split(",", 1)[1], validate=True)
                if len(raw) > MAX_UPLOAD_BYTES:
                    raise ValueError("Ảnh vượt quá giới hạn 8 MB.")
                result = predictor.predict(raw)
            except (ValueError, json.JSONDecodeError, base64.binascii.Error) as exc:
                self.respond(HTTPStatus.BAD_REQUEST, json.dumps({"error": str(exc)}).encode())
                return
            self.respond(HTTPStatus.OK, json.dumps(result).encode())

        def log_message(self, fmt, *args):
            return
    return Handler


def main():
    parser = argparse.ArgumentParser(description="Run the DDS-Edge local browser demo.")
    parser.add_argument("--run", default="effl0_clean", help="run directory containing best.pt")
    parser.add_argument("--runs-dir", default="dds-edge-runs")
    parser.add_argument("--host", default="127.0.0.1", help="localhost by default for privacy")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    predictor = Predictor(Path(args.runs_dir) / args.run / "best.pt")
    server = ThreadingHTTPServer((args.host, args.port), make_handler(predictor))
    print(f"DDS-Edge demo is running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
