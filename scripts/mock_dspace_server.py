#!/usr/bin/env python3
"""Servidor DSpace 9 REST de mentira para desarrollo y demos (FASE 13).

Implementa el subconjunto del contrato REST de DSpace 7/8/9 que usa
``Dspace9Connector`` (backend/app/dspace/connector.py): login con token,
comunidades/colecciones, workspace items, metadata (JSON-Patch), bitstreams
(multipart) y submission.

Uso (contenedor en la red de compose, ya que el host bloquea conexiones nuevas
contenedor->host):
  docker run -d --name mockdspace --network metadato_default \
    -v "$PWD/scripts/mock_dspace_server.py:/app/server.py" -w /app \
    python:3.12-slim python server.py
"""

import json
import re
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

COMMUNITIES = [
    {
        "uuid": "11111111-0000-4000-8000-000000000001",
        "name": "Universidad Nacional de Ejemplo",
        "handle": "123456789/1",
    },
]

COLLECTIONS = [
    {
        "uuid": "22222222-0000-4000-8000-000000000001",
        "name": "Tesis de Grado",
        "handle": "123456789/11",
        "community_uuid": "11111111-0000-4000-8000-000000000001",
    },
    {
        "uuid": "22222222-0000-4000-8000-000000000002",
        "name": "Tesis de Posgrado",
        "handle": "123456789/12",
        "community_uuid": "11111111-0000-4000-8000-000000000001",
    },
]

ITEMS = {}


def collection_for(collection_uuid):
    for c in COLLECTIONS:
        if c["uuid"] == collection_uuid:
            return dict(c)
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _path_parts(self):
        parts = [p for p in self.path.split("?")[0].split("/") if p]
        return parts, dict(re.findall(r"([^?=&]+)=([^&]*)", self.path.split("?")[1] if "?" in self.path else ""))

    def _send(self, data, code=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parts, params = self._path_parts()
        if parts[:2] == ["core", "communities"] and len(parts) == 2:
            self._send({"_embedded": {"communities": COMMUNITIES}})
        elif parts[:2] == ["core", "communities"] and parts[3:4] == ["collections"]:
            cu = parts[2]
            self._send({
                "_embedded": {"collections": [c for c in COLLECTIONS if c["community_uuid"] == cu]}
            })
        elif parts[:2] == ["core", "collections"] and len(parts) == 2:
            self._send({"_embedded": {"collections": COLLECTIONS}})
        elif parts[:2] == ["core", "collections"] and len(parts) == 3:
            col = collection_for(parts[2])
            self._send(col or {"message": "not found"}, 404 if col is None else 200)
        elif parts[:2] == ["core", "items"] and len(parts) == 3:
            item = ITEMS.get(parts[2])
            self._send(item or {"message": "not found"}, 404 if item is None else 200)
        elif parts[:2] == ["submission", "workspaceitems"] and len(parts) == 3:
            ws = ITEMS.get(parts[2])
            self._send(ws or {"message": "not found"}, 404 if ws is None else 200)
        else:
            self._send({"message": "endpoint no implementado: " + self.path}, 404)

    def do_POST(self):
        parts, params = self._path_parts()
        if parts == ["authn", "login"]:
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            token = "tok-mock-" + str(uuid.uuid4())
            payload = token.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif parts == ["submission", "workspaceitems"]:
            col = params.get("parent")
            if not col or not collection_for(col):
                self._send({"message": "coleccion inexistente"}, 422)
                return
            ws = {
                "id": "ws-" + str(uuid.uuid4())[:8],
                "uuid": str(uuid.uuid4()),
                "type": "workspaceitem",
                "_embedded": {"collection": collection_for(col)},
            }
            ws_id = ws["id"]
            ITEMS[ws_id] = ws
            ITEMS[ws["uuid"]] = ws
            self._send(ws, 200)
        elif parts[:2] == ["submission", "workspaceitems"] and len(parts) == 3:
            ws = ITEMS.get(parts[2])
            if ws is None:
                self._send({"message": "not found"}, 404)
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            ctype = self.headers.get("Content-Type", "")
            if "multipart/form-data" in ctype:
                m = re.search(r'filename="([^"]+)"', raw.decode("latin-1"))
                ws["bitstream"] = {
                    "uuid": str(uuid.uuid4()),
                    "name": m.group(1) if m else "documento.pdf",
                }
                self._send(ws["bitstream"], 200)
            else:
                self._apply_patch(ws, raw)
        elif parts == ["workflow", "workflowitems"]:
            length = int(self.headers.get("Content-Length", 0))
            uri = self.rfile.read(length).decode("utf-8").strip()
            ws_uuid = uri.rsplit("/", 1)[-1]
            ws = ITEMS.get(ws_uuid, {})
            item = {
                "uuid": "33333333-0000-4000-8000-00000000000" + str(len(ITEMS))[-1],
                "handle": "123456789/42",
                "name": (ws.get("metadata") or {}).get("dc.title", ["Tesis"])[0],
            }
            ITEMS[item["uuid"]] = item
            self._send({"item": item}, 201)
        else:
            self._send({"message": "endpoint no implementado: " + self.path}, 404)

    def do_PATCH(self):
        parts, _ = self._path_parts()
        if parts[:2] == ["submission", "workspaceitems"] and len(parts) == 3:
            ws = ITEMS.get(parts[2])
            if ws is None:
                self._send({"message": "not found"}, 404)
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            self._apply_patch(ws, raw)
        else:
            self._send({"message": "endpoint no implementado: " + self.path}, 404)

    def _apply_patch(self, ws, raw):
        try:
            ops = json.loads(raw or b"[]")
        except json.JSONDecodeError:
            self._send({"message": "JSON invalido"}, 400)
            return
        metadata = {}
        for op in ops:
            m = re.search(r"^/sections/[^/]+/(.+)$", op.get("path", ""))
            if m:
                metadata[m.group(1)] = [v.get("value") for v in op.get("value", [])]
        ws["metadata"] = metadata
        self._send(ws, 200)


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9998
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()