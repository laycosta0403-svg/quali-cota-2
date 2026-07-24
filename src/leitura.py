from __future__ import annotations

import io
import math
import re
import unicodedata
from pathlib import Path
from typing import BinaryIO, Iterable, Mapping, Sequence

import pandas as pd


Source = str | Path | BinaryIO | io.BytesIO


def normalizar_texto(valor: object) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = texto.lower().replace("\xa0", " ")
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def texto_codigo(valor: object) -> str:
    if valor is None or pd.isna(valor):
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    texto = str(valor).strip()
    if re.fullmatch(r"\d+\.0", texto):
        texto = texto[:-2]
    return texto


def numero(valor: object, padrao: float = 0.0) -> float:
    if valor is None or pd.isna(valor):
        return padrao
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if not texto:
        return padrao
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return padrao


def booleano_sim(valor: object) -> bool:
    return normalizar_texto(valor) in {"sim", "s", "yes", "y", "true", "1", "ativo", "ok"}


def _nome_arquivo(source: Source) -> str:
    if isinstance(source, (str, Path)):
        return str(source)
    return getattr(source, "name", "arquivo.xlsx")


def _preparar_source(source: Source) -> Source:
    if hasattr(source, "seek"):
        source.seek(0)
    return source



def _engine_excel(nome: str) -> str:
    if not nome.endswith(".xlsb"):
        return "openpyxl"
    try:
        import python_calamine  # noqa: F401
        return "calamine"
    except ImportError:
        return "pyxlsb"


def listar_abas(source: Source) -> list[str]:
    nome = _nome_arquivo(source).lower()
    if nome.endswith(".csv"):
        return ["CSV"]
    engine = _engine_excel(nome)
    source = _preparar_source(source)
    return pd.ExcelFile(source, engine=engine).sheet_names


def ler_bruto(source: Source, sheet_name: str | int | None = None) -> pd.DataFrame:
    nome = _nome_arquivo(source).lower()
    source = _preparar_source(source)
    if nome.endswith(".csv"):
        return pd.read_csv(source, header=None, dtype=object, sep=None, engine="python")
    engine = _engine_excel(nome)
    return pd.read_excel(source, sheet_name=sheet_name or 0, header=None, dtype=object, engine=engine)


def detectar_cabecalho(df: pd.DataFrame, aliases: Mapping[str, Sequence[str]], limite: int = 80) -> int:
    alias_norm = {
        normalizar_texto(alias)
        for opcoes in aliases.values()
        for alias in opcoes
    }
    melhor_linha = 0
    melhor_score = -1
    for idx in range(min(limite, len(df))):
        valores = {normalizar_texto(v) for v in df.iloc[idx].tolist() if normalizar_texto(v)}
        score = len(valores & alias_norm)
        if score > melhor_score:
            melhor_linha, melhor_score = idx, score
    if melhor_score < 2:
        raise ValueError("Não foi possível identificar a linha de cabeçalho do arquivo.")
    return melhor_linha


def _mapear_colunas(colunas: Iterable[object], aliases: Mapping[str, Sequence[str]]) -> dict[object, str]:
    normalizadas = {coluna: normalizar_texto(coluna) for coluna in colunas}
    resultado: dict[object, str] = {}
    colunas_usadas: set[object] = set()
    for destino, opcoes in aliases.items():
        candidatos = [normalizar_texto(opcao) for opcao in opcoes]
        escolhido = None

        # Respeita a ordem dos aliases. Isso é importante quando existem, por
        # exemplo, "EAN" e "EAN DE COMPR." na mesma aba: o alias mais específico
        # deve vencer, independentemente da posição física da coluna.
        for candidato in candidatos:
            for coluna, norm in normalizadas.items():
                if coluna not in colunas_usadas and norm == candidato:
                    escolhido = coluna
                    break
            if escolhido is not None:
                break

        if escolhido is None:
            # Fuzzy apenas para aliases com pelo menos duas palavras, evitando que
            # "Fornecedor" seja confundido com "Código fornecedor".
            candidatos_longos = [c for c in candidatos if len(c.split()) >= 2]
            for candidato in candidatos_longos:
                for coluna, norm in normalizadas.items():
                    if coluna in colunas_usadas:
                        continue
                    if candidato and (candidato in norm or norm in candidato):
                        escolhido = coluna
                        break
                if escolhido is not None:
                    break
        if escolhido is not None:
            resultado[escolhido] = destino
            colunas_usadas.add(escolhido)
    return resultado


