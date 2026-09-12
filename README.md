# Satellite Nowcasting — Short-term precipitation forecasting with GOES

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![CI](https://github.com/ViniCebalhos/atmosferic-datascience/actions/workflows/ci.yml/badge.svg)

Pipeline de nowcasting de precipitação usando dados de satélite GOES (GOES-19 a partir de 2025, GOES-16 para datas anteriores). Inclui download, regrid para domínio configurável, motion field (Lucas-Kanade), extrapolação (SPROG) e saída em NetCDF e plots.

O domínio padrão do exemplo é configurável via `src/parameters/nowcasting_params.toml` (ex.: `domain_SP` para região de interesse).

---

## Resultado

<!-- TODO: adicionar GIF/PNG de exemplo do nowcast (ex.: sequência de mapas de precipitação por lead time) -->
<!-- ![Exemplo de nowcast](docs/exemplo_nowcast.gif) -->

---

## Pipeline (Nowcast)

1. **Download** — Dados GOES do bucket público NOAA (S3). GOES-19 para datas ≥ 2025, GOES-16 para datas anteriores. Cache opcional (24h).
2. **Leitura e regrid** — RRQPE, corte para domínio e regrid para grade regular (ex.: 0,03°).
3. **Previsão** — Motion field (LK) + extrapolação (SPROG ou ANVIL).
4. **Escrita** — NetCDF com metadados e compressão.
5. **Plot (opcional)** — Mapas por lead time (cartopy + paleta pysteps).

## Estrutura

```
atmospheric-datascience/
├── src/
│   ├── download/       # Download GOES (cache, GOES-19/16 por data)
│   ├── read/           # Leitura e regrid
│   ├── forecast/       # Motion fields e extrapolação
│   ├── write/          # NetCDF
│   ├── plot/           # Visualização
│   └── parameters/     # Configuração TOML
├── nowcast.py          # Script principal
├── requirements/
├── tests/
└── outputs/
```

## Uso

```bash
# Data/hora específica
python nowcast.py -time 20240115T1430

# Data/hora atual
python nowcast.py

# Com geração de plots
python nowcast.py -time 20240115T1430 -plot

# Diretório de saída
python nowcast.py -time 20240115T1430 -output_path /caminho/para/saida
```

**Argumentos:** `-source` (goes), `-time` (YYYYMMDDTHHMM), `-output_path`, `-plot`.

## Configuração

Parâmetros em `src/parameters/nowcasting_params.toml`:

- **Domínio** — `domain_SP`: `[lon_min, lon_max, lat_min, lat_max]`
- **Resolução** — 0,03° (~3,3 km)
- **Frequência** — 10 min
- **Timesteps** — 18 (3 h)
- **Cache** — 24 h
- **Métodos** — Motion: LK; Extrapolação: SPROG

## Instalação

```bash
pip install -r requirements/prod.txt
```

Para desenvolvimento (lint, tipos, docstrings, testes):

```bash
pip install -r requirements/dev.txt
```

## Saída

- **NetCDF** — `outputs/`, formato `YYYYMMDDHHMM00_NOWCAST_GOES.nc`
- **Plots** — `tests/`, um PNG por lead time (quando usar `-plot`)

## CI (GitHub Actions)

O workflow em `.github/workflows/ci.yml` executa em cada push/PR para `main`/`master`:

- isort, flake8, pyright
- interrogate (cobertura de docstrings), pydocstyle
- pytest

## Ferramentas de desenvolvimento

- **Pre-commit** — `pre-commit install` (black, isort, flake8, pyright, interrogate, pydocstyle)
- **Documentação dos módulos** — `src/download/README.md`, `src/parameters/README.md`, etc.

## Licença

MIT.
