# Patch consolidado — operação assistida

Este pacote consolida as melhorias validadas em 22/07/2026.

## Entregas

- leitura do `Mapa de Envio de Pedidos.xlsb`, aba `Fornecedores`;
- classificação OL, Direto, Distribuidor e Indústria no Pedido Unificado;
- separação entre indústria/fabricante e fornecedor da cotação;
- histórico normalizado, sem cabeçalho legado como registro e com deduplicação;
- página `Tratar pendências` com filtros, seleção e correção em massa dentro do app;
- auditoria das alterações de pendências;
- atualização do Pedido após correções aplicáveis;
- busca do arquivo de homologação também em `Bases Estruturais`;
- geração e upload automático dos quatro outputs em `QualiCota/03 - Saída de Arquivos`;
- atualização de `QualiCota/05_Auditoria/Historico_Cotacao_Consolidado.xlsx`;
- downloads mantidos somente como contingência;
- Dashboard com valor integral, fornecedor alinhado e variações em tabela.

## SharePoint

A aplicação precisa de permissão de escrita no drive, normalmente `Files.ReadWrite.All` ou permissão equivalente concedida pela TI.

Se o upload falhar, a rodada permanece salva e os downloads de contingência continuam disponíveis.

## Pendências

A página permite tratamento em massa sem download/upload. Correções que exigem uma nova oferta comercial continuam registradas até que exista preço e estoque válidos; o app não inventa uma oferta para inserir o SKU no pedido.
