from __future__ import annotations

from pathlib import Path

from src.exportacao import (
    dataframe_para_excel_arquivo,
    gerar_pedido_unificado_arquivo,
    gerar_resumo_excel_arquivo,
)
from src.motor import ResultadoMotor
from src.persistencia import pasta_downloads


def gerar_outputs_rodada(resultado: ResultadoMotor, template: Path) -> list[Path]:
    pasta = pasta_downloads(resultado.id_carga)
    arquivos = [
        pasta / f"Pedido_Unificado_{resultado.id_carga}.xlsx",
        pasta / f"Pendencias_{resultado.id_carga}.xlsx",
        pasta / f"Historico_Cotacao_{resultado.id_carga}.xlsx",
        pasta / f"Resumo_Rodada_{resultado.id_carga}.xlsx",
    ]
    gerar_pedido_unificado_arquivo(resultado, template, arquivos[0])
    dataframe_para_excel_arquivo({"PENDENCIAS": resultado.pendencias}, arquivos[1])
    dataframe_para_excel_arquivo({"HISTORICO_COTACAO": resultado.historico}, arquivos[2])
    gerar_resumo_excel_arquivo(resultado, arquivos[3])
    return arquivos


def publicar_outputs_sharepoint(conector, resultado: ResultadoMotor, template: Path) -> tuple[str, list[dict[str, str]]]:
    # Os quatro arquivos ficam visíveis diretamente na pasta operacional.
    # O ID da carga no nome evita sobrescrever rodadas anteriores.
    pasta_remota = "QualiCota/03 - Saída de Arquivos"
    arquivos = gerar_outputs_rodada(resultado, template)
    publicados = [conector.upload_file(caminho, pasta_remota) for caminho in arquivos]
    # Base única de auditoria: substituída a cada rodada já consolidada e deduplicada.
    conector.upload_file(
        arquivos[2],
        "QualiCota/05_Auditoria",
        remote_name="Historico_Cotacao_Consolidado.xlsx",
    )
    return pasta_remota, publicados
