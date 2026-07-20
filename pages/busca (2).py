import pandas as pd
import streamlit as st

st.title("🔎 Busca")
st.caption("Pesquise por SKU, EAN, descrição ou distribuidor em um único lugar.")

termo = st.text_input(
    "O que você quer consultar?",
    placeholder="Digite SKU, EAN, descrição ou fornecedor",
)

if not termo:
    st.info("Digite um termo para visualizar a cotação atual e o histórico.")
else:
    st.markdown(f"### Resultado para: `{termo}`")

    st.markdown("#### Resumo")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Ofertas encontradas", 8)
    r2.metric("Menor preço", "R$ 12,48")
    r3.metric("Preço médio", "R$ 13,22")
    r4.metric("Variação vs. anterior", "-4,6%")

    st.markdown("#### Cotação atual por distribuidor")
    atual = pd.DataFrame(
        {
            "Distribuidor": ["Santa Cruz", "Panpharma", "Profarma", "Servimed"],
            "Preço": [12.48, 12.71, 13.05, 13.14],
            "Estoque": [280, 190, 350, 80],
            "Status": ["Vencedor", "OK", "OK", "OK"],
        }
    )
    st.dataframe(atual, use_container_width=True, hide_index=True)

    st.markdown("#### Histórico recente")
    historico = pd.DataFrame(
        {
            "Data": ["20/07/2026", "19/07/2026", "18/07/2026", "17/07/2026"],
            "Menor preço": [12.48, 13.08, 12.95, 13.20],
            "Distribuidor vencedor": ["Santa Cruz", "Panpharma", "Santa Cruz", "Profarma"],
        }
    )
    st.dataframe(historico, use_container_width=True, hide_index=True)

    st.warning("Exemplo demonstrativo: os dados reais entrarão após o motor e o SharePoint.")
