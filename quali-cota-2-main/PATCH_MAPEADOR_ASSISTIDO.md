# Patch — Mapeador assistido de arquivos SharePoint

## Implementado
- Sugestão automática por caminho operacional.
- Seletores independentes para corrigir apenas o papel errado.
- Cotação permite múltiplos arquivos.
- Planejamento diário é sugerido pelo arquivo mais recente em Supply.
- Necessidade usa a aba `Volume de Compras - Dia`.
- Cadastro EAN/SKU usa a aba `Ean` do mesmo Planejamento.
- Regras, homologação OL e histórico são enriquecimentos opcionais.
- O processamento exige somente cotação e Planejamento.
- Cada seletor mostra nome e caminho completo.
- Escolhas permanecem na sessão e só são limpas ao clicar em Atualizar.

## Caminhos priorizados
- Cotação: `QualiCota/01 - Entrada de Arquivos`
- Planejamento: arquivos `Planejamento - <data>` na árvore `Supply`
- Regras: `QualiCota/04_Governanca/Regras_fornecedores.xlsx`
- Homologação: `Bases Estruturais/Mapa de Envio de Pedidos.xlsb`
- Histórico: `Supply/COMPRAS (1)/NOVO/mapa diario 2.0-NI-QDC-013.xlsx`
