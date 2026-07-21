# Patch — fuso horário, fornecedores e histórico

## Correções

- Horário oficial do app alterado para `America/Sao_Paulo`.
- ID da carga, ciclo, Dashboard, histórico e metadados passam a usar a data/hora do Brasil.
- Correspondência entre nomes curtos da cotação e razões sociais da base de regras.
- Diagnóstico mostra quantos fornecedores foram mapeados e quais ainda não possuem regra.
- `Como comprar`, `Observação` e `Email contato` passam a enriquecer tipo de operação e contato.
- Histórico novo recebe data da carga, tipo de operação, fabricante, categoria e tipo de preço.
- Registros históricos legados são enriquecidos por EAN quando possível e identificados quando a origem não possui data/tipo de operação.
- Descrição oficial usa a descrição recebida como fallback quando não existir no cadastro.

## Validação com os arquivos reais de 20/07/2026

- Aba lida: `Volume de Compras - Dia`
- SKUs com Pedido Efetivo: 1.888
- Unidades solicitadas: 24.922
- Fornecedores da cotação: 28
- Fornecedores mapeados: 27
- Único fornecedor ainda sem regra: `GAM`
- SKUs com opção de compra: 1.039
- Pendências consolidadas: 861

Os SKUs restantes se concentram em ausência de cotação, estoque zerado e falta da regra do fornecedor GAM.
