from __future__ import annotations

from typing import Iterable

import pandas as pd

from src.leitura import (
    ALIASES_CADASTRO,
    ALIASES_COTACAO,
    ALIASES_HISTORICO,
    ALIASES_HOMOLOGACAO,
    ALIASES_NECESSIDADE,
    ALIASES_REGRAS,
    ler_tabela,
)
from src.motor import ResultadoMotor, executar_motor


def processar_arquivos(
    cotacoes: Iterable,
    necessidade,
    cadastro,
    regras,
    homologacao=None,
    historico=None,
    fornecedores_desativados: Iterable[str] = (),
) -> ResultadoMotor:
    cotacoes_df = [
        ler_tabela(arquivo, ALIASES_COTACAO, abas_preferidas=["cotacao", "fornecedor"])
        for arquivo in cotacoes
    ]
    cotacao_df = pd.concat(cotacoes_df, ignore_index=True, sort=False)
    necessidade_df = ler_tabela(necessidade, ALIASES_NECESSIDADE, abas_preferidas=["volume de compras", "necessidade"])
    cadastro_df = ler_tabela(cadastro, ALIASES_CADASTRO, abas_preferidas=["cadastro", "ean"])
    regras_df = ler_tabela(regras, ALIASES_REGRAS, abas_preferidas=["regras", "fornecedor"])
    homologacao_df = (
        ler_tabela(homologacao, ALIASES_HOMOLOGACAO, abas_preferidas=["homologacao", "ol"])
        if homologacao is not None
        else pd.DataFrame()
    )
    historico_df = (
        ler_tabela(historico, ALIASES_HISTORICO, abas_preferidas=["historico"])
        if historico is not None
        else pd.DataFrame()
    )
    return executar_motor(
        cotacao=cotacao_df,
        necessidade=necessidade_df,
        cadastro=cadastro_df,
        regras_fornecedor=regras_df,
        homologacao_ol=homologacao_df,
        historico=historico_df,
        fornecedores_desativados=fornecedores_desativados,
    )
