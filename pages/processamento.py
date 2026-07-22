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
from src.sharepoint import AutoDiscovery, SharePointConfig, SharePointConnector, SharePointError, SharePointFile

st.title("⚙️ Processamento de Dados")
st.caption("O Quali Cota localiza automaticamente os arquivos e bases no SharePoint.")


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


@st.cache_data(ttl=600, show_spinner=False)
def _inventario_sharepoint(config_json: str) -> list[dict]:
    conector = _connector(config_json)
    return [item.__dict__ for item in conector.list_configured_roots()]


config_sp = _sharepoint_config()
modo = st.radio(
    "Origem dos arquivos",
    ["SharePoint automático", "Upload manual — contingência"],
    index=0 if config_sp else 1,
    horizontal=True,
)

cotacoes = []
necessidade = None
cadastro = regras = homologacao = historico_anterior = None
sp_auto: AutoDiscovery | None = None
conector: SharePointConnector | None = None

if modo == "SharePoint automático":
    if config_sp is None:
        st.error("Cadastre os Secrets do SharePoint ou use o upload manual de contingência.")
    else:
        config_json = json.dumps(config_sp.__dict__, sort_keys=True)
        conector = _connector(config_json)
        a, b = st.columns([1, 4])
        with a:
            if st.button("🔄 Atualizar", width="stretch"):
                _inventario_sharepoint.clear()
                for chave in list(st.session_state):
                    if chave.startswith("qc_map_"):
                        del st.session_state[chave]
                st.rerun()
        with b:
            try:
                diag = conector.diagnostic()
                st.success(f'Conectado · biblioteca: {diag["library_name"]}', icon="✅")
            except SharePointError as exc:
                st.error(f"Falha na conexão: {exc}")
        try:
            with st.spinner("Mapeando pastas autorizadas..."):
                inventario = [SharePointFile(**row) for row in _inventario_sharepoint(config_json)]
                candidatos = SharePointConnector.candidates_by_role(inventario)
                sp_auto = SharePointConnector.discover(inventario)
            st.info(f"{len(inventario):,} arquivos compatíveis encontrados.".replace(",", "."))
            st.markdown("### Mapeamento assistido dos arquivos")
            st.caption("O sistema sugere; você corrige somente o que estiver errado. Nome e caminho completo aparecem nos seletores.")

            def _label(item: SharePointFile) -> str:
                return f"{item.name}  —  {item.path}"

            def _select_one(titulo: str, opcoes: list[SharePointFile], key: str, obrigatorio: bool, sugestao: SharePointFile | None):
                lista = ([None] if not obrigatorio else []) + opcoes
                indice = 0
                if sugestao in lista:
                    indice = lista.index(sugestao)
                escolhido = st.selectbox(
                    titulo + (" *" if obrigatorio else " — opcional"),
                    lista,
                    index=indice,
                    format_func=lambda x: "Não usar nesta rodada" if x is None else _label(x),
                    key=key,
                )
                return escolhido

            cotacoes = st.multiselect(
                "Cotação(ões) *",
                candidatos["cotacoes"],
                default=list(sp_auto.cotacoes),
                format_func=_label,
                key="qc_map_cotacoes",
                help="Arquivos de QualiCota/01 - Entrada de Arquivos. É possível selecionar mais de um.",
            )
            necessidade = _select_one(
                "Planejamento da rodada", candidatos["planejamentos"], "qc_map_planejamento", True,
                sp_auto.necessidade,
            )
            if necessidade:
                st.success(
                    "Necessidade: aba `Volume de Compras - Dia` · Cadastro EAN/SKU: aba `Ean` do mesmo Planejamento.",
                    icon="✅",
                )
            cadastro = necessidade
            regras = _select_one(
                "Regras de fornecedor", candidatos["regras"], "qc_map_regras", False, sp_auto.regras
            )
            homologacao = _select_one(
                "Homologação OL", candidatos["homologacoes"], "qc_map_homologacao", False, sp_auto.homologacao
            )
            historico_anterior = _select_one(
                "Histórico", candidatos["historicos"], "qc_map_historico", False, sp_auto.historico
            )

            st.markdown("#### Conferência da rodada")
            st.dataframe([
                {"Papel": "Cotação(ões)", "Seleção": " | ".join(_label(x) for x in cotacoes) or "Não selecionada", "Obrigatório": "Sim"},
                {"Papel": "Necessidade", "Seleção": _label(necessidade) if necessidade else "Não selecionada", "Obrigatório": "Sim"},
                {"Papel": "Cadastro EAN/SKU", "Seleção": (f"Aba Ean de {_label(necessidade)}" if necessidade else "Não disponível"), "Obrigatório": "Enriquecimento automático"},
                {"Papel": "Regras", "Seleção": _label(regras) if regras else "Não usar", "Obrigatório": "Não"},
                {"Papel": "Homologação OL", "Seleção": _label(homologacao) if homologacao else "Não usar", "Obrigatório": "Não"},
                {"Papel": "Histórico", "Seleção": _label(historico_anterior) if historico_anterior else "Não usar", "Obrigatório": "Não"},
            ], hide_index=True, width="stretch")
        except SharePointError as exc:
            st.error(f"Não foi possível mapear o SharePoint: {exc}")
