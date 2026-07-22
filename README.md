# Quali Cota 2.0

Aplicação Streamlit para executar o motor de compras e gerar os outputs oficiais da rodada.

## Escopo implementado — Fase 3

O motor recebe cotação, necessidade e bases técnicas, valida as ofertas e entrega:

1. **Pedido Unificado** no formato exato de `Modelo Envio Pedidos Fornecedor_Medicamentos.xlsx`.
   - Aba `Base`: pedido e fornecedor recomendado.
   - Aba `Estoques_Fornecedores`: quatro melhores opções por SKU, com fornecedor, preço e estoque.
2. **Pendências** com problema, impacto e ação sugerida.
3. **Histórico** acumulativo e deduplicado.
4. **Resumo e Dashboard** da última rodada.

A classificação considera EAN/SKU, fornecedor ativo, bloqueio, participação na cotação, homologação OL, preço válido, estoque, caixaria/múltiplo e busca ampliada para ruptura crônica.

## Fase 2 — SharePoint

O conector Microsoft Graph lista as cotações e os Planejamentos nas pastas configuradas em `st.secrets`. O upload manual permanece disponível como contingência. Consulte `PATCH_SHAREPOINT_CONNECTOR.md`.

## Estrutura

```text
app.py
pages/
  dashboard.py
  processamento.py
  busca.py
src/
  leitura.py
  motor.py
  processamento.py
  exportacao.py
  ui.py
  sharepoint.py
templates/
  Modelo Envio Pedidos Fornecedor_Medicamentos.xlsx
```

## Executar localmente

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Publicação no Streamlit Community Cloud

- Repositório: `quali-cota-2`
- Branch: `main`
- Arquivo principal: `app.py`

O template Excel precisa permanecer na pasta `templates/`.
