# Módulo de Parâmetros

Este módulo gerencia os parâmetros do pipeline de nowcast via arquivos TOML e a classe `NwcstParams`.

## Arquivos

- **`nowcasting_params.toml`**: Arquivo de configuração em TOML com todos os parâmetros
- **`nowcasting_parameters.py`**: Classe Python (`NwcstParams`) que carrega e gerencia os parâmetros

## Estrutura dos Parâmetros

### Seção `[geral]`

Parâmetros gerais aplicáveis a todo o projeto:

```toml
[geral]
# Diretório padrão de saída
output_path_default = "./outputs"

# Caminho base onde os dados serão armazenados/baixados
db_path = "./data"

# Domínio do estado de São Paulo: [lon_min, lon_max, lat_min, lat_max]
domain_SP = [-53.0, -44.0, -26.0, -19.0]

# Tempo de atraso para busca de arquivos (em minutos)
look_behind_minutes = 240

# Cache temporário para downloads (em horas)
cache_max_age_hours = 24

# Diretório do cache temporário
cache_dir = "./cache"
```

**Descrição dos Parâmetros:**

- **`output_path_default`**: Diretório onde os arquivos NetCDF serão salvos
- **`db_path`**: Caminho base para armazenamento de dados (não usado atualmente)
- **`domain_SP`**: Domínio geográfico do estado de São Paulo em graus
  - `lon_min`: -53.0° (oeste)
  - `lon_max`: -44.0° (leste)
  - `lat_min`: -26.0° (sul)
  - `lat_max`: -19.0° (norte)
- **`look_behind_minutes`**: Tempo de atraso para busca de arquivos (240 min = 4 horas)
- **`cache_max_age_hours`**: Idade máxima do cache em horas (24h)
- **`cache_dir`**: Diretório onde os arquivos em cache são armazenados

### Seção `[goes]`

Parâmetros específicos para dados GOES:

```toml
[goes]
# Formato do nome do arquivo de entrada
input_format = "OR_ABI-L2-RRQPEF-M6_G1[69]_s{date:%Y%j%H%M}*.nc"

# Formato do nome do arquivo de saída
output_format = "{:%Y%m%d%H%M}00_NOWCAST_GOES.nc"

# Estrutura de diretórios onde os dados serão salvos
dir_path = "goes/{date:%Y/%m/%d/}"

# Frequência de amostragem dos dados (em minutos)
freq = 10

# Número de tempos necessários para previsão
num_times_needed = 4

# Priorizar GOES-19 sobre GOES-16
prefer_goes19 = true

# Número máximo de workers para download paralelo
max_workers = 4

# Método para cálculo de motion field (LK, etc)
motion_method = "LK"

# Método de extrapolação (sprog, anvil, etc)
extrapolation_method = "sprog"

# Threshold de precipitação para SPROG (mm/h)
sprog_R_thr = 0.5

# Número de timesteps para previsão (18 = 3 horas a cada 10 min)
forecast_timesteps = 18
```

**Descrição dos Parâmetros:**

- **`input_format`**: Padrão de busca dos arquivos GOES de entrada
  - `{date:%Y%j%H%M}`: Formato de data (ano, dia do ano, hora, minuto)
  - `G1[69]`: GOES-16 ou GOES-19
- **`output_format`**: Formato do nome do arquivo NetCDF de saída
  - `{:%Y%m%d%H%M}00`: Data/hora formatada
- **`dir_path`**: Estrutura de diretórios para organização dos dados
- **`freq`**: Frequência de amostragem em minutos (10 min)
- **`num_times_needed`**: Número de timesteps necessários para calcular a previsão (4)
- **`prefer_goes19`**: Se True, prioriza GOES-19, senão usa GOES-16
- **`max_workers`**: Número de threads paralelas para download (4)
- **`motion_method`**: Método para cálculo de motion field ("LK" = Lucas-Kanade)
- **`extrapolation_method`**: Método de extrapolação ("sprog" = Spectral Prognosis)
- **`sprog_R_thr`**: Threshold de precipitação para SPROG em mm/h (0.5)
- **`forecast_timesteps`**: Número de timesteps da previsão (18 = 3 horas)

