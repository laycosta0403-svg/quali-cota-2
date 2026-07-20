import plotly.express as px
import streamlit as st

from src.demo_data import compra_distribuidor_demo, kpis_demo, variacoes_demo

st.title("📊 Dashboard")
st.caption("Painel gerencial da última rodada válida do Quali Cota.")

st.info("Dados demonstrativos nesta primeira versão. Depois conectaremos o motor e o SharePoint.")

st.markdown("### Última rodada")
st.markdown(
    '''
    <div class="qc-card">
        <strong>ID do motor:</strong> DEMO-2026-001 &nbsp;•&nbsp;
        <strong>Processado em:</strong> 20/07/2026 11:30 &nbsp;•&nbsp;
        <strong>Status:</strong> Última rodada válida
    </div>
    ''',
    unsafe_allow_html=True,
)

kpis = kpis_demo()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Valor da compra", f"R$ {kpis['valor_total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
c2.metric("SKUs no pedido", f"{kpis['skus_pedido']:,}".replace(",", "."))
c3.metric("Pendências", f"{kpis['pendencias']:,}".replace(",", "."))
c4.metric("Sem cotação", f"{kpis['sem_cotacao']:,}".replace(",", "."))
c5.metric("Distribuidores", kpis["distribuidores"])

st.markdown("### Alertas da rodada")
a1, a2, a3 = st.columns(3)
a1.warning("12 SKUs subiram mais de 15%.")
a2.error("416 itens exigem correção antes do pedido.")
a3.info("Santa Cruz concentra 33% do valor sugerido.")

st.markdown("### Compra por distribuidor")
df_dist = compra_distribuidor_demo().sort_values("Valor", ascending=True)
fig = px.bar(df_dist, x="Valor", y="Distribuidor", orientation="h", text_auto=".2s")
fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

altas, baixas = variacoes_demo()
g1, g2 = st.columns(2)

with g1:
    st.markdown("### Maiores aumentos")
    fig_altas = px.bar(
        altas.sort_values("Variação"),
        x="Variação",
        y="Descrição",
        orientation="h",
        hover_data=["SKU"],
    )
    fig_altas.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_altas, use_container_width=True)

with g2:
    st.markdown("### Maiores reduções")
    fig_baixas = px.bar(
        baixas.sort_values("Variação", ascending=False),
        x="Variação",
        y="Descrição",
        orientation="h",
        hover_data=["SKU"],
    )
    fig_baixas.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_baixas, use_container_width=True)
