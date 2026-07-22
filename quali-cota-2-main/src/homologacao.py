from __future__ import annotations

import re
import pandas as pd

from src.leitura import ler_tabela, normalizar_texto, texto_codigo

ALIASES_MAPA_ENVIO = {
    'industria': ['Fornecedor'],
    'codigo_industria': ['Cód. Fornecedor', 'Cod. Fornecedor'],
    'sinonimos': ['Sinônimos', 'Sinonimos'],
    'tipo_operacao': ['Tem OL/Direto?', 'Tem OL Direto'],
    'distribuidores': ['Distribuidores homologados (OL)', 'Distribuidores homologados'],
    'ativo': ['Ativo?', 'Ativo'],
}


def _partes(valor: object) -> list[str]:
    return [p.strip() for p in re.split(r'[;|\n]+', str(valor or '')) if p.strip()]


def ler_mapa_envio(arquivo) -> pd.DataFrame:
    """Normaliza a aba Fornecedores do Mapa de Envio em relações indústria × distribuidor."""
    base = ler_tabela(
        arquivo,
        ALIASES_MAPA_ENVIO,
        aba_obrigatoria='fornecedores',
        exigir_colunas=['industria'],
    )
    linhas: list[dict] = []
    for reg in base.to_dict('records'):
        industria = str(reg.get('industria') or '').strip()
        if not industria or normalizar_texto(industria) == 'fornecedor':
            continue
        tipo = str(reg.get('tipo_operacao') or '').strip()
        tipo_norm = normalizar_texto(tipo)
        if 'direto' in tipo_norm:
            tipo_resolvido = 'Direto'
        elif 'ol' in tipo_norm:
            tipo_resolvido = 'OL'
        else:
            tipo_resolvido = 'Não informado'
        aliases_industria = list(dict.fromkeys([industria, *_partes(reg.get('sinonimos'))]))
        distribuidores = _partes(reg.get('distribuidores'))
        if tipo_resolvido == 'Direto' and not distribuidores:
            distribuidores = [industria]
        if not distribuidores:
            distribuidores = ['']
        for alias in aliases_industria:
            for distribuidor in distribuidores:
                linhas.append({
                    'ol_industria': alias,
                    'industria_oficial': industria,
                    'codigo_industria': texto_codigo(reg.get('codigo_industria')),
                    'fornecedor': distribuidor,
                    'tipo_operacao': tipo_resolvido,
                    'ativo': 'Sim',
                })
    return pd.DataFrame(linhas)
