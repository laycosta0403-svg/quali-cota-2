from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from src.demo_data import compra_distribuidor_demo, kpis_demo, variacoes_demo


st.title("📊 Dashboard")
st.caption("Painel gerencial da última rodada válida do Quali Cota.")

resultado = st.session_state.get("qc_resultado")

if resultado is None:
    st.info("Ainda não há uma rodada processada nesta sessão. Abaixo estão dados demonstrativos.")
    kpis = kpis_demo()
    por_fornecedor = compra_distribuidor_demo().rename(columns={"Distribuidor": "Fornecedor recomendado", "Valor": "Valor total"})
    altas, baixas = variacoes_demo()
    processado_em = "20/07/2026 11:30"
else:
    kpis = {
        "valor_total": resultado.resumo["valor_total"],
        "skus_pedido": resultado.resumo["skus_pedido"],
        "pendencias": resultado.resumo["pendencias"],
        "sem_cotacao": resultado.resumo["sem_oferta"],
        "distribuidores": resultado.resumo["fornecedores"],
    }
    por_fornecedor = resultado.resumo["por_fornecedor"]
    processado_em = resultado.resumo["processado_em"].strftime("%d/%m/%Y %H:%M")
    pedido = resultado.pedido.copy()
    pedido["Variação"] = pd.to_numeric(pedido.get("Variação 1"), errors="coerce") * 100
    pedido["Descrição"] = pedido.get("Descrição", "")
    pedido["SKU"] = pedido.get("SKU", "")
    altas = pedido.nlargest(5, "Variação")[["SKU", "Descrição", "Variação"]].dropna()
    baixas = pedido.nsmallest(5, "Variação")[["SKU", "Descrição", "Variação"]].dropna()

st.markdown("### Última rodada")
st.markdown(
    f'''
    <div class="qc-card">
        <strong>Processado em:</strong> {processado_em} &nbsp;•&nbsp;
        <strong>Status:</strong> Última rodada válida
    </div>
    ''',
    unsafe_allow_html=True,
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Valor da compra", f"R$ {kpis['valor_total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
c2.metric("SKUs no pedido", f"{int(kpis['skus_pedido']):,}".replace(",", "."))
c3.metric("Pendências", f"{int(kpis['pendencias']):,}".replace(",", "."))
c4.metric("Sem oferta", f"{int(kpis['sem_cotacao']):,}".replace(",", "."))
c5.metric("Fornecedores", int(kpis["distribuidores"]))

st.markdown("### Alertas da rodada")
a1, a2, a3 = st.columns(3)
if resultado is None:
    a1.warning("12 SKUs subiram mais de 15%.")
    a2.error("416 itens exigem correção antes do pedido.")
    a3.info("Santa Cruz concentra 33% do valor sugerido.")
else:
    aumentos = int((pd.to_numeric(resultado.pedido.get("Variação 1"), errors="coerce") > 0.15).sum())
    a1.warning(f"{aumentos} SKUs subiram mais de 15%.")
    a2.error(f"{resultado.resumo['pendencias']} pendências registradas.")
    top = por_fornecedor.iloc[0] if not por_fornecedor.empty else None
    if top is not None and resultado.resumo["valor_total"]:
        participacao = float(top["Valor total"]) / float(resultado.resumo["valor_total"]) * 100
        a3.info(f"{top['Fornecedor recomendado']} concentra {participacao:.1f}% do valor sugerido.")
    else:
        a3.info("Nenhum fornecedor consolidado nesta rodada.")

st.markdown("### Compra por fornecedor")
if por_fornecedor.empty:
    st.info("Nenhum item entrou no pedido.")
else:
    df_dist = por_fornecedor.sort_values("Valor total", ascending=True)
    fig = px.bar(df_dist, x="Valor total", y="Fornecedor recomendado", orientation="h", text_auto=".2s")
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

if not altas.empty or not baixas.empty:
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("### Maiores aumentos")
        if altas.empty:
            st.info("Sem aumentos calculados.")
        else:
            fig_altas = px.bar(altas.sort_values("Variação"), x="Variação", y="Descrição", orientation="h", hover_data=["SKU"])
            fig_altas.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_altas, use_container_width=True)
    with g2:
        st.markdown("### Maiores reduções")
        if baixas.empty:
            st.info("Sem reduções calculadas.")
        else:
            fig_baixas = px.bar(baixas.sort_values("Variação", ascending=False), x="Variação", y="Descrição", orientation="h", hover_data=["SKU"])
            fig_baixas.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_baixas, use_container_width=True)
