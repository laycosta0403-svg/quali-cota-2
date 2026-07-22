# Patch — SharePoint automático e bases sem seleção

- Remove a exigência de `cotacoes_folder` e `planejamento_folder`.
- Percorre recursivamente `QualiCota` e `Supply`, respeitando `max_depth`.
- Localiza automaticamente cotação, Planejamento/Volume de Compras, cadastro EAN/SKU, regras, homologação e histórico.
- Baixa as bases técnicas automaticamente no momento do processamento.
- Mantém o upload manual apenas como contingência.
- Não contém credenciais.

## Secrets esperados

```toml
[sharepoint]
tenant_id = "..."
client_id = "..."
client_secret = "..."
site_hostname = "qualidoc.sharepoint.com"
site_path = "/sites/COMPRASQDC"
library_name = "Documents"
root_folder = ""
qualicota_root = "QualiCota"
supply_root = "Supply"
recursive = true
max_depth = 10
```