def ler_tabela(
    source: Source,
    aliases: Mapping[str, Sequence[str]],
    abas_preferidas: Sequence[str] = (),
    aba_obrigatoria: str | None = None,
    exigir_colunas: Sequence[str] = (),
) -> pd.DataFrame:
    nome = _nome_arquivo(source).lower()
    if nome.endswith(".csv"):
        abas = ["CSV"]
    else:
        abas = listar_abas(source)

    if aba_obrigatoria and abas != ["CSV"]:
        alvo = normalizar_texto(aba_obrigatoria)
        correspondentes = [aba for aba in abas if alvo in normalizar_texto(aba)]
        if not correspondentes:
            raise ValueError(
                f'A aba obrigatória contendo "{aba_obrigatoria}" não foi encontrada. '
                f'Abas disponíveis: {", ".join(abas)}'
            )
        ordenadas = correspondentes
    else:
        ordenadas: list[str] = []
        for preferida in abas_preferidas:
            preferida_norm = normalizar_texto(preferida)
            ordenadas.extend([aba for aba in abas if preferida_norm in normalizar_texto(aba)])
        ordenadas.extend([aba for aba in abas if aba not in ordenadas])

    melhor: tuple[int, pd.DataFrame, str, int, set[str]] | None = None
    ultimo_erro: Exception | None = None
    for aba in ordenadas:
        try:
            bruto = ler_bruto(source, None if aba == "CSV" else aba)
            header = detectar_cabecalho(bruto, aliases)
            colunas = bruto.iloc[header].tolist()
            dados = bruto.iloc[header + 1 :].copy()
            dados.columns = colunas
            dados = dados.dropna(how="all").reset_index(drop=True)
            mapa = _mapear_colunas(dados.columns, aliases)
            dados = dados.rename(columns=mapa)
            reconhecidas_set = set(mapa.values())
            reconhecidas = len(reconhecidas_set)
            if melhor is None or reconhecidas > melhor[0]:
                melhor = (reconhecidas, dados, aba, header, reconhecidas_set)
        except Exception as exc:  # pragma: no cover - tenta outras abas
            ultimo_erro = exc

    if melhor is None:
        raise ValueError(f"Não foi possível ler o arquivo: {ultimo_erro}")

    _, dados, aba_lida, header, reconhecidas_set = melhor
    faltantes = [coluna for coluna in exigir_colunas if coluna not in reconhecidas_set]
    if faltantes:
        raise ValueError(
            f'A aba "{aba_lida}" foi encontrada, mas faltam colunas obrigatórias: '
            f'{", ".join(faltantes)}.'
        )
    dados.attrs["aba_lida"] = aba_lida
    dados.attrs["linha_cabecalho"] = header + 1
    dados.attrs["colunas_reconhecidas"] = sorted(reconhecidas_set)
    return dados


def dividir_eans(valor: object) -> list[str]:
    texto = texto_codigo(valor)
    if not texto:
        return []
    partes = re.split(r"\s*(?:/|;|\||\n|,)\s*", texto)
    return [re.sub(r"\D", "", parte) for parte in partes if re.sub(r"\D", "", parte)]


ALIASES_COTACAO = {
    "data_carga": ["Data da carga", "Data carga"],
    "id_carga": ["ID da carga", "Id carga", "Número cotação", "NR COTAÇÃO"],
    "fornecedor": ["Fornecedor", "Distribuidor"],
    "codigo_fornecedor": ["Código fornecedor", "Cod fornecedor", "Código do fornecedor"],
    "tipo_operacao": ["Tipo operação", "Tipo de operação"],
    "como_comprar": ["Como comprar"],
    "observacao_regra": ["Observação"],
    "ol_industria": ["OL / Indústria", "OL", "Indústria"],
    "ean": ["Código de Barras", "EAN", "Código barras"],
    "descricao_recebida": ["Produto", "Descrição", "Descrição produto"],
    "desconto": ["Desc", "Desconto"],
    "preco_fabrica": ["PF", "Preço fábrica", "Preço Fábrica"],
    "preco_final": ["Valor Líquido", "Preço Final", "Valor liquido", "Preço líquido"],
    "tipo_preco": ["Tipo preço", "Tipo de preço"],
    "embalagem": ["Embalagem", "Caixaria"],
    "multiplo": ["Múltiplo Compra", "Múltiplo", "Multiplo compra"],
    "estoque_fornecedor": ["Saldo", "Estoque", "Estoque fornecedor"],
}