else:
    st.info("Contingência manual ativa.")
    cotacoes = st.file_uploader("Cotação(ões)", type=["xlsx", "xlsb", "csv"], accept_multiple_files=True)
    necessidade = st.file_uploader("Necessidade de compra", type=["xlsx", "xlsb", "csv"])
    with st.expander("Bases técnicas", expanded=True):
        cadastro = st.file_uploader("Cadastro EAN/SKU", type=["xlsx", "xlsb", "csv"], key="cadastro")
        regras = st.file_uploader("Regras de fornecedor", type=["xlsx", "xlsb", "csv"], key="regras")
        homologacao = st.file_uploader("Homologação OL — opcional", type=["xlsx", "xlsb", "csv"], key="homologacao")
        historico_anterior = st.file_uploader("Histórico anterior — opcional", type=["xlsx", "xlsb", "csv"], key="historico")

desativados_texto = st.text_area(
    "Fornecedores desativados somente nesta rodada — opcional",
    placeholder="Um nome por linha",
    height=80,
)

pronto_sp = bool(cotacoes and necessidade)
pronto_manual = bool(cotacoes) and necessidade is not None
pronto = pronto_sp if modo == "SharePoint automático" else pronto_manual

st.markdown("### Processar")
if st.button("⚙️ Processar motor", type="primary", width="stretch", disabled=not pronto):
    desativados = [linha.strip() for linha in desativados_texto.splitlines() if linha.strip()]
    etapas = [
        "Baixando arquivos selecionados automaticamente",
        "Lendo a aba Volume de Compras",
        "Validando EANs, preços, estoque e fornecedores",
        "Classificando as quatro melhores opções",
        "Persistindo a rodada",
    ]
    barra = st.progress(0)
    status = st.empty()
    try:
        with tempfile.TemporaryDirectory(prefix="quali_cota_sp_") as pasta_temporaria:
            if modo == "SharePoint automático":
                assert conector is not None
                pasta = Path(pasta_temporaria)
                status.write(f"**{etapas[0]}...**")
                cotacoes_processar = [conector.download_file(item, pasta / "cotacoes") for item in cotacoes]
                necessidade_processar = conector.download_file(necessidade, pasta / "necessidade")
                # Cadastro usa o mesmo arquivo físico, lido na aba Ean.
                cadastro_processar = necessidade_processar
                regras_processar = conector.download_file(regras, pasta / "bases") if regras else None
                homologacao_processar = conector.download_file(homologacao, pasta / "bases") if homologacao else None
                historico_processar = conector.download_file(historico_anterior, pasta / "bases") if historico_anterior else None
            else:
                cotacoes_processar = cotacoes
                necessidade_processar = necessidade
                cadastro_processar = cadastro
                regras_processar = regras
                homologacao_processar = homologacao
                historico_processar = historico_anterior
            barra.progress(1 / len(etapas))
            for indice, etapa in enumerate(etapas[1:-1], start=2):
                status.write(f"**{etapa}...**")
                barra.progress(indice / len(etapas))
            resultado = processar_arquivos(
                cotacoes=cotacoes_processar,
                necessidade=necessidade_processar,
                cadastro=cadastro_processar,
                regras=regras_processar,
                homologacao=homologacao_processar,
                historico=historico_processar,
                fornecedores_desativados=desativados,
            )
        status.write(f"**{etapas[-1]}...**")
        salvar_resultado(resultado)
        st.session_state["qc_id_carga"] = resultado.id_carga
        st.session_state.pop("qc_resultado", None)
        st.session_state.pop("qc_download_path", None)
        id_carga_novo = resultado.id_carga
        del resultado
        gc.collect()
        barra.progress(1.0)
        status.success(f"Rodada processada e salva. ID: {id_carga_novo}")
        st.rerun()
    except Exception as exc:
        status.error(f"Não foi possível concluir o processamento: {exc}")
        st.exception(exc)

if not pronto:
    st.caption("O botão será liberado quando pelo menos uma cotação e um Planejamento forem selecionados.")

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
    avisos_bases = diagnostico.get("avisos_bases", []) or []
    for aviso in avisos_bases:
        st.warning(aviso)

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
