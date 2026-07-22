# Patch — desempenho do processamento

Este patch reduz o pico de memória e o tempo do motor ao filtrar a cotação para os EANs/SKUs efetivamente solicitados antes de criar a base enriquecida de ofertas.

## Alterações

- preserva a leitura das 128.951 linhas da cotação para diagnóstico;
- processa em profundidade somente as ofertas relacionadas aos SKUs da rodada;
- resolve a regra uma vez por fornecedor, e não uma vez por linha;
- evita uma cópia integral desnecessária da base de ofertas;
- mantém as mesmas quatro opções e os mesmos resultados do motor;
- exibe a quantidade de ofertas relevantes processadas.

## Validação real

Com os arquivos de 20/07/2026, o resultado permaneceu em 1.039 SKUs no pedido e 861 pendências, mas o pico de memória do motor caiu de aproximadamente 458 MB para 270 MB.
