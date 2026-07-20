import streamlit as st


def aplicar_estilo() -> None:
    """Aplica ajustes visuais compatíveis com os temas claro e escuro."""

    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1400px;
        }

        [data-testid="stMetric"] {
            background-color: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 14px;
            padding: 14px 16px;
            box-shadow: 0 3px 12px rgba(15, 23, 42, 0.08);
        }

        [data-testid="stMetricLabel"],
        [data-testid="stMetricValue"],
        [data-testid="stMetricDelta"] {
            color: var(--text-color);
        }

        .qc-card {
            background-color: var(--secondary-background-color);
            color: var(--text-color);
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 14px;
            padding: 18px;
            margin-bottom: 12px;
            box-shadow: 0 3px 12px rgba(15, 23, 42, 0.06);
        }

        .qc-card strong {
            color: var(--text-color);
        }

        .qc-muted {
            color: rgba(128, 128, 128, 0.95);
            font-size: 0.95rem;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-top: 1rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
