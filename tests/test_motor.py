from __future__ import annotations

import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from src.exportacao import gerar_pedido_unificado
from src.motor import executar_motor


class TestMotor(unittest.TestCase):
    def setUp(self) -> None:
        self.cadastro = pd.DataFrame(
            [
                ["111", "111", "1", "Produto A", "FAB A", "RX", 1, 1, "Ativo"],
                ["222", "222", "2", "Produto B", "FAB B", "MIP", 1, 1, "Ativo"],
                ["333", "334", "3", "Produto C", "FAB C", "SIMILAR", 10, 10, "Ativo"],
            ],
            columns=["ean_compra", "ean_venda", "sku", "descricao_oficial", "fabricante", "categoria", "caixaria_padrao", "multiplo_padrao", "status_ean"],
        )
        self.regras = pd.DataFrame(
            [
                ["Solfarma", "Distribuidor", "Sim", "Não", "Sim", "Sim", "28 dias", 2],
                ["Bloqueado", "Distribuidor", "Sim", "Sim", "Sim", "Não", "", 0],
            ],
            columns=["fornecedor", "tipo_operacao", "ativo", "bloqueado", "participa_cotacao", "participa_busca", "prazo_pagamento", "lead_time"],
        )
        self.necessidade = pd.DataFrame(
            [
                ["1", "111", "Produto A", 10, 10.5, "Não"],
                ["2", "222", "Produto B", 20, 5.5, "Não"],
                ["3", "334", "Produto C", 15, 21, "Não"],
            ],
            columns=["sku", "ean", "descricao", "quantidade_solicitada", "ultimo_custo", "ruptura_cronica"],
        )
        self.cotacao = pd.DataFrame(
            [
                ["C1", "Solfarma", "Distribuidor", "111", "Produto A", 10, "Unitário", 1, 1, 100],
                ["C2", "Bloqueado", "Distribuidor", "222", "Produto B", 4, "Unitário", 1, 1, 100],
                ["C3", "Solfarma", "Distribuidor", "222", "Produto B", 5, "Unitário", 1, 1, 100],
                ["C4", "Solfarma", "Distribuidor", "333 / 334", "Produto C", 200, "Caixa", 10, 10, 50],
            ],
            columns=["id_carga", "fornecedor", "tipo_operacao", "ean", "descricao_recebida", "preco_final", "tipo_preco", "embalagem", "multiplo", "estoque_fornecedor"],
        )

    def test_decisao_e_caixaria(self) -> None:
        resultado = executar_motor(self.cotacao, self.necessidade, self.cadastro, self.regras)
        por_sku = resultado.pedido.set_index("SKU")
        self.assertEqual(por_sku.loc["1", "Fornecedor recomendado"], "Solfarma")
        self.assertEqual(por_sku.loc["2", "Fornecedor recomendado"], "Solfarma")
        self.assertEqual(por_sku.loc["3", "Quantidade Solicitada"], 20)
        self.assertAlmostEqual(float(por_sku.loc["3", "Preço recomendado"]), 20.0)
        self.assertIn("Fornecedor bloqueado", set(resultado.pendencias["Pendência"]))

    def test_template_mantem_estrutura(self) -> None:
        resultado = executar_motor(self.cotacao, self.necessidade, self.cadastro, self.regras)
        template = Path(__file__).resolve().parents[1] / "templates" / "Modelo Envio Pedidos Fornecedor_Medicamentos.xlsx"
        dados = gerar_pedido_unificado(resultado, template)
        saida = Path("/tmp/pedido_unificado_teste.xlsx")
        saida.write_bytes(dados)
        wb = load_workbook(saida, read_only=True, data_only=False)
        self.assertEqual(wb.sheetnames, ["Base", "Estoques_Fornecedores"])
        self.assertEqual(wb["Base"]["J4"].value, "SKU")
        self.assertEqual(wb["Estoques_Fornecedores"]["D2"].value, "Fornecedor 1")
        self.assertEqual(str(wb["Base"]["J5"].value), "1")
        self.assertEqual(wb["Estoques_Fornecedores"]["D3"].value, "Solfarma")
        wb.close()


if __name__ == "__main__":
    unittest.main()
