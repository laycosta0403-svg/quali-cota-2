import streamlit as st

st.title("⚙️ Processamento de Dados")
st.caption("Selecione os documentos da rodada e execute o motor.")

st.info(
    "Nesta primeira versão os seletores usam arquivos demonstrativos. "
    "A integração com o SharePoint será feita depois que validarmos a experiência."
)

st.markdown("### 1. Selecione a(s) cotação(ões) da rodada")
cotacoes = st.multiselect(
    "Cotações encontradas",
    options=[
        "Cotacao_Santa_Cruz_20-07.xlsx",
        "Cotacao_Panpharma_20-07.xlsx",
        "Cotacao_Profarma_20-07.xlsx",
        "Cotacao_Servimed_20-07.xlsx",
    ],
    placeholder="Selecione uma ou mais cotações",
)

st.markdown("### 2. Selecione a necessidade da rodada")
necessidade = st.selectbox(
    "Necessidades encontradas",
    options=[
        None,
        "Planejamento_20-07.xlsx",
        "Planejamento_19-07.xlsx",
        "Planejamento_18-07.xlsx",
    ],
    format_func=lambda item: "Selecione uma necessidade" if item is None else item,
)

st.markdown("### 3. Bases de governança ativas")
g1, g2, g3 = st.columns(3)
g1.success("✅ Cadastro EAN/SKU")
g2.success("✅ Regras de fornecedor")
g3.success("✅ Aliases e homologações")

pronto = bool(cotacoes) and necessidade is not None

st.markdown("### 4. Processar")
if st.button("⚙️ Processar motor", type="primary", use_container_width=True, disabled=not pronto):
    etapas = [
        "Lendo documentos",
        "Validando arquivos",
        "Consolidando cotações",
        "Executando motor",
        "Gerando MAPA, PEDIDO e PENDÊNCIAS",
        "Atualizando Dashboard, Busca e Histórico",
    ]
    progresso = st.progress(0)
    status = st.empty()

    for indice, etapa in enumerate(etapas, start=1):
        status.write(f"**{etapa}...**")
        progresso.progress(indice / len(etapas))

    status.success("Rodada demonstrativa processada com sucesso.")
    st.toast("Dashboard e consultas atualizados.", icon="✅")

if not pronto:
    st.caption("Selecione pelo menos uma cotação e uma necessidade para habilitar o motor.")
