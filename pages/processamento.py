from __future__ import annotations

import gc
import json
import tempfile
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
from src.sharepoint import SharePointConfig, SharePointConnector, SharePointError, SharePointFile


st.title("⚙️ Processamento de Dados")
st.caption("Execute o motor e gere os quatro outputs oficiais da rodada.")


def _sharepoint_config() -> SharePointConfig | None:
    try:
        secao = st.secrets.get("sharepoint")
    except (FileNotFoundError, KeyError):
        return None
    if not secao:
        return None
    try:
        return SharePointConfig.from_mapping(dict(secao))
    except SharePointError as exc:
        st.warning(f"Secrets do SharePoint incompletos: {exc}")
        return None


@st.cache_resource(show_spinner=False)
def _connector(config_json: str) -> SharePointConnector:
    return SharePointConnector(SharePointConfig.from_mapping(json.loads(config_json)))


@st.cache_data(ttl=300, show_spinner=False)
def _listar_sharepoint(config_json: str, folder: str) -> list[dict]:
    conector = _connector(config_json)
    return [item.__dict__ for item in conector.list_files(folder)]


config_sp = _sharepoint_config()
modo_padrao = "SharePoint" if config_sp else "Upload manual"
modo = st.radio(
    "Origem dos arquivos da rodada",
    ["SharePoint", "Upload manual"],
    index=0 if modo_padrao == "SharePoint" else 1,
    horizontal=True,
    help="O upload manual permanece como contingência.",
)

cotacoes = []
necessidade = None
sp_cotacoes_selecionadas: list[SharePointFile] = []
sp_necessidade_selecionada: SharePointFile | None = None

if modo == "SharePoint":
    if config_sp is None:
        st.error(
            "O conector está instalado, mas os Secrets do SharePoint ainda não foram cadastrados. "
            "Abra Manage app → Settings → Secrets e cole a configuração fornecida no pacote."
        )
    else:
        config_json = json.dumps(config_sp.__dict__, sort_keys=True)
        conector = _connector(config_json)
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("🔄 Atualizar listas", width="stretch"):
                _listar_sharepoint.clear()
                st.rerun()
        with c2:
            try:
                diag = conector.diagnostic()
                st.success(
                    f'Conectado ao SharePoint · biblioteca: {diag["library_name"]}',
                    icon="✅",
                )
            except SharePointError as exc:
                st.error(f"Falha no teste do SharePoint: {exc}")

        try:
            with st.spinner("Consultando arquivos liberados no SharePoint..."):
                dados_cotacoes = _listar_sharepoint(config_json, config_sp.cotacoes_folder)
                dados_necessidades = _listar_sharepoint(config_json, config_sp.planejamento_folder)
            arquivos_cotacao = [SharePointFile(**item) for item in dados_cotacoes]
            arquivos_necessidade = [SharePointFile(**item) for item in dados_necessidades]
            mapa_cotacoes = {item.item_id: item for item in arquivos_cotacao}
            mapa_necessidades = {item.item_id: item for item in arquivos_necessidade}

            st.markdown("### 1. Arquivos da rodada")
            ids_cotacoes = st.multiselect(
                "Cotação(ões) encontradas no SharePoint",
                options=list(mapa_cotacoes),
                format_func=lambda item_id: mapa_cotacoes[item_id].label,
                placeholder="Selecione uma ou mais cotações",
            )
            necessidade_id = st.selectbox(
                "Necessidade de compra encontrada no SharePoint",
                options=[""] + list(mapa_necessidades),
                format_func=lambda item_id: (
                    "Selecione o Planejamento" if not item_id else mapa_necessidades[item_id].label
                ),
            )
            sp_cotacoes_selecionadas = [mapa_cotacoes[item_id] for item_id in ids_cotacoes]
            sp_necessidade_selecionada = mapa_necessidades.get(necessidade_id)
            if not arquivos_cotacao:
                st.warning(f'Nenhuma cotação foi encontrada em "{config_sp.cotacoes_folder}".')
            if not arquivos_necessidade:
                st.warning(f'Nenhum Planejamento foi encontrado em "{config_sp.planejamento_folder}".')
        except SharePointError as exc:
            st.error(f"Não foi possível listar os arquivos do SharePoint: {exc}")
else:
    st.info("Modo de contingência: os arquivos serão enviados manualmente.")
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

arquivos_rodada_prontos = (
    bool(sp_cotacoes_selecionadas) and sp_necessidade_selecionada is not None
    if modo == "SharePoint"
    else bool(cotacoes) and necessidade is not None
)
pronto = arquivos_rodada_prontos and cadastro is not None and regras is not None

st.markdown("### 2. Processar")
st.caption(
    "Com os arquivos reais, a leitura e a classificação podem levar alguns minutos. "
    "Não clique novamente enquanto o motor estiver executando."
)
if st.button("⚙️ Processar motor", type="primary", width="stretch", disabled=not pronto):
    desativados = [linha.strip() for linha in desativados_texto.splitlines() if linha.strip()]
    etapas = [
        "Obtendo os arquivos da rodada",
        "Lendo a aba Volume de Compras",
        "Validando Pedido Efetivo, EANs e fornecedores",
        "Classificando as quatro melhores opções",
        "Persistindo a rodada para Dashboard, Busca e downloads",
    ]
    barra = st.progress(0)
    status = st.empty()
    try:
        with tempfile.TemporaryDirectory(prefix="quali_cota_sp_") as pasta_temporaria:
            if modo == "SharePoint":
                status.write(f"**{etapas[0]} no SharePoint...**")
                pasta = Path(pasta_temporaria)
                cotacoes_processar = [
                    conector.download_file(item, pasta / "cotacoes")
                    for item in sp_cotacoes_selecionadas
                ]
                necessidade_processar = conector.download_file(
                    sp_necessidade_selecionada, pasta / "planejamento"
                )
            else:
                cotacoes_processar = cotacoes
                necessidade_processar = necessidade
            barra.progress(1 / len(etapas))

            for indice, etapa in enumerate(etapas[1:-1], start=2):
                status.write(f"**{etapa}...**")
                barra.progress(indice / len(etapas))

            resultado = processar_arquivos(
                cotacoes=cotacoes_processar,
                necessidade=necessidade_processar,
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
    st.caption(
        "Selecione cotação e necessidade e envie cadastro EAN/SKU e regras de fornecedor "
        "para habilitar o motor."
    )

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
        f'**Ofertas relevantes processadas:** {int(diagnostico.get("linhas_cotacao_relevantes", 0)):,}  ·  '
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
