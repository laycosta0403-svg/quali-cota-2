from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.demo_data import compra_distribuidor_demo, kpis_demo, variacoes_demo
from src.persistencia import carregar_metadata, carregar_tabela, obter_ultimo_id
from src.tempo import FUSO_BRASIL


st.title("📊 Dashboard")
st.caption("Painel gerencial da última rodada válida do Quali Cota.")

id_carga = st.session_state.get("qc_id_carga") or obter_ultimo_id()
metadata = carregar_metadata(id_carga)

if metadata is None:
    st.info("Ainda não há uma rodada salva. Abaixo estão dados demonstrativos.")
    kpis = kpis_demo()
    por_fornecedor = compra_distribuidor_demo().rename(columns={"Distribuidor": "Fornecedor recomendado", "Valor": "Valor total"})
    altas, baixas = variacoes_demo()
    processado_em = "20/07/2026 11:30"
    resultado_real = False
else:
    resumo = metadata.get("resumo", {})
    kpis = {
        "valor_total": float(resumo.get("valor_total", 0) or 0),
        "skus_pedido": int(resumo.get("skus_pedido", 0) or 0),
        "pendencias": int(resumo.get("pendencias", 0) or 0),
        "sem_cotacao": int(resumo.get("sem_oferta", 0) or 0),
        "distribuidores": int(resumo.get("fornecedores", 0) or 0),
    }
    por_fornecedor = carregar_tabela("por_fornecedor", str(metadata["id_carga"]))
    processado_em_raw = resumo.get("processado_em")
    if processado_em_raw:
        timestamp = pd.Timestamp(processado_em_raw)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC").tz_convert(FUSO_BRASIL)
        else:
            timestamp = timestamp.tz_convert(FUSO_BRASIL)
        processado_em = timestamp.strftime("%d/%m/%Y %H:%M")
    else:
        processado_em = "—"
    pedido = carregar_tabela("pedido", str(metadata["id_carga"]))
    pedido["Variação"] = pd.to_numeric(pedido.get("Variação 1"), errors="coerce") * 100
    pedido["Descrição"] = pedido.get("Descrição", "")
    pedido["SKU"] = pedido.get("SKU", "")
    altas = pedido.nlargest(5, "Variação")[["SKU", "Descrição", "Variação"]].dropna()
    baixas = pedido.nsmallest(5, "Variação")[["SKU", "Descrição", "Variação"]].dropna()
    resultado_real = True

st.markdown("### Última rodada")
st.markdown(
    f'''
    <div class="qc-card">
        <strong>Processado em:</strong> {processado_em} &nbsp;•&nbsp;
        <strong>Status:</strong> Última rodada válida
        {f'&nbsp;•&nbsp; <strong>ID:</strong> {metadata["id_carga"]}' if metadata else ''}
    </div>
    ''',
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns(3)
c4, c5 = st.columns(2)
valor_total = float(kpis["valor_total"])
valor_exibido = f"R$ {valor_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
c1.metric("Valor da compra", valor_exibido)
c2.metric("SKUs no pedido", f"{int(kpis['skus_pedido']):,}".replace(",", "."))
c3.metric("Pendências", f"{int(kpis['pendencias']):,}".replace(",", "."))
c4.metric("Sem oferta", f"{int(kpis['sem_cotacao']):,}".replace(",", "."))
c5.metric("Fornecedores", int(kpis["distribuidores"]))

st.markdown("### Alertas da rodada")
a1, a2, a3 = st.columns(3)
if not resultado_real:
    a1.warning("12 SKUs subiram mais de 15%.")
    a2.error("416 itens exigem correção antes do pedido.")
    a3.info("Santa Cruz concentra 33% do valor sugerido.")
else:
    aumentos = int((pd.to_numeric(pedido.get("Variação 1"), errors="coerce") > 0.15).sum())
    a1.warning(f"{aumentos} SKUs subiram mais de 15%.")
    a2.error(f"{kpis['pendencias']} pendências registradas.")
    top = por_fornecedor.iloc[0] if not por_fornecedor.empty else None
    if top is not None and kpis["valor_total"]:
        participacao = float(top["Valor total"]) / float(kpis["valor_total"]) * 100
        a3.info(f"{top['Fornecedor recomendado']} concentra {participacao:.1f}% do valor sugerido.")
    else:
        a3.info("Nenhum fornecedor consolidado nesta rodada.")

st.markdown("### Compra por fornecedor")
if por_fornecedor.empty:
    st.info("Nenhum item entrou no pedido.")
else:
    df_dist = por_fornecedor.sort_values("Valor total", ascending=True).copy()
    fig = px.bar(
        df_dist, x="Valor total", y="Fornecedor recomendado", orientation="h",
        text="Valor total", hover_name="Fornecedor recomendado",
        hover_data={"Fornecedor recomendado": False, "Valor total": ":,.2f"},
    )
    fig.update_traces(texttemplate="R$ %{x:,.0f}", textposition="outside", cliponaxis=False)
    fig.update_yaxes(categoryorder="array", categoryarray=df_dist["Fornecedor recomendado"].tolist())
    fig.update_layout(height=max(360, 28 * len(df_dist) + 100), margin=dict(l=10, r=80, t=10, b=10))
    st.plotly_chart(fig, width="stretch")
    with st.expander("Ver valores por fornecedor"):
        st.dataframe(df_dist.sort_values("Valor total", ascending=False), width="stretch", hide_index=True)

if not altas.empty or not baixas.empty:
    st.markdown("### Maiores variações de custo")
    variacoes = pd.concat([
        altas.assign(Movimento="Aumento"),
        baixas.assign(Movimento="Redução"),
    ], ignore_index=True)
    variacoes["Variação"] = variacoes["Variação"].map(lambda v: f"{v:,.2f}%".replace(",", "X").replace(".", ",").replace("X", "."))
    st.dataframe(variacoes[["Movimento", "SKU", "Descrição", "Variação"]], width="stretch", hide_index=True)
