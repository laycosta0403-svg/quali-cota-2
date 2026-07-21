from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.exportacao import dataframe_para_excel, gerar_pedido_unificado, gerar_resumo_excel
from src.processamento import processar_arquivos


st.title("⚙️ Processamento de Dados")
st.caption("Execute o motor e gere os quatro outputs oficiais da rodada.")

st.info(
    "A integração automática com o SharePoint continua pausada aguardando o TI. "
    "Nesta etapa, os arquivos são enviados manualmente para validar o motor."
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
    help='O sistema usa obrigatoriamente a aba cujo nome contém "Volume de Compras".',
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
        "Lendo a aba Volume de Compras",
        "Validando Pedido Efetivo, EANs e fornecedores",
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
        st.session_state.pop("qc_download", None)
        status.success(f"Rodada processada com sucesso. ID da carga: {resultado.id_carga}")
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
    st.success(f"**ID da carga:** `{resultado.id_carga}`")

    diagnostico = resultado.diagnostico
    st.info(
        f'**Aba lida:** {diagnostico.get("aba_necessidade", "—")}  ·  '
        f'**SKUs com Pedido Efetivo:** {diagnostico.get("skus_com_pedido", 0):,}  ·  '
        f'**Unidades solicitadas:** {diagnostico.get("unidades_solicitadas", 0):,}  ·  '
        f'**Linhas da cotação:** {diagnostico.get("linhas_cotacao", 0):,}'
        .replace(",", ".")
    )

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("SKUs no pedido", resultado.resumo["skus_pedido"])
    r2.metric("Pendências", resultado.resumo["pendencias"])
    r3.metric("Fornecedores", resultado.resumo["fornecedores"])
    r4.metric("Busca ampliada", resultado.resumo["busca_ampliada"])

    aba_pedido, aba_pendencias, aba_historico, aba_resumo = st.tabs(
        ["Pedido unificado", "Pendências", "Histórico", "Resumo"]
    )

    with aba_pedido:
        st.caption(
            "Prévia limitada às primeiras 300 linhas. As quatro opções completas ficam "
            "na aba Estoques_Fornecedores do Excel."
        )
        colunas = [
            "ID da carga", "SKU", "EAN", "Descrição", "Quantidade Solicitada",
            "Fornecedor recomendado", "Preço recomendado", "Estoque recomendado",
            "Origem recomendada", "Status motor",
        ]
        st.dataframe(
            resultado.pedido.reindex(columns=colunas).head(300),
            use_container_width=True,
            hide_index=True,
        )

    with aba_pendencias:
        st.caption("Prévia limitada às primeiras 500 pendências consolidadas por SKU.")
        st.dataframe(resultado.pendencias.head(500), use_container_width=True, hide_index=True)

    with aba_historico:
        st.caption("Prévia das 300 linhas mais recentes do histórico.")
        st.dataframe(resultado.historico.tail(300), use_container_width=True, hide_index=True)

    with aba_resumo:
        st.dataframe(resultado.resumo["por_fornecedor"], use_container_width=True, hide_index=True)
        st.dataframe(resultado.resumo["motivos_pendencia"], use_container_width=True, hide_index=True)

    st.markdown("### 4. Downloads")
    st.caption("Para poupar memória, o app prepara somente um arquivo por vez.")
    tipo_download = st.selectbox(
        "Arquivo a preparar",
        ["Pedido unificado", "Pendências", "Histórico", "Resumo"],
    )

    if st.button("Preparar arquivo selecionado", use_container_width=True):
        with st.spinner(f"Preparando {tipo_download.lower()}..."):
            template = Path(__file__).resolve().parents[1] / "templates" / "Modelo Envio Pedidos Fornecedor_Medicamentos.xlsx"
            if tipo_download == "Pedido unificado":
                dados = gerar_pedido_unificado(resultado, template)
                nome = f"Pedido_Unificado_{resultado.id_carga}.xlsx"
            elif tipo_download == "Pendências":
                dados = dataframe_para_excel({"PENDENCIAS": resultado.pendencias})
                nome = f"Pendencias_{resultado.id_carga}.xlsx"
            elif tipo_download == "Histórico":
                dados = dataframe_para_excel({"HISTORICO_COTACAO": resultado.historico})
                nome = f"Historico_Cotacao_{resultado.id_carga}.xlsx"
            else:
                dados = gerar_resumo_excel(resultado)
                nome = f"Resumo_Rodada_{resultado.id_carga}.xlsx"
            st.session_state["qc_download"] = {
                "id_carga": resultado.id_carga,
                "tipo": tipo_download,
                "nome": nome,
                "dados": dados,
            }

    download = st.session_state.get("qc_download")
    if download and download.get("id_carga") == resultado.id_carga:
        st.download_button(
            f'⬇️ Baixar {download["tipo"]}',
            data=download["dados"],
            file_name=download["nome"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
