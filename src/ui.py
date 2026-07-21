import streamlit as st


def aplicar_estilo() -> None:
    st.markdown(
        '''
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1400px;
        }
        [data-testid="stMetric"] {
            background: var(--secondary-background-color);
            color: var(--text-color);
            border: 1px solid rgba(128, 128, 128, 0.28);
            border-radius: 14px;
            padding: 14px 16px;
            box-shadow: 0 3px 12px rgba(15, 23, 42, 0.08);
        }
        [data-testid="stMetric"] label,
        [data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: var(--text-color) !important;
        }
        .qc-card {
            background: var(--secondary-background-color);
            color: var(--text-color);
            border: 1px solid rgba(128, 128, 128, 0.28);
            border-radius: 14px;
            padding: 18px;
            margin-bottom: 12px;
        }
        </style>
        ''',
        unsafe_allow_html=True,
    )
