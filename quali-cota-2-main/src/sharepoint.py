from __future__ import annotations

import mimetypes
import re
import time
import unicodedata
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


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


@dataclass(frozen=True)
class SharePointConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    site_hostname: str = ""
    site_path: str = ""
    site_id: str = ""
    drive_id: str = ""
    library_name: str = "Documents"
    root_folder: str = ""
    qualicota_root: str = "QualiCota"
    supply_root: str = "Supply"
    structural_root: str = "Bases Estruturais"
    recursive: bool = True
    max_depth: int = 10

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "SharePointConfig":
        raw: dict[str, Any] = {}
        for key in cls.__dataclass_fields__:
            raw[key] = values.get(key, cls.__dataclass_fields__[key].default)
        raw["recursive"] = str(raw.get("recursive", "true")).strip().casefold() not in {"0", "false", "nao", "não"}
        try:
            raw["max_depth"] = max(1, min(int(raw.get("max_depth", 10)), 30))
        except (TypeError, ValueError):
            raw["max_depth"] = 10
        for key in ("tenant_id", "client_id", "client_secret", "site_hostname", "site_path", "site_id", "drive_id", "library_name", "root_folder", "qualicota_root", "supply_root", "structural_root"):
            raw[key] = str(raw.get(key, "") or "").strip()
        config = cls(**raw)
        obrigatorios = {
            "tenant_id": config.tenant_id,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        }
        faltantes = [nome for nome, valor in obrigatorios.items() if not valor]
        if faltantes:
            raise SharePointError("Faltam configurações do SharePoint nos Secrets: " + ", ".join(faltantes))
        if not config.site_id and not (config.site_hostname and config.site_path):
            raise SharePointError("Informe site_id ou a combinação site_hostname + site_path nos Secrets.")
        return config


@dataclass(frozen=True)
class SharePointFile:
    item_id: str
    name: str
    size: int
    modified_at: str
    web_url: str = ""
    path: str = ""

    @property
    def extension(self) -> str:
        return Path(self.name).suffix.lower()

    @property
    def label(self) -> str:
        tamanho_mb = self.size / (1024 * 1024)
        data = self.modified_at.replace("T", " ").replace("Z", " UTC")[:19]
        caminho = f" · {self.path}" if self.path else ""
        return f"{self.name} · {tamanho_mb:.1f} MB · {data}{caminho}"


