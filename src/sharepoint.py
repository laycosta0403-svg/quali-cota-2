from __future__ import annotations

import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import quote

import requests


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
SUPPORTED_EXTENSIONS = {".xlsx", ".xlsb", ".csv"}


class SharePointError(RuntimeError):
    """Erro amigável de autenticação, configuração ou leitura no SharePoint."""


@dataclass(frozen=True)
class SharePointConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    site_hostname: str = ""
    site_path: str = ""
    site_id: str = ""
    drive_id: str = ""
    library_name: str = "Documentos"
    cotacoes_folder: str = ""
    planejamento_folder: str = ""

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "SharePointConfig":
        data = {key: str(values.get(key, "") or "").strip() for key in cls.__dataclass_fields__}
        config = cls(**data)
        obrigatorios = {
            "tenant_id": config.tenant_id,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "cotacoes_folder": config.cotacoes_folder,
            "planejamento_folder": config.planejamento_folder,
        }
        faltantes = [nome for nome, valor in obrigatorios.items() if not valor]
        if faltantes:
            raise SharePointError(
                "Faltam configurações do SharePoint nos Secrets: " + ", ".join(faltantes)
            )
        if not config.site_id and not (config.site_hostname and config.site_path):
            raise SharePointError(
                "Informe site_id ou a combinação site_hostname + site_path nos Secrets."
            )
        return config


@dataclass(frozen=True)
class SharePointFile:
    item_id: str
    name: str
    size: int
    modified_at: str
    web_url: str = ""

    @property
    def extension(self) -> str:
        return Path(self.name).suffix.lower()

    @property
    def label(self) -> str:
        tamanho_mb = self.size / (1024 * 1024)
        data = self.modified_at.replace("T", " ").replace("Z", " UTC")[:19]
        return f"{self.name} · {tamanho_mb:.1f} MB · {data}"


class SharePointConnector:
    def __init__(self, config: SharePointConfig, timeout: int = 60):
        self.config = config
        self.timeout = timeout
        self._token = ""
        self._token_expires_at = 0.0
        self._site_id = config.site_id
        self._drive_id = config.drive_id

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self.access_token()}"
        response = requests.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
        if response.status_code >= 400:
            detalhe = ""
            try:
                payload = response.json()
                detalhe = payload.get("error", {}).get("message", "")
            except ValueError:
                detalhe = response.text[:500]
            raise SharePointError(
                f"Microsoft Graph respondeu {response.status_code}. {detalhe or 'Sem detalhes.'}"
            )
        return response

    def access_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 120:
            return self._token
        response = requests.post(
            TOKEN_URL.format(tenant_id=quote(self.config.tenant_id, safe="")),
            data={
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            detalhe = ""
            try:
                detalhe = response.json().get("error_description", "")
            except ValueError:
                detalhe = response.text[:500]
            raise SharePointError(
                "Não foi possível autenticar a aplicação no Microsoft Graph. " + detalhe
            )
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.time() + int(payload.get("expires_in", 3599))
        return self._token

    def site_id(self) -> str:
        if self._site_id:
            return self._site_id
        caminho = self.config.site_path.strip()
        if not caminho.startswith("/"):
            caminho = "/" + caminho
        url = f"{GRAPH_ROOT}/sites/{self.config.site_hostname}:{quote(caminho, safe='/')}"
        self._site_id = str(self._request("GET", url).json()["id"])
        return self._site_id

    def drive_id(self) -> str:
        if self._drive_id:
            return self._drive_id
        url = f"{GRAPH_ROOT}/sites/{quote(self.site_id(), safe=',')}/drives"
        drives = self._request("GET", url).json().get("value", [])
        alvo = self.config.library_name.casefold()
        for drive in drives:
            if str(drive.get("name", "")).casefold() == alvo:
                self._drive_id = str(drive["id"])
                return self._drive_id
        nomes = ", ".join(str(item.get("name", "")) for item in drives) or "nenhuma"
        raise SharePointError(
            f'A biblioteca "{self.config.library_name}" não foi encontrada. Bibliotecas: {nomes}.'
        )

    def list_files(self, folder_path: str, extensions: Iterable[str] = SUPPORTED_EXTENSIONS) -> list[SharePointFile]:
        folder = folder_path.strip().strip("/")
        if not folder:
            raise SharePointError("O caminho da pasta no SharePoint está vazio.")
        ext_permitidas = {str(ext).lower() for ext in extensions}
        caminho = quote(folder, safe="/")
        url = (
            f"{GRAPH_ROOT}/drives/{quote(self.drive_id(), safe='!')}/root:/{caminho}:/children"
            "?$select=id,name,size,lastModifiedDateTime,webUrl,file,folder&$top=200"
        )
        arquivos: list[SharePointFile] = []
        while url:
            payload = self._request("GET", url).json()
            for item in payload.get("value", []):
                if "file" not in item:
                    continue
                nome = str(item.get("name", ""))
                if Path(nome).suffix.lower() not in ext_permitidas:
                    continue
                arquivos.append(
                    SharePointFile(
                        item_id=str(item["id"]),
                        name=nome,
                        size=int(item.get("size", 0) or 0),
                        modified_at=str(item.get("lastModifiedDateTime", "")),
                        web_url=str(item.get("webUrl", "")),
                    )
                )
            url = str(payload.get("@odata.nextLink", ""))
        return sorted(arquivos, key=lambda item: item.modified_at, reverse=True)

    def download_file(self, item: SharePointFile, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        destino = destination_dir / item.name
        url = f"{GRAPH_ROOT}/drives/{quote(self.drive_id(), safe='!')}/items/{quote(item.item_id, safe='!')}/content"
        response = self._request("GET", url, stream=True, allow_redirects=True)
        with destino.open("wb") as arquivo:
            for bloco in response.iter_content(chunk_size=1024 * 1024):
                if bloco:
                    arquivo.write(bloco)
        if not destino.exists() or destino.stat().st_size == 0:
            raise SharePointError(f'O arquivo "{item.name}" foi baixado vazio.')
        return destino

    def diagnostic(self) -> dict[str, str]:
        return {
            "site_id": self.site_id(),
            "drive_id": self.drive_id(),
            "library_name": self.config.library_name,
        }


def guess_mime_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"
