# Patch — download e persistência da última rodada

## Corrigido

- O resultado deixa de existir apenas na memória da sessão do navegador.
- Pedido, opções, pendências, histórico e resumo são persistidos em arquivos compactados no runtime.
- Dashboard e Busca recuperam automaticamente a última rodada após recarregar a página.
- Os arquivos Excel são gerados diretamente no disco, sem manter o conteúdo inteiro em bytes no `session_state`.
- O botão de download usa `on_click="ignore"` para não rerodar o app durante o clique.
- Apenas as tabelas necessárias para cada download são carregadas na memória.

## Observação

A persistência é local ao runtime do Streamlit. Ela sobrevive a recarregamentos e navegação entre páginas, mas um redeploy completo pode limpar o runtime. A persistência definitiva será feita no SharePoint quando a Fase 2 for aprovada pelo TI.
