"""Ask the local vision model about one user-selected PDF page."""
from base64 import b64encode
from io import BytesIO
import json
import os
from urllib.request import Request, urlopen


def read_figure(image, question):
    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    body = {
        "model": os.getenv("OLLAMA_VISION_MODEL", "qwen2.5vl:3b"),
        "system": ("Use only the visible evidence on the selected PDF page. "
                   "If the answer is absent, say 'Not visible'. Answer briefly."),
        "prompt": question,
        "images": [b64encode(buffer.getvalue()).decode("ascii")],
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 100},
    }
    base = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    request = Request(base + "/api/generate", json.dumps(body).encode(),
                      {"Content-Type": "application/json"})
    with urlopen(request, timeout=300) as response:
        return json.load(response)["response"].strip()
