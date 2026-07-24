from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from src.leitura import (
    booleano_sim,
    dividir_eans,
    normalizar_texto,
    numero,
    texto_codigo,
)
from src.tempo import agora_brasil, agora_brasil_sem_fuso


PATCH_MOTOR = "MVP-HIST-CLASS-05"

@dataclass
class ResultadoMotor:
    id_carga: str
    pedido: pd.DataFrame
    opcoes: pd.DataFrame
    pendencias: pd.DataFrame
    historico: pd.DataFrame
    ofertas_tratadas: pd.DataFrame
    resumo: dict[str, object]
    diagnostico: dict[str, object]


# Nomes curtos usados na cotação versus razões sociais da base de regras.
# O mapeamento evita rejeitar uma oferta apenas por diferença de nomenclatura.
ALIASES_FORNECEDOR = {
    "zerbini": "zerbini do brasil ltda",
    "jm furtina": "j m furtina distribuidora de",
    "samapi": "samapi distribuidora de produt",
    "andorinha": "andorinha comercio e distribui",
    "santa cruz": "distrib medic santa cruz ltda",
    "milfarma": "milfarma comercial ltda",
    "medicamental": "medicamental distribuidora ltd",
    "panpharma": "panpharma distribuidora de med",
    "cimed": "cimed remedios s a",
    "maxifarma": "maxifarma distribuidora de med",
    "j k medicamentos": "j k medicamentos ltda",
    "profarma": "profarma distribuidora de prod",
    "solfarma": "solfarma com prod farm sa",
    "servimed": "servimed comercial ltda",
    "marka": "marka distribuidora de medicam",
    "roge": "roge interg comercio e distrib",
    "navarro": "navarro distribuidora de medic",
    "master formula": "master",
    "julia": "julia cosmeticos ltda",
    "mantiqueira": "mantiqueira distribuidora de p",
    "gpz": "gpz comercial ltda",
    "polydrogras": "polydrogas",
    "polydrogras": "polydrogas",
    "dismap": "ambrosio correa comercio dismap",
}


def _primeiro_preenchido(*valores: object) -> object:
    for valor in valores:
        if normalizar_texto(valor):
            return valor
    return ""


def _tipo_operacao_regra(registro: dict) -> str:
    valor = _primeiro_preenchido(
        registro.get("tipo_operacao"),
        registro.get("como_comprar"),
        registro.get("observacao_regra"),
    )
    norm = normalizar_texto(valor)
    if norm in {"ol", "online"} or norm.startswith("ol "):
        return "OL"
    if "direto" in norm or norm in {"dt", "direta"}:
        return "Direto"
    if "distr" in norm:
        return "Distribuidor"
    return ""


def _normalizar_tipo_operacao(valor: object) -> str:
    """Padroniza a classificação por item usada no Pedido Unificado."""
    norm = normalizar_texto(valor)
    if norm in {"ol", "online"} or norm.startswith("ol "):
        return "OL"
    if "direto" in norm or norm in {"dt", "direta"}:
        return "Direto"
    if norm in {"dist", "distribuidor", "distribuicao"} or "distr" in norm:
        return "Distribuidor"
    return ""


def _mapas_classificacao_historica(historico: pd.DataFrame) -> tuple[dict[str, str], dict[str, str]]:
    """Retorna a classificação do Mapa Diário por SKU e por EAN.

    O Mapa Diário é uma referência de produto, portanto tem prioridade sobre
    regras genéricas do fornecedor. Históricos consolidados não entram aqui.
    """
    if historico.empty or historico.attrs.get("formato_historico") != "mapa_diario":
        return {}, {}
    por_sku: dict[str, str] = {}
    por_ean: dict[str, str] = {}
    for registro in historico.to_dict("records"):
        tipo = _normalizar_tipo_operacao(registro.get("tipo_operacao"))
        if not tipo:
            continue
        sku = texto_codigo(registro.get("sku"))
        ean = texto_codigo(registro.get("ean"))
        if sku:
            por_sku[sku] = tipo
        if ean:
            por_ean[ean] = tipo
    return por_sku, por_ean


def _resolver_regra(regras_map: dict[str, dict], fornecedor: object) -> dict:
    chave = normalizar_texto(fornecedor)
    if not chave:
        return {}
    if chave in regras_map:
        return regras_map[chave]

    alvo = ALIASES_FORNECEDOR.get(chave)
    if alvo:
        if alvo in regras_map:
            return regras_map[alvo]
        candidatos = [regra for nome, regra in regras_map.items() if alvo in nome or nome in alvo]
        if candidatos:
            return candidatos[0]

    # Fallback seguro: o nome curto deve aparecer como expressão completa na
    # razão social. Evita aproximações por similaridade que poderiam misturar
    # fornecedores diferentes.
    candidatos = []
    tokens_chave = chave.split()
    for nome, regra in regras_map.items():
        tokens_nome = nome.split()
        frase_no_nome = all(token in tokens_nome for token in tokens_chave)
        nome_na_frase = all(token in tokens_chave for token in tokens_nome)
        if frase_no_nome or nome_na_frase:
            if "exclusivo" in tokens_nome and "exclusivo" not in tokens_chave:
                continue
            if "perf" in tokens_nome and "perf" not in tokens_chave:
                continue
            candidatos.append((abs(len(nome) - len(chave)), nome, regra))
    if candidatos:
        candidatos.sort(key=lambda item: (item[0], item[1]))
        return candidatos[0][2]
    return {}


def _valor_escalar(valor: object, padrao: object = "") -> object:
    """Converte qualquer célula inesperadamente vetorial em um único escalar.

    Alguns históricos antigos possuem cabeçalhos duplicados e, dependendo de
    como o Excel foi lido, uma célula pode chegar como Series, ndarray ou lista.
    O pandas não aceita esses objetos 2D na montagem de um DataFrame por dicionário.
    """
    if isinstance(valor, pd.DataFrame):
        valor = valor.to_numpy(dtype=object).ravel().tolist()
    elif isinstance(valor, pd.Series):
        valor = valor.tolist()
    elif hasattr(valor, "ndim") and getattr(valor, "ndim", 0) > 0 and not isinstance(valor, (str, bytes)):
        try:
            valor = list(valor.ravel())
        except Exception:
            try:
                valor = list(valor)
            except Exception:
                pass

    if isinstance(valor, (list, tuple)):
        for item in valor:
            escolhido = _valor_escalar(item, padrao=pd.NA)
            if not pd.isna(escolhido) and str(escolhido).strip() not in {"", "nan", "None"}:
                return escolhido
        return padrao

    try:
        if pd.isna(valor):
            return padrao
    except (TypeError, ValueError):
        return padrao
    if isinstance(valor, str) and not valor.strip():
        return padrao
    return valor


