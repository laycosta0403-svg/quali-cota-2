# Patch MVP Funcional 01

Escopo desta entrega:

- consolidação do código que estava incorretamente dentro de uma segunda pasta `quali-cota-2-main`;
- detecção do `Mapa de Envio de Pedidos.xlsb` em `Bases Estruturais`;
- leitura real da aba `Fornecedores`;
- normalização de relações indústria × distribuidor para OL;
- classificação `OL` / `Direto` propagada ao motor e ao Pedido Unificado;
- Dashboard com valor monetário completo e variações em tabela;
- publicação automática dos quatro outputs diretamente em `QualiCota/03 - Saída de Arquivos`;
- página de tratamento de pendências incluída na navegação;
- fallback de leitura `.xlsb` para `pyxlsb` quando `python-calamine` não estiver disponível.

## Validação local

O arquivo real `Mapa de Envio de Pedidos(3).xlsb` foi lido com sucesso e as relações OL foram expandidas por distribuidor.