@dataclass(frozen=True)
class AutoDiscovery:
    cotacoes: tuple[SharePointFile, ...]
    necessidade: SharePointFile | None
    cadastro: SharePointFile | None
    regras: SharePointFile | None
    homologacao: SharePointFile | None
    historico: SharePointFile | None


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
            try:
                detalhe = response.json().get("error", {}).get("message", "")
            except ValueError:
                detalhe = response.text[:500]
            raise SharePointError(f"Microsoft Graph respondeu {response.status_code}. {detalhe or 'Sem detalhes.'}")
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
            try:
                detalhe = response.json().get("error_description", "")
            except ValueError:
                detalhe = response.text[:500]
            raise SharePointError("Não foi possível autenticar a aplicação no Microsoft Graph. " + detalhe)
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
        alvo = _norm(self.config.library_name)
        aliases = {alvo, "documents", "documentos", "documentos compartilhados", "shared documents"}
        for drive in drives:
            if _norm(str(drive.get("name", ""))) in aliases:
                self._drive_id = str(drive["id"])
                return self._drive_id
        nomes = ", ".join(str(item.get("name", "")) for item in drives) or "nenhuma"
        raise SharePointError(f'A biblioteca "{self.config.library_name}" não foi encontrada. Bibliotecas: {nomes}.')

    def _children_url(self, folder_path: str) -> str:
        folder = folder_path.strip().strip("/")
        drive = quote(self.drive_id(), safe="!")
        if folder:
            caminho = quote(folder, safe="/")
            base = f"{GRAPH_ROOT}/drives/{drive}/root:/{caminho}:/children"
        else:
            base = f"{GRAPH_ROOT}/drives/{drive}/root/children"
        return base + "?$select=id,name,size,lastModifiedDateTime,webUrl,file,folder&$top=200"

    def list_files(self, folder_path: str, extensions: Iterable[str] = SUPPORTED_EXTENSIONS) -> list[SharePointFile]:
        return self.list_files_recursive(folder_path, extensions=extensions, max_depth=0)

    def list_files_recursive(
        self,
        folder_path: str,
        extensions: Iterable[str] = SUPPORTED_EXTENSIONS,
        max_depth: int | None = None,
    ) -> list[SharePointFile]:
        ext_permitidas = {str(ext).lower() for ext in extensions}
        limite = self.config.max_depth if max_depth is None else max_depth
        raiz = folder_path.strip().strip("/")
        fila: list[tuple[str, int]] = [(raiz, 0)]
        arquivos: list[SharePointFile] = []
        visitadas: set[str] = set()
        while fila:
            pasta, profundidade = fila.pop(0)
            if pasta.casefold() in visitadas:
                continue
            visitadas.add(pasta.casefold())
            url = self._children_url(pasta)
            while url:
                payload = self._request("GET", url).json()
                for item in payload.get("value", []):
                    nome = str(item.get("name", ""))
                    caminho_item = "/".join(part for part in (pasta, nome) if part)
                    if "folder" in item:
                        if self.config.recursive and profundidade < limite:
                            fila.append((caminho_item, profundidade + 1))
                        continue
                    if "file" not in item or Path(nome).suffix.lower() not in ext_permitidas:
                        continue
                    arquivos.append(SharePointFile(
                        item_id=str(item["id"]), name=nome, size=int(item.get("size", 0) or 0),
                        modified_at=str(item.get("lastModifiedDateTime", "")), web_url=str(item.get("webUrl", "")),
                        path=caminho_item,
                    ))
                url = str(payload.get("@odata.nextLink", ""))
        return sorted(arquivos, key=lambda item: item.modified_at, reverse=True)

    def list_configured_roots(self) -> list[SharePointFile]:
        roots = []
        prefix = self.config.root_folder.strip().strip("/")
        for root in (self.config.qualicota_root, self.config.supply_root, self.config.structural_root):
            root = str(root or "").strip().strip("/")
            if not root:
                continue
            path = "/".join(part for part in (prefix, root) if part)
            roots.extend(self.list_files_recursive(path))
        unique = {item.item_id: item for item in roots}
        return sorted(unique.values(), key=lambda item: item.modified_at, reverse=True)

    @staticmethod
    def _path_contains(item: SharePointFile, *parts: str) -> bool:
        path = _norm(item.path)
        return all(_norm(part) in path for part in parts if part)

    @staticmethod
    def candidates_by_role(files: Iterable[SharePointFile]) -> dict[str, list[SharePointFile]]:
        """Retorna listas enxutas para o mapeador assistido.

        A seleção usa primeiro o caminho operacional informado pela usuária e
        só depois o nome/data. Isso evita oferecer 10 mil arquivos em cada
        seletor e mantém a possibilidade de correção manual.
        """
        items = list(files)
        by_modified = lambda seq: sorted(seq, key=lambda x: x.modified_at, reverse=True)

        cotacoes = [
            x for x in items
            if SharePointConnector._path_contains(x, 'QualiCota', '01 Entrada de Arquivos')
        ]
        # Planejamento muda diariamente. Priorizamos arquivos na árvore Supply
        # cujo nome contenha Planejamento; o mais recente será sugerido.
        planejamentos = [
            x for x in items
            if SharePointConnector._path_contains(x, 'Supply') and 'planejamento' in _norm(x.name)
        ]
        regras = [
            x for x in items
            if SharePointConnector._path_contains(x, 'QualiCota', '04 Governanca')
            and ('regras fornecedor' in _norm(x.name) or 'regras fornecedores' in _norm(x.name))
        ]
        homologacoes = [
            x for x in items
            if SharePointConnector._path_contains(x, 'Bases Estruturais')
            and 'mapa de envio de pedidos' in _norm(x.name)
        ]
        historicos = [
            x for x in items
            if SharePointConnector._path_contains(x, 'Supply', 'COMPRAS 1', 'NOVO')
            and 'mapa diario 2 0' in _norm(x.name)
        ]

        # Fallbacks aparecem depois dos caminhos oficiais, para permitir
        # correção caso um arquivo tenha sido movido temporariamente.
        if not cotacoes:
            cotacoes = [x for x in items if 'cotacao' in _norm(x.name)]
        if not planejamentos:
            planejamentos = [x for x in items if 'planejamento' in _norm(x.name)]
        if not regras:
            regras = [x for x in items if 'regras fornecedor' in _norm(x.name)]
        if not homologacoes:
            homologacoes = [x for x in items if 'mapa de envio de pedidos' in _norm(x.name)]
        if not historicos:
            historicos = [x for x in items if 'mapa diario 2 0' in _norm(x.name)]

        return {
            'cotacoes': by_modified(cotacoes),
            'planejamentos': by_modified(planejamentos),
            'regras': by_modified(regras),
            'homologacoes': by_modified(homologacoes),
            'historicos': by_modified(historicos),
        }

    @staticmethod
    def discover(files: Iterable[SharePointFile]) -> AutoDiscovery:
        candidatos = SharePointConnector.candidates_by_role(files)
        planejamento = candidatos['planejamentos'][0] if candidatos['planejamentos'] else None
        return AutoDiscovery(
            tuple(candidatos['cotacoes'][:5]),
            planejamento,
            planejamento,  # cadastro EAN/SKU vem da aba Ean do mesmo Planejamento
            candidatos['regras'][0] if candidatos['regras'] else None,
            candidatos['homologacoes'][0] if candidatos['homologacoes'] else None,
            candidatos['historicos'][0] if candidatos['historicos'] else None,
        )

    def download_file(self, item: SharePointFile, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        safe_name = item.name.replace("/", "_").replace("\\", "_")
        destino = destination_dir / safe_name
        url = f"{GRAPH_ROOT}/drives/{quote(self.drive_id(), safe='!')}/items/{quote(item.item_id, safe='!')}/content"
        response = self._request("GET", url, stream=True, allow_redirects=True)
        with destino.open("wb") as arquivo:
            for bloco in response.iter_content(chunk_size=1024 * 1024):
                if bloco:
                    arquivo.write(bloco)
        if not destino.exists() or destino.stat().st_size == 0:
            raise SharePointError(f'O arquivo "{item.name}" foi baixado vazio.')
        return destino


    def ensure_folder(self, folder_path: str) -> str:
        """Cria a árvore de pastas se necessário e retorna o item_id final."""
        parts = [part for part in folder_path.strip().strip("/").split("/") if part]
        parent_id = "root"
        current = ""
        for part in parts:
            current = "/".join([current, part]).strip("/")
            try:
                url = f"{GRAPH_ROOT}/drives/{quote(self.drive_id(), safe='!')}/root:/{quote(current, safe='/')}"
                parent_id = str(self._request("GET", url).json()["id"])
                continue
            except SharePointError:
                pass
            if parent_id == "root":
                create_url = f"{GRAPH_ROOT}/drives/{quote(self.drive_id(), safe='!')}/root/children"
            else:
                create_url = f"{GRAPH_ROOT}/drives/{quote(self.drive_id(), safe='!')}/items/{quote(parent_id, safe='!')}/children"
            payload = {"name": part, "folder": {}, "@microsoft.graph.conflictBehavior": "replace"}
            parent_id = str(self._request("POST", create_url, json=payload).json()["id"])
        return parent_id

    def upload_file(self, local_path: Path, folder_path: str, remote_name: str | None = None) -> dict[str, str]:
        """Envia arquivo ao SharePoint; usa upload simples até 250 MB."""
        self.ensure_folder(folder_path)
        name = remote_name or local_path.name
        remote = "/".join(part for part in [folder_path.strip().strip("/"), name] if part)
        url = f"{GRAPH_ROOT}/drives/{quote(self.drive_id(), safe='!')}/root:/{quote(remote, safe='/')}:/content"
        headers = {"Content-Type": guess_mime_type(name)}
        with local_path.open("rb") as fh:
            payload = self._request("PUT", url, headers=headers, data=fh).json()
        return {"id": str(payload.get("id", "")), "name": str(payload.get("name", name)), "web_url": str(payload.get("webUrl", ""))}

    def diagnostic(self) -> dict[str, str]:
        return {"site_id": self.site_id(), "drive_id": self.drive_id(), "library_name": self.config.library_name}


def guess_mime_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"
