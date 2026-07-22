# Fase 3 — Reconstrução do motor

## Escopo fechado

- Pedido Unificado no template oficial.
- Quatro melhores opções por SKU: código, fornecedor, estoque, preço e variação.
- Fornecedor recomendado pelo motor.
- Pendências.
- Histórico acumulativo e deduplicado.
- Resumo e Dashboard.

## Regras implementadas

- Identificação por EAN de compra e venda.
- Desmembramento de EANs múltiplos.
- Fornecedor ativo, desativado ou bloqueado.
- Participação na cotação e busca ampliada.
- Homologação OL × distribuidor.
- Preço válido e conversão de preço por caixa para preço unitário.
- Estoque disponível.
- Ajuste de quantidade por caixaria/múltiplo, sempre para cima.
- Busca ampliada no histórico para ruptura crônica.
- Deduplicação do histórico por carga, fornecedor, EAN, SKU e preço unitário.

## Saídas

1. `Pedido_Unificado.xlsx`
   - `Base`
   - `Estoques_Fornecedores`
2. `Pendencias.xlsx`
3. `Historico_Cotacao.xlsx`
4. `Resumo_Rodada.xlsx`

## Fora desta entrega

- Leitura automática no SharePoint, que permanece na Fase 2 aguardando aprovação do TI.
- Envio final do pedido ao Qualicota.
