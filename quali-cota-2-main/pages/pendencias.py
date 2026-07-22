from __future__ import annotations

import pandas as pd
import streamlit as st

from src.persistencia import (
    carregar_tabela, obter_ultimo_id, salvar_auditoria_pendencias, salvar_tabela,
)
from src.tempo import agora_brasil_sem_fuso

st.set_page_config(page_title="Tratar pendências · Quali Cota", layout="wide")
st.title("Tratamento de pendências")
st.caption("Filtre, selecione e trate em massa dentro do app. Nenhum download ou upload é necessário.")

id_carga = st.session_state.get("qc_id_carga") or obter_ultimo_id()
if not id_carga:
    st.info("Processe uma rodada primeiro.")
    st.stop()

pend = carregar_tabela("pendencias", id_carga)
pedido = carregar_tabela("pedido", id_carga)
if pend.empty:
    st.success("Não há pendências nesta rodada.")
    st.stop()

for col, default in {
    "Selecionar": False,
    "Status tratamento": "Pendente",
    "Tratativa corrigida": "",
    "Fornecedor corrigido": "",
    "Observação tratamento": "",
    "Escopo": "Somente esta rodada",
}.items():
    if col not in pend.columns:
        pend[col] = default

f1, f2, f3 = st.columns(3)
motivos = sorted(str(v) for v in pend["Pendência"].dropna().unique())
fornecedores = sorted(str(v) for v in pend.get("Fornecedor", pd.Series(dtype=str)).dropna().unique() if str(v))
filtro_motivo = f1.multiselect("Pendência", motivos)
filtro_fornecedor = f2.multiselect("Fornecedor", fornecedores)
busca = f3.text_input("Buscar SKU, EAN ou descrição")

mask = pd.Series(True, index=pend.index)
if filtro_motivo:
    mask &= pend["Pendência"].astype(str).isin(filtro_motivo)
if filtro_fornecedor:
    mask &= pend["Fornecedor"].astype(str).isin(filtro_fornecedor)
if busca.strip():
    texto = busca.strip().casefold()
    mask &= pend[[c for c in ["SKU", "EAN", "Descrição"] if c in pend.columns]].astype(str).apply(
        lambda row: row.str.casefold().str.contains(texto, regex=False).any(), axis=1
    )

filtrada = pend.loc[mask].copy()
a1, a2 = st.columns([1, 4])
if a1.button("Selecionar filtradas", width="stretch"):
    pend.loc[mask, "Selecionar"] = True
    st.session_state["qc_pendencias_edit"] = pend
if a2.button("Limpar seleção", width="content"):
    pend["Selecionar"] = False
    st.session_state["qc_pendencias_edit"] = pend

base_editor = st.session_state.get("qc_pendencias_edit", pend)
filtrada = base_editor.loc[mask].copy()
edited = st.data_editor(
    filtrada,
    width="stretch",
    hide_index=True,
    disabled=[c for c in filtrada.columns if c not in {"Selecionar", "Observação tratamento"}],
    column_config={"Selecionar": st.column_config.CheckboxColumn(required=True)},
    key="editor_pendencias",
)
base_editor.loc[edited.index, edited.columns] = edited
st.session_state["qc_pendencias_edit"] = base_editor

st.subheader("Ação em massa")
c1, c2, c3, c4 = st.columns(4)
tratativa = c1.selectbox("Tratativa", ["Não alterar", "OL", "Direto", "Distribuidor", "Indústria"])
fornecedor = c2.text_input("Fornecedor correto")
status = c3.selectbox("Status", ["Corrigido", "Ignorar nesta rodada", "Pendente"])
escopo = c4.selectbox("Escopo", ["Somente esta rodada", "Próximas rodadas também"])
observacao = st.text_input("Observação da correção")

selecionadas = base_editor[base_editor["Selecionar"].fillna(False).astype(bool)]
st.caption(f"{len(selecionadas)} pendência(s) selecionada(s).")

if st.button("Aplicar correção em massa", type="primary", disabled=selecionadas.empty, width="stretch"):
    idx = selecionadas.index
    antes = base_editor.loc[idx].copy()
    base_editor.loc[idx, "Status tratamento"] = status
    base_editor.loc[idx, "Escopo"] = escopo
    base_editor.loc[idx, "Observação tratamento"] = observacao
    if tratativa != "Não alterar":
        base_editor.loc[idx, "Tratativa corrigida"] = tratativa
    if fornecedor.strip():
        base_editor.loc[idx, "Fornecedor corrigido"] = fornecedor.strip()

    # Atualiza linhas já existentes no Pedido; casos sem oferta continuam visíveis
    # até uma nova oferta ser informada em futura evolução do motor.
    for _, cor in base_editor.loc[idx].iterrows():
        sku, ean = str(cor.get("SKU", "")), str(cor.get("EAN", ""))
        m = pd.Series(True, index=pedido.index)
        if sku and "SKU" in pedido.columns:
            m &= pedido["SKU"].astype(str) == sku
        elif ean and "EAN" in pedido.columns:
            m &= pedido["EAN"].astype(str) == ean
        else:
            continue
        if tratativa != "Não alterar":
            for col in ["Tratativa", "Tipo Condição", "Tipo operação recomendado"]:
                if col in pedido.columns:
                    pedido.loc[m, col] = tratativa
        if fornecedor.strip():
            for col in ["Fornecedor recomendado", "Novo Fornecedor "]:
                if col in pedido.columns:
                    pedido.loc[m, col] = fornecedor.strip()
        if status == "Corrigido" and "Status motor" in pedido.columns:
            pedido.loc[m, "Status motor"] = "Corrigido no app"

    auditoria = antes[[c for c in ["ID da carga", "SKU", "EAN", "Pendência", "Fornecedor"] if c in antes.columns]].copy()
    auditoria["Tratativa nova"] = tratativa
    auditoria["Fornecedor novo"] = fornecedor.strip()
    auditoria["Status novo"] = status
    auditoria["Escopo"] = escopo
    auditoria["Observação"] = observacao
    auditoria["Tratado em"] = agora_brasil_sem_fuso()
    salvar_tabela("pendencias", base_editor, id_carga)
    salvar_tabela("pedido", pedido, id_carga)
    salvar_auditoria_pendencias(id_carga, auditoria)
    st.session_state["qc_pendencias_edit"] = base_editor
    st.success("Correções salvas. Pedido e pendências foram atualizados sem baixar planilhas.")
    st.rerun()
