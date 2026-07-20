from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.exportacao import dataframe_para_excel, gerar_pedido_unificado, gerar_resumo_excel
from src.processamento import processar_arquivos


st.title("⚙️ Processamento de Dados")
st.caption("Execute o motor e gere os quatro outputs oficiais da rodada.")

st.info(
    "A integração automática com o SharePoint continua pausada aguardando o TI. "
    "Nesta etapa, os arquivos são enviados manualmente apenas para validar o motor."
)

st.markdown("### 1. Arquivos da rodada")
cotacoes = st.file_uploader(
    "Cotação(ões)",
    type=["xlsx", "xlsb", "csv"],
    accept_multiple_files=True,
    help="É possível enviar uma ou várias cotações na mesma rodada.",
)
necessidade = st.file_uploader(
    "Necessidade de compra",
    type=["xlsx", "xlsb", "csv"],
    accept_multiple_files=False,
)

with st.expander("Bases técnicas do motor", expanded=False):
    st.caption("Essas bases alimentam o motor, mas não viram etapas extras para o usuário.")
    cadastro = st.file_uploader("Cadastro EAN/SKU", type=["xlsx", "xlsb", "csv"], key="cadastro")
    regras = st.file_uploader("Regras de fornecedor", type=["xlsx", "xlsb", "csv"], key="regras")
    homologacao = st.file_uploader(
        "Homologação OL — opcional", type=["xlsx", "xlsb", "csv"], key="homologacao"
    )
    historico_anterior = st.file_uploader(
        "Histórico anterior — opcional", type=["xlsx", "xlsb", "csv"], key="historico"
    )
    desativados_texto = st.text_area(
        "Fornecedores desativados somente nesta rodada — opcional",
        placeholder="Um nome por linha",
        height=90,
    )

pronto = bool(cotacoes) and necessidade is not None and cadastro is not None and regras is not None

st.markdown("### 2. Processar")
if st.button("⚙️ Processar motor", type="primary", use_container_width=True, disabled=not pronto):
    desativados = [linha.strip() for linha in desativados_texto.splitlines() if linha.strip()]
    etapas = [
        "Lendo os arquivos",
        "Validando EANs e fornecedores",
        "Classificando as quatro melhores opções",
        "Gerando pedido, pendências, histórico e resumo",
    ]
    barra = st.progress(0)
    status = st.empty()
    try:
        for indice, etapa in enumerate(etapas[:-1], start=1):
            status.write(f"**{etapa}...**")
            barra.progress(indice / len(etapas))

        resultado = processar_arquivos(
            cotacoes=cotacoes,
            necessidade=necessidade,
            cadastro=cadastro,
            regras=regras,
            homologacao=homologacao,
            historico=historico_anterior,
            fornecedores_desativados=desativados,
        )
        status.write(f"**{etapas[-1]}...**")
        barra.progress(1.0)
        st.session_state["qc_resultado"] = resultado
        status.success("Rodada processada com sucesso.")
        st.toast("Dashboard e Busca atualizados.", icon="✅")
    except Exception as exc:
        status.error(f"Não foi possível concluir o processamento: {exc}")
        st.exception(exc)

if not pronto:
    st.caption("Envie cotação, necessidade, cadastro EAN/SKU e regras de fornecedor para habilitar o motor.")

resultado = st.session_state.get("qc_resultado")
if resultado is not None:
    st.divider()
    st.markdown("### 3. Resultado da rodada")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("SKUs no pedido", resultado.resumo["skus_pedido"])
    r2.metric("Pendências", resultado.resumo["pendencias"])
    r3.metric("Fornecedores", resultado.resumo["fornecedores"])
    r4.metric("Busca ampliada", resultado.resumo["busca_ampliada"])

    aba_pedido, aba_pendencias, aba_historico, aba_resumo = st.tabs(
        ["Pedido unificado", "Pendências", "Histórico", "Resumo"]
    )

    with aba_pedido:
        st.caption("Prévia do fornecedor recomendado. As quatro opções completas ficam na aba Estoques_Fornecedores do Excel.")
        colunas = [
            "SKU", "EAN", "Descrição", "Quantidade Solicitada", "Fornecedor recomendado",
            "Preço recomendado", "Estoque recomendado", "Origem recomendada", "Status motor",
        ]
        st.dataframe(resultado.pedido.reindex(columns=colunas), use_container_width=True, hide_index=True)

    with aba_pendencias:
        st.dataframe(resultado.pendencias, use_container_width=True, hide_index=True)

    with aba_historico:
        st.dataframe(resultado.historico.tail(500), use_container_width=True, hide_index=True)

    with aba_resumo:
        st.dataframe(resultado.resumo["por_fornecedor"], use_container_width=True, hide_index=True)
        st.dataframe(resultado.resumo["motivos_pendencia"], use_container_width=True, hide_index=True)

    template = Path(__file__).resolve().parents[1] / "templates" / "Modelo Envio Pedidos Fornecedor_Medicamentos.xlsx"
    pedido_bytes = gerar_pedido_unificado(resultado, template)
    pendencias_bytes = dataframe_para_excel({"PENDENCIAS": resultado.pendencias})
    historico_bytes = dataframe_para_excel({"HISTORICO_COTACAO": resultado.historico})
    resumo_bytes = gerar_resumo_excel(resultado)

    st.markdown("### 4. Downloads")
    d1, d2, d3, d4 = st.columns(4)
    d1.download_button(
        "⬇️ Pedido unificado",
        data=pedido_bytes,
        file_name="Pedido_Unificado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    d2.download_button(
        "⬇️ Pendências",
        data=pendencias_bytes,
        file_name="Pendencias.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    d3.download_button(
        "⬇️ Histórico",
        data=historico_bytes,
        file_name="Historico_Cotacao.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    d4.download_button(
        "⬇️ Resumo",
        data=resumo_bytes,
        file_name="Resumo_Rodada.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