def _col(df: pd.DataFrame, nome: str, padrao: object = "") -> pd.Series:
    """Retorna sempre uma Series 1D, mesmo com cabeçalhos duplicados.

    A seleção é feita por posição, não por rótulo. Isso evita que o pandas
    devolva um DataFrame 2D quando existem duas ou mais colunas com o mesmo
    nome canônico no histórico legado.
    """
    if df is None or not isinstance(df, pd.DataFrame):
        return pd.Series(dtype=object)

    posicoes = [i for i, coluna in enumerate(list(df.columns)) if coluna == nome]
    if not posicoes:
        return pd.Series([padrao] * len(df), index=df.index, dtype=object)

    bloco = df.iloc[:, posicoes]
    valores: list[object] = []
    matriz = bloco.to_numpy(dtype=object, copy=False)
    for linha in matriz:
        valores.append(_valor_escalar(list(linha), padrao))

    # Construir a partir de uma lista Python garante ndim=1 mesmo quando uma
    # célula de origem contém arrays/listas por corrupção do arquivo legado.
    return pd.Series(valores, index=df.index, dtype=object, name=nome)


def _normalizar_cadastro(df: pd.DataFrame) -> pd.DataFrame:
    cad = df.copy()
    for coluna in ["ean_compra", "ean_venda", "sku"]:
        cad[coluna] = _col(cad, coluna).map(texto_codigo)
    cad["status_ean"] = _col(cad, "status_ean", "Ativo")
    cad["caixaria_padrao"] = _col(cad, "caixaria_padrao", 1).map(lambda v: max(1, int(numero(v, 1))))
    cad["multiplo_padrao"] = _col(cad, "multiplo_padrao", 1).map(lambda v: max(1, int(numero(v, 1))))
    return cad


def _normalizar_regras(df: pd.DataFrame, desativados: Iterable[str]) -> pd.DataFrame:
    regras = df.copy()
    regras["fornecedor_norm"] = _col(regras, "fornecedor").map(normalizar_texto)
    desativados_norm = {normalizar_texto(v) for v in desativados}
    regras["ativo_bool"] = _col(regras, "ativo", "Sim").map(booleano_sim)
    regras.loc[regras["fornecedor_norm"].isin(desativados_norm), "ativo_bool"] = False
    regras["bloqueado_bool"] = _col(regras, "bloqueado", "Não").map(booleano_sim)
    regras["participa_cotacao_bool"] = _col(regras, "participa_cotacao", "Sim").map(booleano_sim)
    regras["participa_busca_bool"] = _col(regras, "participa_busca", "Sim").map(booleano_sim)
    regras["tipo_operacao_resolvida"] = [
        _tipo_operacao_regra(registro) for registro in regras.to_dict("records")
    ]
    return regras


def _mapa_cadastro(cadastro: pd.DataFrame) -> tuple[dict[str, dict], dict[str, dict]]:
    por_ean: dict[str, dict] = {}
    por_sku: dict[str, dict] = {}
    for _, linha in cadastro.iterrows():
        registro = linha.to_dict()
        sku = texto_codigo(registro.get("sku"))
        if sku:
            por_sku[sku] = registro
        for ean in {texto_codigo(registro.get("ean_compra")), texto_codigo(registro.get("ean_venda"))}:
            if ean:
                por_ean[ean] = registro
    return por_ean, por_sku


def _preparar_necessidade(df: pd.DataFrame, cadastro: pd.DataFrame) -> pd.DataFrame:
    por_ean, por_sku = _mapa_cadastro(cadastro)
    linhas: list[dict] = []
    for _, row in df.iterrows():
        item = row.to_dict()
        sku = texto_codigo(item.get("sku"))
        ean = texto_codigo(item.get("ean"))
        reg = por_sku.get(sku) if sku else por_ean.get(ean)
        if reg:
            sku = sku or texto_codigo(reg.get("sku"))
            ean = ean or texto_codigo(reg.get("ean_venda")) or texto_codigo(reg.get("ean_compra"))
        multiplo = max(
            1,
            int(numero(item.get("caixaria"), 1)),
            int(numero((reg or {}).get("multiplo_padrao"), 1)),
            int(numero((reg or {}).get("caixaria_padrao"), 1)),
        )
        qtd = max(0, int(math.ceil(numero(item.get("quantidade_solicitada"), 0))))
        qtd_ajustada = int(math.ceil(qtd / multiplo) * multiplo) if qtd else 0
        linhas.append(
            {
                **item,
                "sku": sku,
                "ean": ean,
                "descricao": item.get("descricao") or (reg or {}).get("descricao_oficial", ""),
                "descricao_oficial": (reg or {}).get("descricao_oficial", item.get("descricao", "")),
                "fabricante": item.get("fabricante") or (reg or {}).get("fabricante", ""),
                "categoria": item.get("categoria") or (reg or {}).get("categoria", ""),
                "quantidade_solicitada": qtd,
                "quantidade_ajustada": qtd_ajustada,
                "multiplo": multiplo,
                "ean_encontrado": bool(reg),
                "ruptura_cronica_bool": booleano_sim(item.get("ruptura_cronica")),
                "ultimo_custo": numero(item.get("ultimo_custo"), numero(item.get("pmz"), 0)),
            }
        )
    return pd.DataFrame(linhas)


def _regra_fornecedor(regras: pd.DataFrame, fornecedor: object) -> dict:
    regras_map = {
        str(registro.get("fornecedor_norm", "")): registro
        for registro in regras.to_dict("records")
        if str(registro.get("fornecedor_norm", ""))
    }
    return _resolver_regra(regras_map, fornecedor)


def _homologado(homologacao: pd.DataFrame, ol: object, fornecedor: object) -> bool:
    if homologacao.empty:
        return True
    ol_norm = normalizar_texto(ol)
    forn_norm = normalizar_texto(fornecedor)
    for _, linha in homologacao.iterrows():
        if normalizar_texto(linha.get("ol_industria")) == ol_norm and normalizar_texto(linha.get("fornecedor")) == forn_norm:
            return booleano_sim(linha.get("ativo"))
    return False


