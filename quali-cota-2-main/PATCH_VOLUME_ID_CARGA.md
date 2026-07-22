# Patch — Volume de Compras e ID da carga

Correções incluídas:

- leitura obrigatória da aba cujo nome contém `Volume de Compras`;
- mapeamento de `CÓD`, `EAN DE COMPR.`, `Pedido Efetivo` e `CAIXARIA`;
- bloqueio do processamento se `Pedido Efetivo` não for encontrado ou vier todo zerado;
- geração automática de ID no formato `QDC_AAAAMMDD_HHMMSS_mmm`;
- propagação do ID para Pedido Unificado (`NR COTAÇÃO`), Pendências, Histórico, Resumo e nomes dos downloads;
- processamento somente dos SKUs com `Pedido Efetivo > 0`;
- pendências consolidadas por SKU, em vez de uma linha para cada oferta rejeitada;
- prévias limitadas na tela e preparação de apenas um download por vez;
- template oficial compactado sem alterar cabeçalhos, abas ou formatação necessária;
- estilos dos cartões compatíveis com tema claro e escuro.

Validação com os arquivos reais de 20/07/2026:

- aba lida: `Volume de Compras - Dia`;
- 1.888 SKUs com Pedido Efetivo positivo;
- 24.922 unidades solicitadas;
- ID gerado e preenchido no Pedido Unificado;
- quatro outputs gerados sem ficarem vazios;
- testes automatizados: 2/2 aprovados.
