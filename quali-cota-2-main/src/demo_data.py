import pandas as pd

def kpis_demo() -> dict:
    return {
        "valor_total": 553218.00,
        "skus_pedido": 1001,
        "pendencias": 416,
        "sem_cotacao": 4205,
        "distribuidores": 24,
    }

def compra_distribuidor_demo() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Distribuidor": ["Santa Cruz", "Panpharma", "Profarma", "Servimed", "Profarma ES"],
            "Valor": [182400, 134800, 97800, 76300, 61918],
        }
    )

def variacoes_demo() -> tuple[pd.DataFrame, pd.DataFrame]:
    altas = pd.DataFrame(
        {
            "SKU": ["10021", "10087", "10234", "10440", "10551"],
            "Descrição": ["Produto A", "Produto B", "Produto C", "Produto D", "Produto E"],
            "Variação": [31.4, 27.8, 23.1, 19.7, 17.2],
        }
    )
    baixas = pd.DataFrame(
        {
            "SKU": ["20102", "20215", "20288", "20401", "20592"],
            "Descrição": ["Produto F", "Produto G", "Produto H", "Produto I", "Produto J"],
            "Variação": [-22.3, -18.6, -16.4, -13.1, -11.8],
        }
    )
    return altas, baixas