def _preparar_ofertas(
    cotacao: pd.DataFrame,
    cadastro: pd.DataFrame,
    regras: pd.DataFrame,
    homologacao: pd.DataFrame,
    eans_interesse: set[str] | None = None,
    tipo_historico_por_sku: dict[str, str] | None = None,
    tipo_historico_por_ean: dict[str, str] | None = None,
) -> pd.DataFrame:
    por_ean, _ = _mapa_cadastro(cadastro)
    tipo_historico_por_sku = tipo_historico_por_sku or {}
    tipo_historico_por_ean = tipo_historico_por_ean or {}
    regras_map = {
        str(registro.get("fornecedor_norm", "")): registro
        for registro in regras.to_dict("records")
        if str(registro.get("fornecedor_norm", ""))
    }
    homologacao_map = {
        (normalizar_texto(registro.get("ol_industria")), normalizar_texto(registro.get("fornecedor"))): booleano_sim(registro.get("ativo"))
        for registro in homologacao.to_dict("records")
    } if not homologacao.empty else {}
    homologacao_tipo = {
        (normalizar_texto(registro.get("ol_industria")), normalizar_texto(registro.get("fornecedor"))): str(registro.get("tipo_operacao") or "")
        for registro in homologacao.to_dict("records")
    } if not homologacao.empty else {}

    # Resolver a regra uma única vez por fornecedor. A cotação real tem cerca de
    # 129 mil linhas, mas somente poucas dezenas de fornecedores distintos.
    fornecedores_originais = {
        normalizar_texto(valor): valor
        for valor in _col(cotacao, "fornecedor")
        if normalizar_texto(valor)
    }
    regras_resolvidas = {
        chave: _resolver_regra(regras_map, valor)
        for chave, valor in fornecedores_originais.items()
    }

    linhas: list[dict] = []
    for original in cotacao.to_dict("records"):
        eans = dividir_eans(original.get("ean")) or [""]
        if eans_interesse is not None and not any(ean in eans_interesse for ean in eans):
            continue
        fornecedor = original.get("fornecedor", "")
        fornecedor_norm = normalizar_texto(fornecedor)
        regra = regras_resolvidas.get(fornecedor_norm, {})
        tipo_operacao = _primeiro_preenchido(
            original.get("tipo_operacao"), regra.get("tipo_operacao_resolvida", "")
        )
        embalagem = max(1, int(numero(original.get("embalagem"), 1)))
        multiplo = max(1, int(numero(original.get("multiplo"), embalagem)))
        preco_final_base = numero(original.get("preco_final"), 0)
        preco_fabrica = numero(original.get("preco_fabrica"), 0)
        desconto = numero(original.get("desconto"), 0)
        if preco_final_base <= 0 and preco_fabrica > 0:
            desconto_decimal = desconto / 100 if desconto > 1 else desconto
            preco_final_base = preco_fabrica * (1 - desconto_decimal)
        tipo_preco = normalizar_texto(original.get("tipo_preco"))
        estoque = max(0, int(numero(original.get("estoque_fornecedor"), 0)))
        for ean in eans:
            cad = por_ean.get(ean)
            industria = _primeiro_preenchido(original.get("ol_industria"), (cad or {}).get("fabricante"))
            ol_norm = normalizar_texto(industria)
            tipo_homologacao = homologacao_tipo.get((ol_norm, fornecedor_norm), "")
            sku_item = texto_codigo((cad or {}).get("sku"))
            tipo_historico = _primeiro_preenchido(
                tipo_historico_por_sku.get(sku_item, ""),
                tipo_historico_por_ean.get(ean, ""),
            )
            tipo_operacao_item = _normalizar_tipo_operacao(
                _primeiro_preenchido(tipo_historico, tipo_operacao, tipo_homologacao)
            ) or "Não informado"
            eh_ol = normalizar_texto(tipo_operacao_item) == "ol"
            homologado = True if not eh_ol or not homologacao_map else homologacao_map.get((ol_norm, fornecedor_norm), False)
            divisor = max(embalagem, multiplo, int(numero((cad or {}).get("caixaria_padrao"), 1)))
            preco_unitario = preco_final_base / divisor if "caixa" in tipo_preco else preco_final_base

            motivos: list[str] = []
            if cad is None:
                motivos.append("EAN não encontrado")
            elif normalizar_texto(cad.get("status_ean", "Ativo")) not in {"ativo", "ok", "sim"}:
                motivos.append("EAN inativo")
            if not regra:
                motivos.append("Fornecedor sem regra")
            else:
                if not bool(regra.get("ativo_bool")):
                    motivos.append("Fornecedor desativado")
                if bool(regra.get("bloqueado_bool")):
                    motivos.append("Fornecedor bloqueado")
                if not bool(regra.get("participa_cotacao_bool")):
                    motivos.append("Fornecedor fora da cotação")
            if eh_ol and not homologado:
                motivos.append("OL não homologada")
            if preco_unitario <= 0:
                motivos.append("Sem preço válido")
            if estoque <= 0:
                motivos.append("Sem estoque")

            linhas.append(
                {
                    **original,
                    "ean_original": texto_codigo(original.get("ean")),
                    "ean": ean,
                    "sku": texto_codigo((cad or {}).get("sku")),
                    "descricao_oficial": _primeiro_preenchido(
                        (cad or {}).get("descricao_oficial"), original.get("descricao_recebida", "")
                    ),
                    "fabricante": _primeiro_preenchido((cad or {}).get("fabricante"), ""),
                    "categoria": _primeiro_preenchido((cad or {}).get("categoria"), ""),
                    "fornecedor": fornecedor,
                    "fornecedor_regra": regra.get("fornecedor", ""),
                    "codigo_fornecedor": texto_codigo(original.get("codigo_fornecedor") or regra.get("codigo_fornecedor")),
                    "tipo_operacao": tipo_operacao_item or "Não informado",
                    "ol_industria": industria or "Não informado",
                    "preco_fabrica": preco_fabrica,
                    "preco_final": preco_final_base,
                    "preco_unitario": round(preco_unitario, 6),
                    "estoque_fornecedor": estoque,
                    "caixaria": divisor,
                    "multiplo": multiplo,
                    "prazo_pagamento": regra.get("prazo_pagamento", ""),
                    "lead_time": regra.get("lead_time", ""),
                    "email": regra.get("email", ""),
                    "origem": "Cotação atual",
                    "valida": not motivos,
                    "motivos_rejeicao": " | ".join(dict.fromkeys(motivos)),
                    "status_ean": "OK" if cad is not None else "EAN não encontrado",
                    "status_fornecedor": "OK" if regra and bool(regra.get("ativo_bool")) and not bool(regra.get("bloqueado_bool")) else "Inválido",
                    "status_homologacao": "OK" if homologado else "Não homologada",
                }
            )
    return pd.DataFrame(linhas)


