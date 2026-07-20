from __future__ import annotations

import pandas as pd
import streamlit as st

from src.leitura import normalizar_texto


st.title("🔎 Busca")
st.caption("Pesquise por SKU, EAN, descrição ou fornecedor em um único lugar.")

resultado = st.session_state.get("qc_resultado")
if resultado is None:
    st.info("Processe uma rodada para habilitar a busca real.")
    st.stop()

termo = st.text_input("O que você quer consultar?", placeholder="Digite SKU, EAN, descrição ou fornecedor")
if not termo:
    st.info("Digite um termo para visualizar as opções atuais e o histórico.")
    st.stop()

termo_norm = normalizar_texto(termo)


def filtrar(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    mascara = pd.Series(False, index=df.index)
    for coluna in colunas:
        if coluna in df.columns:
            mascara |= df[coluna].astype(str).map(normalizar_texto).str.contains(termo_norm, na=False, regex=False)
    return df[mascara].copy()


pedido = filtrar(resultado.pedido, ["SKU", "EAN", "Descrição", "Fornecedor recomendado"])
opcoes = filtrar(resultado.opcoes, ["SKU", "Fornecedor 1", "Fornecedor 2", "Fornecedor 3", "Fornecedor 4"])
historico = filtrar(
    resultado.historico,
    ["SKU identificado", "EAN tratado", "Descrição oficial", "Fornecedor"],
)

st.markdown(f"### Resultado para: `{termo}`")
r1, r2, r3 = st.columns(3)
r1.metric("Itens no pedido", len(pedido))
r2.metric("Linhas de opções", len(opcoes))
r3.metric("Registros no histórico", len(historico))

st.markdown("#### Pedido e recomendação")
st.dataframe(pedido, use_container_width=True, hide_index=True)

st.markdown("#### Quatro melhores opções")
st.dataframe(opcoes, use_container_width=True, hide_index=True)

st.markdown("#### Histórico")
st.dataframe(historico.tail(300), use_container_width=True, hide_index=True)
