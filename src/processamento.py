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
    numero,
    texto_codigo,
)
from src.motor import ResultadoMotor, executar_motor
from src.tempo import agora_brasil


def gerar_id_carga() -> str:
    return agora_brasil().strftime("QDC_%Y%m%d_%H%M%S_%f")[:-3]


def _nome_arquivo(arquivo) -> str:
    return str(getattr(arquivo, "name", "arquivo"))


def processar_arquivos(
    cotacoes: Iterable,
    necessidade,
    cadastro,
    regras,
    homologacao=None,
    historico=None,
    fornecedores_desativados: Iterable[str] = (),
) -> ResultadoMotor:
    id_carga = gerar_id_carga()

    cotacoes_df: list[pd.DataFrame] = []
    abas_cotacao: list[str] = []
    for arquivo in cotacoes:
        df = ler_tabela(
            arquivo,
            ALIASES_COTACAO,
            abas_preferidas=["cotacao", "fornecedor", "planilha1"],
            exigir_colunas=["fornecedor", "ean", "preco_final", "estoque_fornecedor"],
        )
        abas_cotacao.append(str(df.attrs.get("aba_lida", "")))
        df["arquivo_origem"] = _nome_arquivo(arquivo)
        # O arquivo real de cotações não possui ID da carga. A rodada passa a ter
        # um identificador próprio, único e obrigatório, propagado a todos os outputs.
        df["id_carga"] = id_carga
        cotacoes_df.append(df)

    if not cotacoes_df:
        raise ValueError("Nenhuma cotação válida foi enviada.")
    cotacao_df = pd.concat(cotacoes_df, ignore_index=True, sort=False)

    necessidade_df = ler_tabela(
        necessidade,
        ALIASES_NECESSIDADE,
        aba_obrigatoria="volume de compras",
        exigir_colunas=["sku", "ean", "quantidade_solicitada"],
    )
    necessidade_df["sku"] = necessidade_df["sku"].map(texto_codigo)
    necessidade_df["ean"] = necessidade_df["ean"].map(texto_codigo)
    necessidade_df["quantidade_solicitada"] = necessidade_df["quantidade_solicitada"].map(numero)
    necessidade_df = necessidade_df[
        necessidade_df["sku"].ne("") | necessidade_df["ean"].ne("")
    ].reset_index(drop=True)

    total_linhas_necessidade = len(necessidade_df)
    quantidade_positiva = necessidade_df["quantidade_solicitada"] > 0
    skus_com_pedido = int(quantidade_positiva.sum())
    unidades_solicitadas = int(necessidade_df.loc[quantidade_positiva, "quantidade_solicitada"].sum())
    if total_linhas_necessidade == 0:
        raise ValueError('A aba "Volume de Compras" foi encontrada, mas não possui itens válidos.')
    if skus_com_pedido == 0:
        raise ValueError(
            'A aba "Volume de Compras" foi lida, porém a coluna "Pedido Efetivo" '
            "não trouxe nenhuma quantidade maior que zero. O processamento foi bloqueado."
        )

    avisos_bases: list[str] = []

    # Por desenho, o cadastro vem da aba Ean do mesmo Planejamento. Caso a aba
    # não esteja utilizável, criamos um cadastro mínimo a partir da necessidade,
    # permitindo a rodada sem esconder que faltou enriquecimento.
    try:
        cadastro_df = ler_tabela(
            cadastro if cadastro is not None else necessidade,
            ALIASES_CADASTRO,
            aba_obrigatoria="ean",
            exigir_colunas=["sku"],
        )
    except Exception as exc:
        avisos_bases.append(f"Cadastro EAN/SKU não validado: {exc}")
        cadastro_df = pd.DataFrame({
            "ean_compra": necessidade_df["ean"],
            "ean_venda": necessidade_df["ean"],
            "sku": necessidade_df["sku"],
            "descricao_oficial": necessidade_df.get("descricao", ""),
            "fabricante": necessidade_df.get("fabricante", ""),
            "categoria": necessidade_df.get("categoria", ""),
            "caixaria_padrao": necessidade_df.get("caixaria", 1),
            "multiplo_padrao": necessidade_df.get("caixaria", 1),
            "status_ean": "Ativo",
        })

    try:
        regras_df = ler_tabela(
            regras,
            ALIASES_REGRAS,
            abas_preferidas=["regras", "fornecedor"],
            exigir_colunas=["fornecedor"],
        ) if regras is not None else pd.DataFrame()
    except Exception as exc:
        avisos_bases.append(f"Regras de fornecedor não validadas: {exc}")
        regras_df = pd.DataFrame()

    # Sem regras selecionadas, aplicamos uma base permissiva mínima para não
    # bloquear a rodada. O Dashboard registra que esse enriquecimento faltou.
    if regras_df.empty:
        fornecedores = sorted({str(v).strip() for v in cotacao_df.get("fornecedor", []) if str(v).strip()})
        regras_df = pd.DataFrame({
            "fornecedor": fornecedores,
            "ativo": "Sim",
            "bloqueado": "Não",
            "participa_cotacao": "Sim",
            "participa_busca": "Sim",
        })
        avisos_bases.append("Rodada processada com regras permissivas geradas a partir da cotação.")

    try:
        homologacao_df = (
            ler_tabela(homologacao, ALIASES_HOMOLOGACAO, abas_preferidas=["homologacao", "ol"])
            if homologacao is not None else pd.DataFrame()
        )
    except Exception as exc:
        avisos_bases.append(f"Homologação OL não validada: {exc}")
        homologacao_df = pd.DataFrame()

    try:
        historico_df = (
            ler_tabela(historico, ALIASES_HISTORICO, abas_preferidas=["historico"])
            if historico is not None else pd.DataFrame()
        )
    except Exception as exc:
        avisos_bases.append(f"Histórico não validado: {exc}")
        historico_df = pd.DataFrame()

    diagnostico = {
        "id_carga": id_carga,
        "arquivo_necessidade": _nome_arquivo(necessidade),
        "aba_necessidade": necessidade_df.attrs.get("aba_lida", ""),
        "linha_cabecalho_necessidade": necessidade_df.attrs.get("linha_cabecalho", ""),
        "linhas_necessidade": total_linhas_necessidade,
        "skus_com_pedido": skus_com_pedido,
        "unidades_solicitadas": unidades_solicitadas,
        "linhas_cotacao": len(cotacao_df),
        "abas_cotacao": abas_cotacao,
        "avisos_bases": avisos_bases,
        "arquivo_cadastro": _nome_arquivo(cadastro if cadastro is not None else necessidade),
        "arquivo_regras": _nome_arquivo(regras) if regras is not None else "Não selecionado",
        "arquivo_homologacao": _nome_arquivo(homologacao) if homologacao is not None else "Não selecionado",
        "arquivo_historico": _nome_arquivo(historico) if historico is not None else "Não selecionado",
    }

    return executar_motor(
        cotacao=cotacao_df,
        necessidade=necessidade_df,
        cadastro=cadastro_df,
        regras_fornecedor=regras_df,
        homologacao_ol=homologacao_df,
        historico=historico_df,
        fornecedores_desativados=fornecedores_desativados,
        id_carga=id_carga,
        diagnostico=diagnostico,
    )