def _enriquecer_ofertas_com_necessidade(ofertas: pd.DataFrame, necessidade: pd.DataFrame) -> pd.DataFrame:
    if ofertas.empty or necessidade.empty:
        return ofertas
    meta = necessidade[["sku", "descricao_oficial", "fabricante", "categoria"]].copy()
    meta = meta.drop_duplicates(subset=["sku"], keep="first").set_index("sku")
    # Trabalha no próprio DataFrame para não duplicar centenas de milhares de
    # células em memória no Streamlit.
    resultado = ofertas
    for coluna in ["descricao_oficial", "fabricante", "categoria"]:
        mapa = meta[coluna].to_dict()
        atual = _col(resultado, coluna)
        complemento = resultado["sku"].map(mapa)
        vazio = atual.map(lambda valor: not normalizar_texto(valor))
        resultado.loc[vazio, coluna] = complemento.loc[vazio]
    return resultado


def _ofertas_historico(
    historico: pd.DataFrame,
    sku: str,
    regras: pd.DataFrame,
    quantidade: int,
) -> pd.DataFrame:
    if (
        historico.empty
        or not sku
        or historico.attrs.get("uso_busca_ampliada") is False
    ):
        return pd.DataFrame()
    hist = historico.copy()
    hist["sku"] = _col(hist, "sku").map(texto_codigo)
    hist = hist[hist["sku"] == sku].copy()
    if hist.empty:
        return hist
    linhas = []
    for _, row in hist.iterrows():
        item = row.to_dict()
        regra = _regra_fornecedor(regras, item.get("fornecedor"))
        if not regra or not bool(regra.get("ativo_bool")) or bool(regra.get("bloqueado_bool")) or not bool(regra.get("participa_busca_bool")):
            continue
        preco = numero(item.get("preco_unitario"), numero(item.get("preco_final"), 0))
        estoque = int(numero(item.get("estoque_fornecedor"), 0))
        if preco <= 0 or estoque <= 0:
            continue
        linhas.append(
            {
                **item,
                "ean": texto_codigo(item.get("ean")),
                "sku": sku,
                "codigo_fornecedor": texto_codigo(item.get("codigo_fornecedor") or regra.get("codigo_fornecedor")),
                "preco_unitario": preco,
                "estoque_fornecedor": estoque,
                "prazo_pagamento": regra.get("prazo_pagamento", item.get("prazo_pagamento", "")),
                "lead_time": regra.get("lead_time", item.get("lead_time", "")),
                "email": regra.get("email", item.get("email", "")),
                "origem": "Busca ampliada",
                "valida": True,
                "motivos_rejeicao": "",
                "atende_total": estoque >= quantidade,
            }
        )
    return pd.DataFrame(linhas)


def _pendencias_ofertas(ofertas: pd.DataFrame) -> list[dict]:
    pendencias: list[dict] = []
    if ofertas.empty:
        return pendencias
    for _, oferta in ofertas[~ofertas["valida"]].iterrows():
        for motivo in str(oferta.get("motivos_rejeicao", "")).split(" | "):
            if not motivo:
                continue
            acao = {
                "EAN não encontrado": "Cadastrar o EAN no cadastro EAN/SKU.",
                "Fornecedor bloqueado": "Revisar o bloqueio do fornecedor.",
                "Fornecedor desativado": "Reativar o fornecedor apenas se a regra estiver correta.",
                "OL não homologada": "Homologar a relação OL × distribuidor ou usar outra oferta.",
                "Sem preço válido": "Verificar PF, desconto ou preço final enviado.",
                "Sem estoque": "Usar outra opção ou busca ampliada.",
                "Fornecedor sem regra": "Cadastrar o fornecedor na base de regras.",
            }.get(motivo, "Revisar a base de origem.")
            pendencias.append(
                {
                    "SKU": texto_codigo(oferta.get("sku")),
                    "EAN": texto_codigo(oferta.get("ean")),
                    "Descrição": oferta.get("descricao_oficial") or oferta.get("descricao_recebida", ""),
                    "Fornecedor": oferta.get("fornecedor", ""),
                    "Pendência": motivo,
                    "Ação sugerida": acao,
                    "Impacto": "Oferta desconsiderada pelo motor",
                }
            )
    return pendencias


def _motivos_rejeicao_item(ofertas: pd.DataFrame, sku: str, ean: str) -> list[tuple[str, str]]:
    if ofertas.empty:
        return []
    relacionadas = ofertas[(ofertas["sku"] == sku) | (ofertas["ean"] == ean)]
    if relacionadas.empty:
        return []
    motivos_fornecedores: dict[str, set[str]] = {}
    for _, oferta in relacionadas[~relacionadas["valida"]].iterrows():
        fornecedor = str(oferta.get("fornecedor", "") or "")
        for motivo in str(oferta.get("motivos_rejeicao", "")).split(" | "):
            if motivo:
                motivos_fornecedores.setdefault(motivo, set()).add(fornecedor)
    return [
        (motivo, ", ".join(sorted(f for f in fornecedores if f)))
        for motivo, fornecedores in motivos_fornecedores.items()
    ]


