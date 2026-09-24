"""Conector para repositorios de metadatos (FASE 13).

Interfaz ``RepositoryConnector`` y su implementación para DSpace 9 REST
(API ``/server/api`` de DSpace 7/8/9). Todas las operaciones se realizan
desde el backend; el frontend nunca habla con DSpace directamente.
"""

import httpx
import time

from app.core.security import decrypt_secret
from app.models import Repository

DSpaceError = RuntimeError


def _resolve_credential(stored: str | None) -> str | None:
    """Devuelve la credencial en claro.

    Las credenciales nuevas se guardan cifradas en ``configuration_json``;
    si el valor no descifra (credenciales legacy guardadas en claro) se
    devuelve tal cual para no romper configuraciones existentes.
    """
    if not stored:
        return stored
    try:
        return decrypt_secret(stored)
    except Exception:  # noqa: BLE001
        return stored


class RepositoryConnector:
    """Interfaz común de conectores de repositorio."""

    def authenticate(self) -> str:
        raise NotImplementedError

    def get_communities(self, token: str | None = None) -> list[dict]:
        raise NotImplementedError

    def get_collections(self, community_uuid: str | None = None, token: str | None = None) -> list[dict]:
        raise NotImplementedError

    def get_collection(self, collection_uuid: str, token: str | None = None) -> dict:
        raise NotImplementedError

    def create_workspace_item(self, collection_uuid: str, token: str | None = None) -> dict:
        raise NotImplementedError

    def add_metadata(self, workspace_id, metadata: dict, token: str | None = None) -> None:
        raise NotImplementedError

    def upload_bitstream(self, workspace_id, filename: str, content: bytes, token: str | None = None) -> dict:
        raise NotImplementedError

    def get_workspace_item(self, workspace_id, token: str | None = None) -> dict:
        raise NotImplementedError

    def submit_workspace_item(self, workspace_id, token: str | None = None) -> dict:
        raise NotImplementedError

    def get_item(self, item_uuid: str, token: str | None = None) -> dict:
        raise NotImplementedError


