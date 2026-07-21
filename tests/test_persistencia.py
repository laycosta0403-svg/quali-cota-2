from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

os.environ["QC_RUNTIME_DIR"] = "/tmp/quali_cota_test_runtime"

from src.motor import ResultadoMotor
from src.persistencia import carregar_metadata, carregar_resultado, salvar_resultado


def test_persistencia_ultima_rodada(tmp_path, monkeypatch):
    import src.persistencia as persistencia

    persistencia.RUNTIME_DIR = tmp_path / "runtime"
    persistencia.RODADAS_DIR = persistencia.RUNTIME_DIR / "rodadas"
    persistencia.ULTIMA_RODADA = persistencia.RUNTIME_DIR / "ultima_rodada.json"

    resultado = ResultadoMotor(
        id_carga="QDC_TESTE",
        pedido=pd.DataFrame([{"SKU": "1", "Quantidade Solicitada": 10}]),
        opcoes=pd.DataFrame([{"SKU": "1", "Fornecedor 1": "Solfarma"}]),
        pendencias=pd.DataFrame(),
        historico=pd.DataFrame([{"SKU identificado": "1"}]),
        ofertas_tratadas=pd.DataFrame(),
        resumo={
            "processado_em": pd.Timestamp("2026-07-20 22:00").to_pydatetime(),
            "valor_total": 100.0,
            "skus_pedido": 1,
            "por_fornecedor": pd.DataFrame([{"Fornecedor recomendado": "Solfarma", "Valor total": 100.0}]),
            "motivos_pendencia": pd.DataFrame(columns=["Pendência", "Quantidade"]),
        },
        diagnostico={"aba_necessidade": "Volume de Compras - Dia"},
    )

    salvar_resultado(resultado)
    metadata = carregar_metadata()
    assert metadata is not None
    assert metadata["id_carga"] == "QDC_TESTE"

    parcial = carregar_resultado(incluir={"pedido", "opcoes"})
    assert parcial is not None
    assert len(parcial.pedido) == 1
    assert len(parcial.opcoes) == 1
    assert parcial.historico.empty