def _historico_atualizado(
    historico: pd.DataFrame, ofertas: pd.DataFrame, id_carga: str, cadastro: pd.DataFrame
) -> pd.DataFrame:
    eh_mapa_diario = bool(
        historico is not None
        and historico.attrs.get("formato_historico") == "mapa_diario"
    )
    anterior_interno = (
        pd.DataFrame() if eh_mapa_diario
        else (historico.copy() if historico is not None else pd.DataFrame())
    )
    if anterior_interno.empty:
        anterior = pd.DataFrame()
    elif "ID da carga" in anterior_interno.columns:
        anterior = anterior_interno.copy()
        anterior = anterior.rename(columns={"Fornecedor": "Fornecedor da cotação"})
        if "Código fornecedor" not in anterior.columns:
            anterior.insert(min(3, len(anterior.columns)), "Código fornecedor", "")
    else:
        anterior = pd.DataFrame(
            {
                "Data processamento": _col(anterior_interno, "data_processamento"),
                "Data da carga": _col(anterior_interno, "data_carga"),
                "ID da carga": _col(anterior_interno, "id_carga"),
                "Código fornecedor": _col(anterior_interno, "codigo_fornecedor"),
                "Fornecedor da cotação": _col(anterior_interno, "fornecedor"),
                "Tipo operação": _col(anterior_interno, "tipo_operacao"),
                "OL / Indústria": _col(anterior_interno, "ol_industria"),
                "SKU identificado": _col(anterior_interno, "sku").map(texto_codigo),
                "EAN tratado": _col(anterior_interno, "ean").map(texto_codigo),
                "EAN original": _col(anterior_interno, "ean_original").map(texto_codigo),
                "Descrição recebida": _col(anterior_interno, "descricao_recebida"),
                "Descrição oficial": _col(anterior_interno, "descricao_oficial"),
                "Fabricante": _col(anterior_interno, "fabricante"),
                "Categoria": _col(anterior_interno, "categoria"),
                "Preço Fábrica": _col(anterior_interno, "preco_fabrica").map(numero),
                "Desconto": _col(anterior_interno, "desconto").map(numero),
                "Preço Final": _col(anterior_interno, "preco_final").map(numero),
                "Tipo preço": _col(anterior_interno, "tipo_preco"),
                "Caixaria final": _col(anterior_interno, "caixaria").map(numero),
                "Múltiplo": _col(anterior_interno, "multiplo").map(numero),
                "Estoque fornecedor": _col(anterior_interno, "estoque_fornecedor").map(numero),
                "Preço unitário": _col(anterior_interno, "preco_unitario").map(numero),
                "Status EAN": _col(anterior_interno, "status_ean"),
                "Status fornecedor": _col(anterior_interno, "status_fornecedor"),
                "Status homologação OL": _col(anterior_interno, "status_homologacao"),
                "Observação sistema": _col(anterior_interno, "observacao_sistema"),
            }
        )
    if not anterior.empty:
        # Remove cabeçalhos antigos importados como se fossem registros.
        fornecedor_col = "Fornecedor da cotação" if "Fornecedor da cotação" in anterior.columns else "Fornecedor"
        mascara_cabecalho = anterior[fornecedor_col].map(normalizar_texto).isin({"fornecedor", "distribuidor"})
        anterior = anterior.loc[~mascara_cabecalho].copy()
        anterior["Origem do registro"] = anterior.get("Origem do registro", "Legado")

    # Enriquece registros legados com tudo que pode ser recuperado pelo EAN.
    # Datas e nomes de fornecedor que não existiam no arquivo original não são
    # inventados; esses casos ficam identificados na observação.
    if not anterior.empty:
        por_ean, por_sku = _mapa_cadastro(cadastro)
        enriquecidos = []
        for registro in anterior.to_dict("records"):
            ean = texto_codigo(registro.get("EAN tratado") or registro.get("EAN original"))
            sku = texto_codigo(registro.get("SKU identificado"))
            cad = por_sku.get(sku) if sku else por_ean.get(ean)
            if cad:
                registro["SKU identificado"] = sku or texto_codigo(cad.get("sku"))
                registro["Descrição oficial"] = _primeiro_preenchido(
                    registro.get("Descrição oficial"), cad.get("descricao_oficial")
                )
                registro["Fabricante"] = _primeiro_preenchido(
                    registro.get("Fabricante"), cad.get("fabricante")
                )
                registro["Categoria"] = _primeiro_preenchido(
                    registro.get("Categoria"), cad.get("categoria")
                )
                registro["Status EAN"] = _primeiro_preenchido(registro.get("Status EAN"), "OK")
            preco_unitario = numero(registro.get("Preço unitário"), 0)
            if preco_unitario <= 0:
                divisor = max(
                    1,
                    int(numero(registro.get("Caixaria final"), 1)),
                    int(numero(registro.get("Múltiplo"), 1)),
                )
                preco_final = numero(registro.get("Preço Final"), 0)
                registro["Preço unitário"] = preco_final / divisor if preco_final > 0 else 0
            observacao_valor = registro.get("Observação sistema")
            observacao = str(observacao_valor).strip() if normalizar_texto(observacao_valor) and normalizar_texto(observacao_valor) != "nan" else ""
            faltas_legado = []
            if not normalizar_texto(registro.get("Data processamento")):
                faltas_legado.append("data de processamento")
            if not normalizar_texto(registro.get("Data da carga")):
                faltas_legado.append("data da carga")
            if not normalizar_texto(registro.get("Tipo operação")):
                faltas_legado.append("tipo de operação")
            if faltas_legado:
                aviso = "Registro legado sem " + ", ".join(faltas_legado)
                registro["Observação sistema"] = " | ".join(v for v in [observacao, aviso] if v)
            enriquecidos.append(registro)
        anterior = pd.DataFrame(enriquecidos, columns=anterior.columns)

    agora = agora_brasil_sem_fuso()
    novos = pd.DataFrame(
        {
            "Data processamento": [agora] * len(ofertas),
            "Origem do registro": ["Rodada atual"] * len(ofertas),
            "Data da carga": _col(ofertas, "data_carga").map(
                lambda valor: valor if normalizar_texto(valor) else agora.date()
            ),
            "ID da carga": [id_carga] * len(ofertas),
            "Código fornecedor": _col(ofertas, "codigo_fornecedor"),
            "Fornecedor da cotação": _col(ofertas, "fornecedor"),
            "Tipo operação": _col(ofertas, "tipo_operacao"),
            "OL / Indústria": _col(ofertas, "ol_industria"),
            "SKU identificado": _col(ofertas, "sku").map(texto_codigo),
            "EAN tratado": _col(ofertas, "ean").map(texto_codigo),
            "EAN original": _col(ofertas, "ean_original").map(texto_codigo),
            "Descrição recebida": _col(ofertas, "descricao_recebida"),
            "Descrição oficial": _col(ofertas, "descricao_oficial"),
            "Fabricante": _col(ofertas, "fabricante"),
            "Categoria": _col(ofertas, "categoria"),
            "Preço Fábrica": _col(ofertas, "preco_fabrica").map(numero),
            "Desconto": _col(ofertas, "desconto").map(numero),
            "Preço Final": _col(ofertas, "preco_final").map(numero),
            "Tipo preço": _col(ofertas, "tipo_preco"),
            "Caixaria final": _col(ofertas, "caixaria").map(numero),
            "Múltiplo": _col(ofertas, "multiplo").map(numero),
            "Estoque fornecedor": _col(ofertas, "estoque_fornecedor").map(numero),
            "Preço unitário": _col(ofertas, "preco_unitario").map(numero),
            "Status EAN": _col(ofertas, "status_ean"),
            "Status fornecedor": _col(ofertas, "status_fornecedor"),
            "Status homologação OL": _col(ofertas, "status_homologacao"),
            "Observação sistema": _col(ofertas, "motivos_rejeicao"),
        }
    )
    # Campos que não existem na cotação atual são identificados claramente,
    # em vez de serem exportados como células silenciosamente vazias.
    novos["Tipo operação"] = novos["Tipo operação"].map(
        lambda valor: valor if normalizar_texto(valor) else "Não informado"
    )
    novos["OL / Indústria"] = [
        (ol if normalizar_texto(ol) else ("Não informado" if normalizar_texto(tipo) == "ol" else "Não se aplica"))
        for ol, tipo in zip(novos["OL / Indústria"], novos["Tipo operação"])
    ]
    novos["Tipo preço"] = novos["Tipo preço"].map(
        lambda valor: valor if normalizar_texto(valor) else "Unitário"
    )

    combinado = pd.concat([anterior, novos], ignore_index=True, sort=False)
    chaves = [c for c in ["ID da carga", "Fornecedor", "EAN tratado", "SKU identificado", "Preço unitário"] if c in combinado.columns]
    if chaves:
        combinado = combinado.drop_duplicates(subset=chaves, keep="last")
    return combinado.reset_index(drop=True)


