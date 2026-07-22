# Patch — Conector SharePoint

Este patch ativa a Fase 2 sem remover o upload manual de contingência.

## O que foi adicionado

- autenticação app-only no Microsoft Graph;
- resolução automática de Site ID e biblioteca, quando os IDs não forem informados;
- listagem das cotações e Planejamentos nas pastas configuradas;
- seleção de uma ou mais cotações e de um Planejamento;
- download temporário e em blocos, sem gravar credenciais ou arquivos no GitHub;
- botão para atualizar as listas;
- teste de conexão visível na tela;
- upload manual mantido como contingência.

## Secrets necessários

Cadastrar em **Manage app → Settings → Secrets**. Não criar nem enviar `secrets.toml` ao GitHub.

```toml
[sharepoint]
tenant_id = "SEU_TENANT_ID"
client_id = "SEU_CLIENT_ID"
client_secret = "SEU_CLIENT_SECRET"

# Opção recomendada quando você conhece a URL do site:
site_hostname = "qualidoc.sharepoint.com"
site_path = "/sites/COMPRASQDC"

# Nome exibido da biblioteca. Em alguns ambientes é "Documentos";
# em outros, "Documents" ou outro nome definido pela empresa.
library_name = "Documentos"

# Caminhos relativos dentro da biblioteca:
cotacoes_folder = "CAMINHO/PASTA/COTACOES"
planejamento_folder = "CAMINHO/PASTA/PLANEJAMENTOS"

# Alternativamente, o TI pode fornecer IDs prontos:
# site_id = "..."
# drive_id = "..."
```

## Permissão esperada

A aplicação precisa de acesso de leitura ao site/biblioteca no Microsoft Graph. Se o TI usa `Sites.Selected`, a aplicação também precisa estar autorizada especificamente no site do Quali Cota.

## Primeiro teste

1. Salvar os Secrets.
2. Reiniciar o app.
3. Abrir Processamento de Dados.
4. Escolher `SharePoint`.
5. Confirmar a mensagem verde de conexão.
6. Confirmar que os arquivos aparecem nos dois seletores.
7. Selecionar os arquivos e usar as bases técnicas do motor normalmente.
