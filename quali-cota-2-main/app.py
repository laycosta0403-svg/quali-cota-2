import streamlit as st

st.set_page_config(
    page_title="Quali Cota 2.0",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.ui import aplicar_estilo

aplicar_estilo()

paginas = {
    "Quali Cota": [
        st.Page("pages/dashboard.py", title="Dashboard", icon="📊", default=True),
        st.Page("pages/processamento.py", title="Processamento de Dados", icon="⚙️"),
        st.Page("pages/busca.py", title="Busca", icon="🔎"),
    ]
}

navegacao = st.navigation(paginas)
navegacao.run()
