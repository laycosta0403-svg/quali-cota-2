from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.motor import ResultadoMotor
from src.tempo import agora_brasil


RUNTIME_DIR = Path(os.getenv("QC_RUNTIME_DIR", "/tmp/quali_cota"))
RODADAS_DIR = RUNTIME_DIR / "rodadas"
ULTIMA_RODADA = RUNTIME_DIR / "ultima_rodada.json"

_TABELAS = {
    "pedido": "pedido.csv.gz",
    "opcoes": "opcoes.csv.gz",
    "pendencias": "pendencias.csv.gz",
    "historico": "historico.csv.gz",
    "por_fornecedor": "por_fornecedor.csv.gz",
    "motivos_pendencia": "motivos_pendencia.csv.gz",
}


def _jsonavel(valor: Any) -> Any:
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, (pd.Timestamp,)):
        return valor.isoformat()
    if hasattr(valor, "item"):
        try:
            return valor.item()
        except Exception:
            pass
    if isinstance(valor, dict):
        return {str(k): _jsonavel(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_jsonavel(v) for v in valor]
    return valor


def _pasta_rodada(id_carga: str) -> Path:
    return RODADAS_DIR / id_carga


def salvar_resultado(resultado: ResultadoMotor) -> Path:
    pasta = _pasta_rodada(resultado.id_carga)
    pasta.mkdir(parents=True, exist_ok=True)

    tabelas = {
        "pedido": resultado.pedido,
        "opcoes": resultado.opcoes,
        "pendencias": resultado.pendencias,
        "historico": resultado.historico,
        "por_fornecedor": resultado.resumo.get("por_fornecedor", pd.DataFrame()),
        "motivos_pendencia": resultado.resumo.get("motivos_pendencia", pd.DataFrame()),
    }
    for nome, df in tabelas.items():
        destino = pasta / _TABELAS[nome]
        df.to_csv(destino, index=False, compression="gzip")

    resumo_escalar = {
        chave: valor
        for chave, valor in resultado.resumo.items()
        if not isinstance(valor, pd.DataFrame)
    }
    metadata = {
        "id_carga": resultado.id_carga,
        "resumo": _jsonavel(resumo_escalar),
        "diagnostico": _jsonavel(resultado.diagnostico),
        "salvo_em": agora_brasil().isoformat(),
    }
    (pasta / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    ULTIMA_RODADA.write_text(
        json.dumps({"id_carga": resultado.id_carga}, ensure_ascii=False), encoding="utf-8"
    )
    return pasta


def obter_ultimo_id() -> str | None:
    try:
        payload = json.loads(ULTIMA_RODADA.read_text(encoding="utf-8"))
        id_carga = str(payload.get("id_carga", "")).strip()
        return id_carga or None
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def carregar_metadata(id_carga: str | None = None) -> dict[str, Any] | None:
    id_carga = id_carga or obter_ultimo_id()
    if not id_carga:
        return None
    caminho = _pasta_rodada(id_carga) / "metadata.json"
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def carregar_tabela(
    nome: str,
    id_carga: str | None = None,
    *,
    nrows: int | None = None,
) -> pd.DataFrame:
    if nome not in _TABELAS:
        raise ValueError(f"Tabela persistida desconhecida: {nome}")
    id_carga = id_carga or obter_ultimo_id()
    if not id_carga:
        return pd.DataFrame()
    caminho = _pasta_rodada(id_carga) / _TABELAS[nome]
    if not caminho.exists():
        return pd.DataFrame()
    return pd.read_csv(caminho, compression="gzip", nrows=nrows, low_memory=False)


def carregar_resultado(
    id_carga: str | None = None,
    incluir: set[str] | None = None,
) -> ResultadoMotor | None:
    metadata = carregar_metadata(id_carga)
    if metadata is None:
        return None
    id_carga = str(metadata["id_carga"])
    resumo = dict(metadata.get("resumo", {}))
    processado_em = resumo.get("processado_em")
    if processado_em:
        resumo["processado_em"] = pd.Timestamp(processado_em).to_pydatetime()
    resumo["por_fornecedor"] = carregar_tabela("por_fornecedor", id_carga)
    resumo["motivos_pendencia"] = carregar_tabela("motivos_pendencia", id_carga)
    if incluir is None:
        incluir = {"pedido", "opcoes", "pendencias", "historico"}
    return ResultadoMotor(
        id_carga=id_carga,
        pedido=carregar_tabela("pedido", id_carga) if "pedido" in incluir else pd.DataFrame(),
        opcoes=carregar_tabela("opcoes", id_carga) if "opcoes" in incluir else pd.DataFrame(),
        pendencias=carregar_tabela("pendencias", id_carga) if "pendencias" in incluir else pd.DataFrame(),
        historico=carregar_tabela("historico", id_carga) if "historico" in incluir else pd.DataFrame(),
        ofertas_tratadas=pd.DataFrame(),
        resumo=resumo,
        diagnostico=dict(metadata.get("diagnostico", {})),
    )


def pasta_downloads(id_carga: str | None = None) -> Path:
    id_carga = id_carga or obter_ultimo_id()
    if not id_carga:
        raise ValueError("Nenhuma rodada persistida foi encontrada.")
    pasta = _pasta_rodada(id_carga) / "downloads"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def salvar_tabela(nome: str, df: pd.DataFrame, id_carga: str | None = None) -> Path:
    """Atualiza uma tabela persistida da rodada sem reprocessar todas as bases."""
    if nome not in _TABELAS:
        raise ValueError(f"Tabela persistida desconhecida: {nome}")
    id_carga = id_carga or obter_ultimo_id()
    if not id_carga:
        raise ValueError("Nenhuma rodada persistida foi encontrada.")
    pasta = _pasta_rodada(id_carga)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / _TABELAS[nome]
    df.to_csv(destino, index=False, compression="gzip")
    return destino


def salvar_auditoria_pendencias(id_carga: str, auditoria: pd.DataFrame) -> Path:
    pasta = _pasta_rodada(id_carga)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "auditoria_pendencias.csv.gz"
    if destino.exists():
        anterior = pd.read_csv(destino, compression="gzip", low_memory=False)
        auditoria = pd.concat([anterior, auditoria], ignore_index=True, sort=False)
    auditoria.to_csv(destino, index=False, compression="gzip")
    return destino