ALIASES_NECESSIDADE = {
    "data_necessidade": ["Data da necessidade", "Data necessidade"],
    "sku": ["CÓD", "COD", "SKU", "Código produto", "Código interno", "Código"],
    "ean": ["EAN DE COMPR.", "EAN DE COMPRA", "EAN compra", "EAN", "Código de barras"],
    "descricao": ["Descrição", "Produto", "Nome"],
    "quantidade_solicitada": [
        "Pedido Efetivo", "Quantidade solicitada", "Qtd.Solic", "Qtd solicitada", "Necessidade"
    ],
    "curva": ["Curva"],
    "ruptura": ["Ruptura?", "Ruptura"],
    "ruptura_cronica": ["Ruptura crônica?", "Ruptura crônica", "Ruptura Cronico", "Ruptura"],
    "vmd": ["VMD Final", "VMD", "Venda média diária"],
    "dde": ["DDE Atual", "DDE"],
    "estoque_atual": ["Estoque atual", "Estoque"],
    "pmz": ["PMZ"],
    "ultimo_custo": ["Último custo", "Ultimo custo", "Custo"],
    "categoria": ["Categoria"],
    "fabricante": ["Fabricante"],
    "comprador": ["Comprador"],
    "caixaria": ["CAIXARIA", "Caixaria", "Múltiplo", "Multiplo"],
}

ALIASES_CADASTRO = {
    "ean_compra": ["EAN compra", "EAN de compra"],
    "ean_venda": ["EAN venda", "EAN de venda", "EAN"],
    "sku": ["SKU", "Código interno"],
    "descricao_oficial": ["Descrição oficial", "Descrição", "Produto"],
    "fabricante": ["Fabricante"],
    "categoria": ["Categoria"],
    "caixaria_padrao": ["Caixaria padrão", "Caixaria", "Embalagem"],
    "multiplo_padrao": ["Múltiplo padrão", "Múltiplo"],
    "status_ean": ["Status EAN", "Status"],
}

ALIASES_REGRAS = {
    "fornecedor": ["Fornecedor", "Distribuidor"],
    "codigo_fornecedor": ["Código fornecedor", "Cod fornecedor", "Código"],
    "tipo_operacao": ["Tipo operação", "Tipo de operação"],
    "como_comprar": ["Como comprar"],
    "observacao_regra": ["Observação"],
    "ativo": ["Ativo?", "Ativo"],
    "bloqueado": ["Bloqueado?", "Bloqueado"],
    "participa_cotacao": ["Participa da cotação por padrão?", "Participa cotação"],
    "participa_busca": ["Participa da busca ampliada?", "Participa busca ampliada"],
    "minimo_faturamento": ["Mínimo de faturamento", "Minimo faturamento"],
    "prazo_pagamento": ["Prazo pagamento", "Condição pagamento"],
    "lead_time": ["Lead time", "Prazo entrega"],
    "email": ["E-Mail", "Email", "Email contato"],
}

ALIASES_HOMOLOGACAO = {
    "ol_industria": ["OL / Indústria", "OL", "Indústria", "Fornecedor"],
    "fornecedor": ["Distribuidor", "Distribuidores homologados (OL)"],
    "tipo_operacao": ["Tipo operação", "Tem OL/Direto?"],
    "ativo": ["Ativo?", "Ativo"],
    "prioridade": ["Prioridade"],
}

ALIASES_HISTORICO = {
    "data_processamento": ["Data processamento"],
    "data_carga": ["Data da carga"],
    "id_carga": ["ID da carga"],
    "fornecedor": ["Fornecedor da cotação", "Fornecedor"],
    "codigo_fornecedor": ["Código fornecedor", "Cod fornecedor"],
    "tipo_operacao": ["Tipo operação"],
    "ol_industria": ["OL / Indústria"],
    "sku": ["SKU identificado", "SKU"],
    "ean": ["EAN tratado", "EAN"],
    "ean_original": ["EAN original"],
    "descricao_recebida": ["Descrição recebida"],
    "descricao_oficial": ["Descrição oficial"],
    "fabricante": ["Fabricante"],
    "categoria": ["Categoria"],
    "preco_fabrica": ["Preço Fábrica"],
    "desconto": ["Desconto"],
    "preco_final": ["Preço Final"],
    "tipo_preco": ["Tipo preço"],
    "caixaria": ["Caixaria final", "Caixaria"],
    "multiplo": ["Múltiplo"],
    "estoque_fornecedor": ["Estoque fornecedor"],
    "preco_unitario": ["Preço unitário", "Preço comparável"],
    "status_ean": ["Status EAN"],
    "status_fornecedor": ["Status fornecedor"],
    "status_homologacao": ["Status homologação OL"],
    "observacao_sistema": ["Observação sistema"],
}