class Dspace9Connector(RepositoryConnector):
    """Conector REST para DSpace 7/8/9 (contrato de la API de submission)."""

    def __init__(
        self,
        api_url: str,
        username: str | None = None,
        credential: str | None = None,
        client: httpx.Client | None = None,
        section: str = "traditionalpageone",
    ):
        self.api_url = api_url.rstrip("/")
        self.username = username
        self.credential = credential
        self.section = section
        self._client = client or httpx.Client(timeout=30.0)
        self._csrf_token: str | None = None

    def _request(self, method: str, path: str, token: str | None = None, **kwargs) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}))
        if token:
            headers.setdefault("Authorization", f"Bearer {token}")
        if method.upper() not in {"GET", "HEAD", "OPTIONS"} and self._csrf_token:
            headers.setdefault("X-XSRF-TOKEN", self._csrf_token)
        resp = self._client.request(method, f"{self.api_url}{path}", headers=headers, **kwargs)
        csrf_token = resp.headers.get("DSPACE-XSRF-TOKEN")
        if csrf_token:
            self._csrf_token = csrf_token
        return resp

    def _refresh_csrf_token(self) -> str:
        r = self._request(
            "GET",
            "/security/csrf",
            auth=(self.username or "", self.credential or ""),
        )
        token = self._csrf_token or r.headers.get("DSPACE-XSRF-TOKEN")
        if not token:
            raise DSpaceError("DSpace no devolvio un token CSRF")
        self._csrf_token = token
        return token

    def authenticate(self) -> str:
        self._refresh_csrf_token()
        r = self._request(
            "POST",
            "/authn/login",
            auth=(self.username or "", self.credential or ""),
            data={"user": self.username or "", "password": self.credential or ""},
        )
        if r.status_code >= 300:
            if r.status_code == 403 and "csrf" in (r.text or "").lower():
                self._refresh_csrf_token()
                r = self._request(
                    "POST",
                    "/authn/login",
                    auth=(self.username or "", self.credential or ""),
                    data={"user": self.username or "", "password": self.credential or ""},
                )
            if r.status_code >= 300:
                raise DSpaceError(f"Autenticacion fallida en DSpace (HTTP {r.status_code})")
        token = (r.headers.get("Authorization") or "").strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        if not token:
            token = r.text.strip()
        if not token:
            raise DSpaceError("DSpace no devolvio un token de autenticacion")
        return token

    def get_communities(self, token: str | None = None) -> list[dict]:
        r = self._request("GET", "/core/communities", params={"size": 500}, token=token)
        if r.status_code >= 400:
            raise DSpaceError(f"No se pudieron obtener comunidades (HTTP {r.status_code})")
        return r.json().get("_embedded", {}).get("communities", [])

    def get_collections(self, community_uuid: str | None = None, token: str | None = None) -> list[dict]:
        params = {"size": 500}
        if community_uuid:
            r = self._request("GET", f"/core/communities/{community_uuid}/collections", params=params, token=token)
        else:
            r = self._request("GET", "/core/collections", params=params, token=token)
        if r.status_code >= 400:
            raise DSpaceError(f"No se pudieron obtener colecciones (HTTP {r.status_code})")
        return r.json().get("_embedded", {}).get("collections", [])

    def get_collection(self, collection_uuid: str, token: str | None = None) -> dict:
        r = self._request("GET", f"/core/collections/{collection_uuid}", token=token)
        if r.status_code >= 400:
            raise DSpaceError(f"No se pudo obtener la coleccion (HTTP {r.status_code})")
        return r.json()

    def create_workspace_item(self, collection_uuid: str, token: str | None = None) -> dict:
        r = self._request(
            "POST",
            "/submission/workspaceitems",
            params={"owningCollection": collection_uuid},
            json={},
            token=token,
        )
        if r.status_code >= 300:
            raise DSpaceError(f"No se pudo crear el workspace item (HTTP {r.status_code})")
        return r.json()

    def add_metadata(self, workspace_id, metadata: dict, token: str | None = None) -> None:
        for key, values in metadata.items():
            op = {
                "op": "add",
                "path": f"/sections/{self.section}/{key}",
                "value": [
                    {
                        **(dict(value) if isinstance(value, dict) else {"value": value}),
                        "language": (value.get("language") if isinstance(value, dict) else None),
                        "authority": (value.get("authority") if isinstance(value, dict) else None),
                        "confidence": (value.get("confidence") if isinstance(value, dict) else -1),
                    }
                    for value in values
                ],
            }
            last = None
            for attempt in range(3):
                last = self._request("PATCH", f"/submission/workspaceitems/{workspace_id}", json=[op], token=token)
                if last.status_code < 300:
                    break
                if last.status_code not in {500, 502, 503} or attempt == 2:
                    raise DSpaceError(
                        f"No se pudo agregar metadata {key} (HTTP {last.status_code}): {last.text[:200]}"
                    )
                time.sleep(0.5)

    def upload_bitstream(self, workspace_id, filename: str, content: bytes, token: str | None = None) -> dict:
        r = self._request(
            "POST",
            f"/submission/workspaceitems/{workspace_id}",
            files={"file": (filename, content, "application/pdf")},
            token=token,
        )
        if r.status_code >= 300:
            raise DSpaceError(f"No se pudo cargar el bitstream (HTTP {r.status_code})")
        return r.json()

    def get_workspace_item(self, workspace_id, token: str | None = None) -> dict:
        r = self._request("GET", f"/submission/workspaceitems/{workspace_id}", token=token)
        if r.status_code >= 400:
            raise DSpaceError(f"No se pudo obtener el workspace item (HTTP {r.status_code})")
        return r.json()

    def submit_workspace_item(self, workspace_id, token: str | None = None) -> dict:
        self._request(
            "PATCH",
            f"/submission/workspaceitems/{workspace_id}",
            json=[{"op": "add", "path": "/sections/license/granted", "value": True}],
            token=token,
        )
        uri = f"{self.api_url}/submission/workspaceitems/{workspace_id}"
        r = self._request(
            "POST",
            "/workflow/workflowitems",
            headers={"Content-Type": "text/uri-list"},
            content=uri,
            token=token,
        )
        if r.status_code >= 300:
            raise DSpaceError(f"No se pudo completar la submission (HTTP {r.status_code})")
        data = r.json()
        item_ref = data.get("item") or data.get("_embedded", {}).get("item", {})
        item_uuid = (item_ref or {}).get("uuid")
        if not item_uuid and data.get("id"):
            workflow_item = self._request("GET", f"/workflow/workflowitems/{data['id']}/item", token=token)
            if workflow_item.status_code < 300:
                item_uuid = (workflow_item.json() or {}).get("uuid")
        if not item_uuid:
            raise DSpaceError("DSpace no devolvio el item de la submission")
        item = self.get_item(item_uuid, token)
        return {"item_uuid": item_uuid, "handle": item.get("handle")}

    def get_item(self, item_uuid: str, token: str | None = None) -> dict:
        r = self._request("GET", f"/core/items/{item_uuid}", token=token)
        if r.status_code >= 400:
            raise DSpaceError(f"No se pudo obtener el item (HTTP {r.status_code})")
        return r.json()


def build_connector(repo: Repository) -> Dspace9Connector:
    """Construye el conector adecuado para la configuración guardada."""
    cfg = repo.configuration_json or {}
    return Dspace9Connector(
        api_url=repo.api_url or "",
        username=repo.username,
        credential=_resolve_credential(cfg.get("credential")),
        section=cfg.get("submission_section", "traditionalpageone"),
    )