def executar_motor(
    cotacao: pd.DataFrame,
    necessidade: pd.DataFrame,
    cadastro: pd.DataFrame,
    regras_fornecedor: pd.DataFrame,
    homologacao_ol: pd.DataFrame | None = None,
    historico: pd.DataFrame | None = None,
    fornecedores_desativados: Iterable[str] = (),
    id_carga: str = "",
    diagnostico: dict[str, object] | None = None,
) -> ResultadoMotor:
    homologacao_ol = homologacao_ol if homologacao_ol is not None else pd.DataFrame()
    historico = historico if historico is not None else pd.DataFrame()
    diagnostico = diagnostico or {}
    id_carga = id_carga or agora_brasil().strftime("QDC_%Y%m%d_%H%M%S_%f")[:-3]

    cadastro_n = _normalizar_cadastro(cadastro)
    regras_n = _normalizar_regras(regras_fornecedor, fornecedores_desativados)
    necessidade_n = _preparar_necessidade(necessidade, cadastro_n)

    # A aba EAN contém apenas a relação SKU × EAN. Fabricante, descrição e
    # categoria vêm de Volume de Compras. Enriquecemos o cadastro antes de
    # validar homologação OL, pois a indústria é indispensável para cruzar
    # indústria × distribuidor no Mapa de Envio de Pedidos.
    if not cadastro_n.empty and not necessidade_n.empty:
        meta_por_sku = necessidade_n.drop_duplicates("sku", keep="first").set_index("sku")
        for coluna in ("descricao_oficial", "fabricante", "categoria"):
            if coluna not in cadastro_n.columns:
                cadastro_n[coluna] = ""
            mapa = meta_por_sku[coluna].to_dict() if coluna in meta_por_sku.columns else {}
            complemento = cadastro_n["sku"].map(mapa)
            vazio = cadastro_n[coluna].map(lambda valor: not normalizar_texto(valor))
            cadastro_n.loc[vazio, coluna] = complemento.loc[vazio]

    # Somente itens com Pedido Efetivo positivo entram no motor. Linhas zeradas
    # permanecem no Planejamento, mas não devem virar pedido nem pendência.
    necessidade_n = necessidade_n[necessidade_n["quantidade_ajustada"] > 0].reset_index(drop=True)

    # A cotação real possui ~129 mil linhas, mas a rodada pede menos de 2 mil
    # SKUs. Filtramos antes de materializar o DataFrame enriquecido de ofertas,
    # reduzindo fortemente memória e tempo sem alterar a decisão do motor.
    skus_interesse = set(necessidade_n["sku"].map(texto_codigo))
    eans_interesse = {
        texto_codigo(valor)
        for valor in necessidade_n["ean"]
        if texto_codigo(valor)
    }
    cadastro_interesse = cadastro_n[cadastro_n["sku"].isin(skus_interesse)]
    for coluna_ean in ["ean_compra", "ean_venda"]:
        eans_interesse.update(
            texto_codigo(valor)
            for valor in _col(cadastro_interesse, coluna_ean)
            if texto_codigo(valor)
        )

    regras_map = {
        str(registro.get("fornecedor_norm", "")): registro
        for registro in regras_n.to_dict("records")
        if str(registro.get("fornecedor_norm", ""))
    }
    fornecedores_cotacao = sorted({str(v).strip() for v in _col(cotacao, "fornecedor") if str(v).strip()})
    fornecedores_sem_regra = sorted([
        fornecedor
        for fornecedor in fornecedores_cotacao
        if not _resolver_regra(regras_map, fornecedor)
    ])

    tipo_historico_por_sku, tipo_historico_por_ean = _mapas_classificacao_historica(historico)
    diagnostico["classificacoes_historicas_por_sku"] = len(tipo_historico_por_sku)

    ofertas = _preparar_ofertas(
        cotacao,
        cadastro_n,
        regras_n,
        homologacao_ol,
        eans_interesse=eans_interesse,
        tipo_historico_por_sku=tipo_historico_por_sku,
        tipo_historico_por_ean=tipo_historico_por_ean,
    )
    diagnostico["linhas_cotacao_relevantes"] = len(ofertas)
    ofertas = _enriquecer_ofertas_com_necessidade(ofertas, necessidade_n)

    diagnostico["fornecedores_cotacao"] = len(fornecedores_cotacao)
    diagnostico["fornecedores_mapeados"] = len(fornecedores_cotacao) - len(fornecedores_sem_regra)
    diagnostico["fornecedores_sem_regra"] = fornecedores_sem_regra

    # Pendências são consolidadas apenas para os SKUs efetivamente solicitados;
    # não registramos uma pendência para cada uma das milhares de ofertas rejeitadas.
    pendencias: list[dict] = []
    pedido_linhas: list[dict] = []
    opcoes_linhas: list[dict] = []

    grupos_validos_sku = {
        texto_codigo(chave): list(indices)
        for chave, indices in ofertas[ofertas["valida"]].groupby("sku", sort=False).groups.items()
        if texto_codigo(chave)
    }
    grupos_sku = {
        texto_codigo(chave): list(indices)
        for chave, indices in ofertas.groupby("sku", sort=False).groups.items()
        if texto_codigo(chave)
    }
    grupos_ean = {
        texto_codigo(chave): list(indices)
        for chave, indices in ofertas.groupby("ean", sort=False).groups.items()
        if texto_codigo(chave)
    }

    for item in necessidade_n.to_dict("records"):
        sku = texto_codigo(item.get("sku"))
        ean = texto_codigo(item.get("ean"))
        qtd = int(item.get("quantidade_ajustada", 0))

        if not bool(item.get("ean_encontrado")):
            pendencias.append(
                {
                    "ID da carga": id_carga,
                    "SKU": sku,
                    "EAN": ean,
                    "Descrição": item.get("descricao", ""),
                    "Fornecedor": "",
                    "Pendência": "EAN não encontrado",
                    "Ação sugerida": "Cadastrar o EAN no cadastro EAN/SKU.",
                    "Impacto": "Item não entra no pedido",
                }
            )
            continue

        indices_atuais = grupos_validos_sku.get(sku, [])
        atuais = ofertas.loc[indices_atuais].copy() if indices_atuais else pd.DataFrame()
        if not atuais.empty:
            atuais["atende_total"] = atuais["estoque_fornecedor"] >= qtd

        precisa_busca = bool(item.get("ruptura_cronica_bool")) and (atuais.empty or not atuais["atende_total"].any())
        ampliadas = _ofertas_historico(historico, sku, regras_n, qtd) if precisa_busca else pd.DataFrame()
        candidatas = pd.concat([atuais, ampliadas], ignore_index=True, sort=False)
        if not candidatas.empty:
            candidatas = candidatas.drop_duplicates(subset=["fornecedor", "preco_unitario", "estoque_fornecedor"], keep="first")
            candidatas = candidatas.sort_values(
                by=["preco_unitario", "estoque_fornecedor"], ascending=[True, False], na_position="last"
            ).reset_index(drop=True)

        if candidatas.empty:
            indices_relacionadas = grupos_sku.get(sku) or grupos_ean.get(ean) or []
            relacionadas = ofertas.loc[indices_relacionadas] if indices_relacionadas else pd.DataFrame()
            motivos_item = _motivos_rejeicao_item(relacionadas, sku, ean)
            if motivos_item:
                acoes = {
                    "EAN não encontrado": "Cadastrar o EAN no cadastro EAN/SKU.",
                    "Fornecedor bloqueado": "Revisar o bloqueio do fornecedor.",
                    "Fornecedor desativado": "Reativar o fornecedor apenas se a regra estiver correta.",
                    "OL não homologada": "Homologar a relação OL × distribuidor ou usar outra oferta.",
                    "Sem preço válido": "Verificar preço final, preço fábrica ou desconto.",
                    "Sem estoque": "Solicitar nova cotação ou usar a busca ampliada.",
                    "Fornecedor sem regra": "Cadastrar o fornecedor na base de regras.",
                }
                motivos_unicos = list(dict.fromkeys(motivo for motivo, _ in motivos_item))
                fornecedores_unicos = sorted({
                    fornecedor.strip()
                    for _, fornecedores in motivos_item
                    for fornecedor in fornecedores.split(",")
                    if fornecedor.strip()
                })
                acoes_unicas = list(dict.fromkeys(acoes.get(motivo, "Revisar a base de origem.") for motivo in motivos_unicos))
                pendencias.append(
                    {
                        "ID da carga": id_carga,
                        "SKU": sku,
                        "EAN": ean,
                        "Descrição": item.get("descricao", ""),
                        "Fornecedor": ", ".join(fornecedores_unicos),
                        "Pendência": "Sem oferta válida",
                        "Motivos encontrados": " | ".join(motivos_unicos),
                        "Ação sugerida": " | ".join(acoes_unicas),
                        "Impacto": "Item não entra no pedido",
                    }
                )
            else:
                pendencias.append(
                    {
                        "ID da carga": id_carga,
                        "SKU": sku,
                        "EAN": ean,
                        "Descrição": item.get("descricao", ""),
                        "Fornecedor": "",
                        "Pendência": "Sem oferta válida",
                        "Ação sugerida": "Revisar cotação, regras e homologações.",
                        "Impacto": "Item não entra no pedido",
                    }
                )
            continue

        top4 = candidatas.head(4).copy()
        completas = candidatas[candidatas["estoque_fornecedor"] >= qtd]
        if not completas.empty:
            recomendada = completas.iloc[0]
            status = "Busca ampliada" if recomendada.get("origem") == "Busca ampliada" else "OK"
        else:
            recomendada = candidatas.sort_values("estoque_fornecedor", ascending=False).iloc[0]
            status = "Pendente"
            pendencias.append(
                {
                    "ID da carga": id_carga,
                    "SKU": sku,
                    "EAN": ean,
                    "Descrição": item.get("descricao", ""),
                    "Fornecedor": recomendada.get("fornecedor", ""),
                    "Pendência": "Sem estoque suficiente",
                    "Ação sugerida": "Negociar atendimento parcial ou buscar nova oferta.",
                    "Impacto": f"Necessidade {qtd}; maior estoque encontrado {int(recomendada.get('estoque_fornecedor', 0))}",
                }
            )

        opcao1 = top4.iloc[0]
        ultimo_custo = numero(item.get("ultimo_custo"), 0)
        variacao1 = (numero(opcao1.get("preco_unitario")) / ultimo_custo - 1) if ultimo_custo > 0 else None
        variacao_rec = (numero(recomendada.get("preco_unitario")) / ultimo_custo - 1) if ultimo_custo > 0 else None
        nova = normalizar_texto(opcao1.get("fornecedor")) != normalizar_texto(recomendada.get("fornecedor"))

        pedido_linhas.append(
            {
                "ID da carga": id_carga,
                "Loja": 1015,
                "Ciclo": agora_brasil().strftime("%Y%m%d") + "/p1",
                "Tratativa": recomendada.get("tipo_operacao", "Não informado"),
                "Fabricante ": item.get("fabricante", ""),
                "Categoria ": item.get("categoria", ""),
                "Condição Pagamento": opcao1.get("prazo_pagamento", ""),
                "Condição Leilão": 1,
                "Código Fornecedor": texto_codigo(opcao1.get("codigo_fornecedor")),
                "Prazo Pagamento": opcao1.get("prazo_pagamento", ""),
                "SKU": sku,
                "EAN": ean,
                "Tipo de Produto": item.get("categoria", ""),
                "Descrição": item.get("descricao_oficial") or item.get("descricao", ""),
                "Quantidade Solicitada": qtd,
                "Variação 1": variacao1,
                "Status ": "Opção 1 atende" if int(opcao1.get("estoque_fornecedor", 0)) >= qtd else "Tratar - atende parcial",
                "Novo Fornecedor ": recomendada.get("fornecedor", "") if nova else "",
                "Novo Código Fornecedor ": texto_codigo(recomendada.get("codigo_fornecedor")) if nova else "",
                "Nova Variação": variacao_rec if nova else None,
                "Unidade": "UN",
                "Preço": numero(opcao1.get("preco_unitario")),
                "Prazo Entrega": opcao1.get("lead_time", ""),
                "Embalagem": int(item.get("multiplo", 1)),
                "Tipo Condição": recomendada.get("tipo_operacao", "Não informado"),
                "ComercialDiscount": 0,
                "FinancialDiscount": 0,
                "E-Mail": opcao1.get("email", ""),
                "NR COTAÇÃO": id_carga,
                "Comprador ": item.get("comprador", ""),
                "Fornecedor recomendado": recomendada.get("fornecedor", ""),
                "Tipo operação recomendado": recomendada.get("tipo_operacao", "Não informado"),
                "OL / Indústria recomendada": recomendada.get("ol_industria", "Não informado"),
                "Status homologação OL": recomendada.get("status_homologacao", "Não informado"),
                "Preço recomendado": numero(recomendada.get("preco_unitario")),
                "Estoque recomendado": int(recomendada.get("estoque_fornecedor", 0)),
                "Origem recomendada": recomendada.get("origem", ""),
                "Status motor": status,
                "Valor total": numero(recomendada.get("preco_unitario")) * qtd,
            }
        )

        linha_opcoes = {"ID da carga": id_carga, "SKU": sku, "Quantidade solicitada": qtd}
        for posicao in range(1, 5):
            if posicao <= len(top4):
                oferta = top4.iloc[posicao - 1]
                variacao = (numero(oferta.get("preco_unitario")) / ultimo_custo - 1) if ultimo_custo > 0 else None
                linha_opcoes.update(
                    {
                        f"Código fornecedor {posicao}": texto_codigo(oferta.get("codigo_fornecedor")),
                        f"Fornecedor {posicao}": oferta.get("fornecedor", ""),
                        f"Estoque {posicao}": int(oferta.get("estoque_fornecedor", 0)),
                        f"Preço {posicao}": numero(oferta.get("preco_unitario")),
                        f"Variação custo {posicao}": variacao,
                    }
                )
            else:
                linha_opcoes.update(
                    {
                        f"Código fornecedor {posicao}": "",
                        f"Fornecedor {posicao}": "",
                        f"Estoque {posicao}": "",
                        f"Preço {posicao}": "",
                        f"Variação custo {posicao}": "",
                    }
                )
        opcoes_linhas.append(linha_opcoes)

    pedido = pd.DataFrame(pedido_linhas)
    opcoes = pd.DataFrame(opcoes_linhas)
    pendencias_df = pd.DataFrame(pendencias).drop_duplicates().reset_index(drop=True) if pendencias else pd.DataFrame(
        columns=["ID da carga", "SKU", "EAN", "Descrição", "Fornecedor", "Pendência", "Motivos encontrados", "Ação sugerida", "Impacto"]
    )
    # O histórico operacional guarda somente ofertas dos SKUs efetivamente
    # solicitados nesta rodada. Isso preserva a rastreabilidade e evita carregar
    # centenas de milhares de linhas irrelevantes na memória do Streamlit.
    skus_processados = set(necessidade_n["sku"].map(texto_codigo))
    ofertas_relevantes = ofertas[ofertas["sku"].isin(skus_processados)].copy()
    historico_atualizado = _historico_atualizado(historico, ofertas_relevantes, id_carga, cadastro_n)

    valor_total = numero(pedido.get("Valor total", pd.Series(dtype=float)).sum(), 0) if not pedido.empty else 0
    por_fornecedor = (
        pedido.groupby("Fornecedor recomendado", dropna=False)["Valor total"].sum().sort_values(ascending=False).reset_index()
        if not pedido.empty
        else pd.DataFrame(columns=["Fornecedor recomendado", "Valor total"])
    )
    motivos = (
        pendencias_df["Pendência"].value_counts().rename_axis("Pendência").reset_index(name="Quantidade")
        if not pendencias_df.empty
        else pd.DataFrame(columns=["Pendência", "Quantidade"])
    )
    resumo = {
        "id_carga": id_carga,
        "processado_em": agora_brasil(),
        "valor_total": valor_total,
        "skus_necessidade": len(necessidade_n),
        "skus_pedido": len(pedido),
        "pendencias": len(pendencias_df),
        "sem_oferta": int((pendencias_df["Pendência"] == "Sem oferta válida").sum()) if not pendencias_df.empty else 0,
        "fornecedores": int(pedido["Fornecedor recomendado"].nunique()) if not pedido.empty else 0,
        "busca_ampliada": int((pedido["Origem recomendada"] == "Busca ampliada").sum()) if not pedido.empty else 0,
        "por_fornecedor": por_fornecedor,
        "motivos_pendencia": motivos,
    }

    return ResultadoMotor(
        id_carga=id_carga,
        pedido=pedido,
        opcoes=opcoes,
        pendencias=pendencias_df,
        historico=historico_atualizado,
        ofertas_tratadas=pd.DataFrame(),
        resumo=resumo,
        diagnostico=diagnostico,
    )
