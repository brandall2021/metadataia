#!/usr/bin/env python3
"""Servidor OpenAI-compatible de mentira para desarrollo y demos (FASE 9).

No llama a ninguna IA: devuelve metadatos plausibles derivados del texto del
documento que recibe en el prompt, en el formato esperado por el motor de
extraccion (app/extraction/engine.py).

Uso (contenedor en la red de compose, ya que el host bloquea conexiones nuevas
contenedor->host):
  docker run -d --name mockai --network metadato_default \
    -v "$PWD/scripts/mock_ai_server.py:/app/server.py" -w /app \
    python:3.12-slim python server.py
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


def extract_fields(body):
    msgs = body.get("messages", [])
    user = next((m.get("content", "") for m in msgs if m.get("role") == "user"), "")
    lines = user.splitlines()
    fields = {}
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("TITULO DE LA TESIS:"):
            value = stripped.split(":", 1)[1].strip()
            fields["title"] = {
                "value": value,
                "confidence": 0.98,
                "source_page": 1,
                "source_text": stripped[:200],
            }
            break
    if "title" not in fields:
        fields["title"] = {"value": "Tesis sin titulo", "confidence": 0.7, "source_page": 1}
    fields["creator"] = {"value": "Juan Perez", "confidence": 0.95, "source_page": 1}
    fields["date"] = {"value": "2023-05-10", "confidence": 0.92}
    fields["subject"] = [
        {"value": "Inteligencia artificial en bibliotecas", "confidence": 0.9, "source_page": 1},
        {"value": "Metadatos descriptivos", "confidence": 0.88, "source_page": 1},
    ]
    fields["description"] = {
        "value": "Tesis sobre la aplicacion de inteligencia artificial para la "
        "generacion automatica de metadatos en bibliotecas universitarias.",
        "confidence": 0.85,
        "source_page": 1,
    }
    return fields


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/v1/models":
            data = {"object": "list", "data": [{"id": "mock-model", "object": "model"}]}
            self.send_response(200)
        else:
            data = {}
            self.send_response(404)
        self._send(data)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/v1/chat/completions":
            content = json.dumps({"fields": extract_fields(body)}, ensure_ascii=False)
            data = {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "model": body.get("model") or "mock-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 123, "completion_tokens": 45},
            }
            self.send_response(200)
        else:
            data = {"object": "error", "detail": f"endpoint no implementado: {self.path}"}
            self.send_response(404)
        self._send(data)

    def _send(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9999), Handler).serve_forever()