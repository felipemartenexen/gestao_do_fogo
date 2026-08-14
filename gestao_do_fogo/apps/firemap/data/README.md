# Planilhas de estatística de fogo

Os números do painel direito do mapa saem daqui — não do Earth Engine. Calcular área
queimada ao vivo custa dezenas de segundos por recorte, e estas planilhas são as mesmas
que a rede já cita nos relatórios.

## Como atualizar

1. Largue o `.csv` nesta pasta (pode substituir o antigo ou deixar os dois — o mais novo
   com o mesmo formato vence, já que a importação apaga a tabela antes de recarregar).
2. Rode:

```bash
make manage ARGS='importar_estatisticas_fogo --conferir'   # só diagnostica
make manage ARGS='importar_estatisticas_fogo'              # grava
```

O `--conferir` diz qual planilha cada arquivo é e quantas linhas não cruzariam com a malha
do IBGE, sem tocar no banco. Use sempre antes de gravar.

## Planilhas reconhecidas

O arquivo é reconhecido **pelo cabeçalho**, não pelo nome — pode renomear à vontade.

| Planilha | Colunas obrigatórias | Alimenta |
|---|---|---|
| Área queimada anual | `Ano`, `Bioma`, `Municipio`, `Área ha` | aba **Área queimada** |
| Área queimada mensal por cobertura | `Ano`, `Mês`, `Bioma`, `UF`, `Nível 1`, `Área ha` | aba **Monitor** |
| Risco de fogo | `Bioma`, `UF`, `Município`, `Classes de risco de fogo`, `Área ha` | aba **Risco** |

Detalhes que a importação assume:

- **Município vem como `Nome (UF)`** na planilha anual, e é o sufixo que vale como UF —
  não a coluna `UF`. A exportação do MapBiomas cruza bioma × UF × município, então
  municípios de fronteira aparecem sob a UF vizinha por imprecisão de borda.
- **`Cod_municipio` é ignorado**: é um id interno do MapBiomas (35, 36, 37…), não o código
  do IBGE. O cruzamento é por nome normalizado, com uma tabela de apelidos em
  `apps/firemap/importers.py` para as grafias em que IBGE e MapBiomas divergem.
- **A planilha de risco não tem coluna de ano**: a temporada sai do nome do arquivo
  (`...-2026.csv`). Se renomear, mantenha o ano no nome.
- Delimitador `,`, decimal `.`, UTF-8.

Se um arquivo novo não for reconhecido, `--conferir` diz isso e nenhuma tabela é tocada;
acrescente o formato em `apps/firemap/importers.py`, na lista `PLANILHAS`.

## Por que os CSV não estão no Git

São dezenas de megabytes de dado derivado, que engordariam o clone para sempre. Ficam
fora do versionamento (`.gitignore`) e são reimportados a partir da fonte original —
MapBiomas Fogo Coleção 5 e a análise de risco do IPAM.
