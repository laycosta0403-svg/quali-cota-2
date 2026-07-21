from __future__ import annotations

import gc
from pathlib import Path

import streamlit as st

from src.exportacao import (
    dataframe_para_excel_arquivo,
    gerar_pedido_unificado_arquivo,
    gerar_resumo_excel_arquivo,
)
from src.persistencia import (
    carregar_metadata,
    carregar_resultado,
    carregar_tabela,
    obter_ultimo_id,
    pasta_downloads,
    salvar_resultado,
)
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
if st.button("⚙️ Processar motor", type="primary", width="stretch", disabled=not pronto):
    desativados = [linha.strip() for linha in desativados_texto.splitlines() if linha.strip()]
    etapas = [
        "Lendo a aba Volume de Compras",
        "Validando Pedido Efetivo, EANs e fornecedores",
        "Classificando as quatro melhores opções",
        "Persistindo a rodada para Dashboard, Busca e downloads",
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
        salvar_resultado(resultado)
        st.session_state["qc_id_carga"] = resultado.id_carga
        st.session_state.pop("qc_resultado", None)
        st.session_state.pop("qc_download_path", None)
        id_carga = resultado.id_carga
        del resultado
        gc.collect()
        barra.progress(1.0)
        status.success(f"Rodada processada e salva com sucesso. ID da carga: {id_carga}")
        st.toast("Dashboard e Busca atualizados.", icon="✅")
        st.rerun()
    except Exception as exc:
        status.error(f"Não foi possível concluir o processamento: {exc}")
        st.exception(exc)

if not pronto:
    st.caption("Envie cotação, necessidade, cadastro EAN/SKU e regras de fornecedor para habilitar o motor.")

id_carga = st.session_state.get("qc_id_carga") or obter_ultimo_id()
metadata = carregar_metadata(id_carga)
if metadata is not None:
    id_carga = str(metadata["id_carga"])
    resumo = metadata.get("resumo", {})
    diagnostico = metadata.get("diagnostico", {})

    st.divider()
    st.markdown("### 3. Resultado da rodada")
    st.success(f"**ID da carga:** `{id_carga}`")
    st.info(
        f'**Aba lida:** {diagnostico.get("aba_necessidade", "—")}  ·  '
        f'**SKUs com Pedido Efetivo:** {int(diagnostico.get("skus_com_pedido", 0)):,}  ·  '
        f'**Unidades solicitadas:** {int(diagnostico.get("unidades_solicitadas", 0)):,}  ·  '
        f'**Linhas da cotação:** {int(diagnostico.get("linhas_cotacao", 0)):,}  ·  '
        f'**Fornecedores mapeados:** {int(diagnostico.get("fornecedores_mapeados", 0))}/'
        f'{int(diagnostico.get("fornecedores_cotacao", 0))}'
        .replace(",", ".")
    )
    sem_regra = diagnostico.get("fornecedores_sem_regra", []) or []
    if sem_regra:
        st.warning("Fornecedores ainda sem correspondência na base de regras: " + ", ".join(sem_regra))

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("SKUs no pedido", int(resumo.get("skus_pedido", 0)))
    r2.metric("Pendências", int(resumo.get("pendencias", 0)))
    r3.metric("Fornecedores", int(resumo.get("fornecedores", 0)))
    r4.metric("Busca ampliada", int(resumo.get("busca_ampliada", 0)))

    aba_pedido, aba_pendencias, aba_historico, aba_resumo = st.tabs(
        ["Pedido unificado", "Pendências", "Histórico", "Resumo"]
    )

    with aba_pedido:
        st.caption("Prévia limitada às primeiras 300 linhas.")
        pedido = carregar_tabela("pedido", id_carga, nrows=300)
        colunas = [
            "ID da carga", "SKU", "EAN", "Descrição", "Quantidade Solicitada",
            "Fornecedor recomendado", "Preço recomendado", "Estoque recomendado",
            "Origem recomendada", "Status motor",
        ]
        st.dataframe(pedido.reindex(columns=colunas), width="stretch", hide_index=True)
        del pedido

    with aba_pendencias:
        st.caption("Prévia limitada às primeiras 500 pendências consolidadas por SKU.")
        pendencias = carregar_tabela("pendencias", id_carga, nrows=500)
        st.dataframe(pendencias, width="stretch", hide_index=True)
        del pendencias

    with aba_historico:
        st.caption("Prévia das 300 linhas mais recentes do histórico.")
        historico = carregar_tabela("historico", id_carga)
        st.dataframe(historico.tail(300), width="stretch", hide_index=True)
        del historico

    with aba_resumo:
        st.dataframe(carregar_tabela("por_fornecedor", id_carga), width="stretch", hide_index=True)
        st.dataframe(carregar_tabela("motivos_pendencia", id_carga), width="stretch", hide_index=True)

    gc.collect()
    st.markdown("### 4. Downloads")
    st.caption(
        "Os resultados foram salvos antes desta etapa. Assim, mesmo que o navegador seja "
        "recarregado, Dashboard e Busca continuam lendo a última rodada disponível."
    )
    tipo_download = st.selectbox(
        "Arquivo a preparar",
        ["Pedido unificado", "Pendências", "Histórico", "Resumo"],
    )

    if st.button("Preparar arquivo selecionado", width="stretch"):
        with st.spinner(f"Preparando {tipo_download.lower()}..."):
            pasta = pasta_downloads(id_carga)
            template = Path(__file__).resolve().parents[1] / "templates" / "Modelo Envio Pedidos Fornecedor_Medicamentos.xlsx"
            if tipo_download == "Pedido unificado":
                nome = f"Pedido_Unificado_{id_carga}.xlsx"
                destino = pasta / nome
                resultado_export = carregar_resultado(id_carga, incluir={"pedido", "opcoes"})
                if resultado_export is None:
                    raise RuntimeError("A rodada persistida não pôde ser recuperada.")
                gerar_pedido_unificado_arquivo(resultado_export, template, destino)
            elif tipo_download == "Pendências":
                nome = f"Pendencias_{id_carga}.xlsx"
                destino = pasta / nome
                dataframe_para_excel_arquivo(
                    {"PENDENCIAS": carregar_tabela("pendencias", id_carga)}, destino
                )
            elif tipo_download == "Histórico":
                nome = f"Historico_Cotacao_{id_carga}.xlsx"
                destino = pasta / nome
                dataframe_para_excel_arquivo(
                    {"HISTORICO_COTACAO": carregar_tabela("historico", id_carga)}, destino
                )
            else:
                nome = f"Resumo_Rodada_{id_carga}.xlsx"
                destino = pasta / nome
                resultado_export = carregar_resultado(id_carga, incluir=set())
                if resultado_export is None:
                    raise RuntimeError("A rodada persistida não pôde ser recuperada.")
                gerar_resumo_excel_arquivo(resultado_export, destino)
            st.session_state["qc_download_path"] = str(destino)
            st.session_state["qc_download_tipo"] = tipo_download
            if "resultado_export" in locals():
                del resultado_export
            gc.collect()

    download_path = st.session_state.get("qc_download_path")
    if download_path:
        caminho = Path(download_path)
        if caminho.exists() and id_carga in caminho.name:
            with caminho.open("rb") as arquivo:
                st.download_button(
                    f'⬇️ Baixar {st.session_state.get("qc_download_tipo", "arquivo")}',
                    data=arquivo,
                    file_name=caminho.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    on_click="ignore",
                )