### Seção `[satelite]`

Parâmetros genéricos para dados de satélite (reservado para uso futuro):

```toml
[satelite]
# Formato genérico para dados de satélite
input_format = "satellite_{date:%Y%m%d_%H%M}.nc"
output_format = "{:%Y%m%d%H%M}00_NOWCAST_SATELLITE.nc"
dir_path = "satellite/{date:%Y/%m/%d/}"
freq = 10
```

## Classe NwcstParams

A classe `NwcstParams` carrega e gerencia os parâmetros:

### Inicialização

```python
from src.parameters.nowcasting_parameters import NwcstParams

# Carrega parâmetros para fonte 'goes'
params = NwcstParams(source="goes")
```

### Propriedades Principais

#### Propriedades Gerais

- **`domain`**: Domínio de SP `[lon_min, lon_max, lat_min, lat_max]`
- **`output_path_default`**: Diretório padrão de saída
- **`cache_max_age_hours`**: Idade máxima do cache em horas
- **`cache_dir`**: Diretório do cache
- **`look_behind_minutes`**: Tempo de atraso para busca

#### Propriedades Específicas da Fonte

- **`frequency`**: Frequência de amostragem (ex: "10min")
- **`time_range_minutes`**: Intervalo em minutos
- **`num_times_needed`**: Número de tempos necessários
- **`prefer_goes19`**: Priorizar GOES-19
- **`max_workers`**: Número de workers paralelos
- **`motion_method`**: Método de motion field
- **`extrapolation_method`**: Método de extrapolação
- **`sprog_R_thr`**: Threshold para SPROG
- **`forecast_timesteps`**: Número de timesteps da previsão
- **`output_format`**: Formato do arquivo de saída

#### Métodos

- **`input_dir(dtime)`**: Retorna diretório de entrada para uma data/hora
- **`input_pattern(dtime)`**: Retorna padrão de busca para uma data/hora

### Exemplo de Uso

```python
from datetime import datetime
import pytz
from src.parameters.nowcasting_parameters import NwcstParams

# Carrega parâmetros
params = NwcstParams(source="goes")

# Acessa propriedades
print(f"Domínio: {params.domain}")
print(f"Frequência: {params.frequency}")
print(f"Timesteps: {params.forecast_timesteps}")

# Usa métodos
dtime = datetime.now(pytz.UTC)
input_dir = params.input_dir(dtime)
pattern = params.input_pattern(dtime)
print(f"Diretório: {input_dir}")
print(f"Padrão: {pattern}")
```

## Validação

A classe valida automaticamente:

1. **Fonte válida**: Verifica se a fonte está na lista de fontes válidas
   - Fontes válidas: `["goes", "satellite"]`

2. **Arquivo TOML**: Verifica se o arquivo existe e é válido

3. **Seções obrigatórias**: Verifica se as seções `[geral]` e `[source]` existem

## Formato de Data nos Parâmetros

Os parâmetros usam formatação de data Python:

- **`{date:%Y}`**: Ano (4 dígitos)
- **`{date:%j}`**: Dia do ano (001-366)
- **`{date:%m}`**: Mês (01-12)
- **`{date:%d}`**: Dia (01-31)
- **`{date:%H}`**: Hora (00-23)
- **`{date:%M}`**: Minuto (00-59)

**Exemplo:**
- `{date:%Y/%m/%d/}` → `2024/01/15/`
- `{date:%Y%m%d%H%M}` → `202401151430`

## Notas Importantes

- **Fonte obrigatória**: A fonte deve ser especificada na inicialização (Ainda não)
- **Caminho relativo**: O arquivo TOML é procurado na pasta `parameters/`
- **Timezone**: Todos os parâmetros de data/hora assumem UTC
- **Valores padrão**: Alguns parâmetros têm valores padrão se não especificados no TOML

