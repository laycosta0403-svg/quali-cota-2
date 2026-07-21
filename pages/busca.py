from __future__ import annotations

import pandas as pd
import streamlit as st

from src.leitura import normalizar_texto
from src.persistencia import carregar_metadata, carregar_tabela, obter_ultimo_id


st.title("🔎 Busca")
st.caption("Pesquise por SKU, EAN, descrição ou fornecedor em um único lugar.")

id_carga = st.session_state.get("qc_id_carga") or obter_ultimo_id()
metadata = carregar_metadata(id_carga)
if metadata is None:
    st.info("Processe uma rodada para habilitar a busca real.")
    st.stop()

id_carga = str(metadata["id_carga"])
termo = st.text_input("O que você quer consultar?", placeholder="Digite SKU, EAN, descrição ou fornecedor")
if not termo:
    st.info(f"Última rodada disponível: {id_carga}. Digite um termo para pesquisar.")
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


pedido = filtrar(carregar_tabela("pedido", id_carga), ["SKU", "EAN", "Descrição", "Fornecedor recomendado"])
opcoes = filtrar(carregar_tabela("opcoes", id_carga), ["SKU", "Fornecedor 1", "Fornecedor 2", "Fornecedor 3", "Fornecedor 4"])
historico = filtrar(
    carregar_tabela("historico", id_carga),
    ["SKU identificado", "EAN tratado", "Descrição oficial", "Fornecedor"],
)

st.markdown(f"### Resultado para: `{termo}`")
r1, r2, r3 = st.columns(3)
r1.metric("Itens no pedido", len(pedido))
r2.metric("Linhas de opções", len(opcoes))
r3.metric("Registros no histórico", len(historico))

st.markdown("#### Pedido e recomendação")
st.dataframe(pedido, width="stretch", hide_index=True)

st.markdown("#### Quatro melhores opções")
st.dataframe(opcoes, width="stretch", hide_index=True)

st.markdown("#### Histórico")
st.dataframe(historico.tail(300), width="stretch", hide_index=True)
