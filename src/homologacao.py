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


def _partes(valor: object, separar_hifen: bool = False) -> list[str]:
    if valor is None or pd.isna(valor):
        return []
    texto = str(valor).strip()
    if not texto or normalizar_texto(texto) in {'nan', 'none'}:
        return []
    padrao = r'[;|\n]+' if not separar_hifen else r'[;|\n]+|\s*-\s*'
    return [parte.strip() for parte in re.split(padrao, texto) if parte.strip()]



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
        distribuidores = _partes(reg.get('distribuidores'), separar_hifen=True)
        if tipo_resolvido == 'Direto' and not distribuidores:
            distribuidores = [industria]
        if not distribuidores:
            # OL sem distribuidor cadastrado permanece não homologada; não criamos
            # uma relação vazia que poderia produzir falsos positivos.
            continue
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
