# Módulo de Download (Fase 1)

Este módulo é responsável pelo download de dados de satélite GOES e implementando cache temporário.

## Arquivos

- **`download_satellite.py`**: Interface principal para download de dados de satélite
- **`download_goes.py`**: Implementação específica para download GOES-19
- **`cache_manager.py`**: Gerenciamento de cache temporário (24h)

## Funcionamento

### 1. Interface Principal (`download_satellite.py`)

A função `download_satellite_data()` é a interface principal que:
- Inicializa o gerenciador de cache
- Calcula o intervalo de tempo necessário (baseado em `num_times_needed`)
- Chama o download GOES com os parâmetros configurados

**Parâmetros:**
- `dtime`: Data/hora dos dados a serem baixados
- `params`: Instância de `NwcstParams` com configurações
- `num_times`: Número de timesteps necessários (padrão: 4)
- `verbose`: Se True, imprime mensagens de status

**Retorna:** Lista de caminhos dos arquivos baixados ou encontrados no cache

### 2. Download GOES (`download_goes.py`)

#### Função `download_goes_single()`

Baixa um único arquivo GOES com as seguintes características:

1. **Verificação de Cache:**
   - Primeiro verifica pelo nome exato do arquivo
   - Se não encontrar, busca por padrão de timestamp
   - Se encontrar no cache e válido (não expirado), retorna imediatamente

2. **Priorização de Satélites:**
   - Tenta GOES-19 primeiro (se `prefer_goes19=True`)
   - Se falhar, tenta GOES-16 como fallback (Houve a troca de satélite. Preciso melhorar.)
   - Retorna informações sobre qual satélite foi usado

3. **Download com Retry:**
   - Até 10 tentativas com espera de 60 segundos entre tentativas
   - Arredonda o tempo para múltiplo de 10 minutos
   - Se arquivo exato não existir, usa o mais recente da hora/dia

**Retorna:** Dicionário com:
- `success`: Se o download foi bem-sucedido
- `file_path`: Caminho do arquivo (do cache ou baixado)
- `satellite`: 'goes19' ou 'goes16'
- `from_cache`: Se o arquivo veio do cache
- `error`: Mensagem de erro (se houver)

#### Função `download_goes_time_range()`

Baixa múltiplos arquivos em paralelo para um intervalo de tempo:

1. **Geração de Timestamps:**
   - Cria lista de timestamps com intervalo de 10 minutos
   - Limita ao número de tempos necessários (`num_times_needed`)

2. **Download Paralelo:**
   - Usa `ThreadPoolExecutor` com `max_workers` threads
   - Cada thread baixa um arquivo independentemente
   - Mostra progresso em tempo real

3. **Estatísticas:**
   - Conta arquivos do cache vs baixados
   - Mostra tempo total de execução
   - Retorna estatísticas completas

**Parâmetros:**
- `start_dt`, `end_dt`: Intervalo de tempo
- `cache_manager`: Gerenciador de cache
- `interval_minutes`: Intervalo entre downloads (padrão: 10)
- `max_retries`: Número máximo de tentativas (padrão: 10)
- `wait_time`: Tempo de espera entre tentativas em segundos (padrão: 60)
- `prefer_goes19`: Priorizar GOES-19 (padrão: True)
- `max_workers`: Número de threads paralelas (padrão: 4)
- `num_times_needed`: Número de tempos necessários (padrão: 4)

**Retorna:** Dicionário com estatísticas:
- `total`: Total de arquivos
- `success`: Arquivos baixados com sucesso
- `from_cache`: Arquivos encontrados no cache
- `downloaded`: Arquivos baixados (não estavam no cache)
- `errors`: Número de erros
- `files`: Lista de caminhos dos arquivos
- `total_time`: Tempo total de execução

### 3. Gerenciamento de Cache (`cache_manager.py`)

A classe `CacheManager` gerencia o cache temporário:

#### Funcionalidades Principais:

1. **Verificação de Existência:**
   - `exists()`: Verifica se arquivo existe e não expirou
   - `get_file_path()`: Retorna caminho se válido, None caso contrário

2. **Busca por Padrão:**
   - `find_files_by_pattern()`: Busca arquivos que correspondem a um padrão
   - Útil para encontrar arquivos com nomes ligeiramente diferentes

3. **Limpeza Automática:**
   - `clean_old_files()`: Remove arquivos expirados (>24h)
   - Executado automaticamente na inicialização se `auto_clean=True`

4. **Utilitários:**
   - `get_cache_size()`: Retorna tamanho total do cache em bytes
   - `clear_cache()`: Remove todos os arquivos do cache

#### Parâmetros de Cache:

- **`cache_dir`**: Diretório do cache (padrão: `./cache`)
- **`max_age_hours`**: Idade máxima em horas (padrão: 24)
- **`auto_clean`**: Limpar automaticamente arquivos antigos (padrão: True)

#### Estrutura do Cache:

```
cache/
├── goes19/
│   └── OR_ABI-L2-RRQPEF-M6_G19_s*.nc
└── goes16/
    └── OR_ABI-L2-RRQPEF-M6_G16_s*.nc
```

## Parâmetros Configuráveis

No arquivo `nowcasting_params.toml`:

```toml
[goes]
# Número de tempos necessários para previsão
num_times_needed = 4

# Priorizar GOES-19 sobre GOES-16
prefer_goes19 = true

# Número máximo de workers para download paralelo
max_workers = 4

[geral]
# Cache temporário para downloads (em horas)
cache_max_age_hours = 24

# Diretório do cache temporário
cache_dir = "./cache"
```

## Exemplo de Uso

```python
from datetime import datetime
import pytz
from src.download.download_satellite import download_satellite_data
from src.parameters.nowcasting_parameters import NwcstParams

# Carrega parâmetros
params = NwcstParams(source="goes")

# Define data/hora
dtime = datetime.now(pytz.UTC)

# Baixa dados
files = download_satellite_data(
    dtime=dtime,
    params=params,
    num_times=4,
    verbose=True
)

print(f"Arquivos baixados: {len(files)}")
```

## Fluxo de Download

```
1. Verifica cache
   ├─> Arquivo existe e válido? → Retorna do cache
   └─> Arquivo não existe ou expirado? → Continua

2. Tenta GOES-19 (se prefer_goes19=True)
   ├─> Sucesso? → Salva no cache e retorna
   └─> Falha? → Tenta GOES-16

3. Tenta GOES-16
   ├─> Sucesso? → Salva no cache e retorna
   └─> Falha? → Retorna erro

4. Download paralelo (para múltiplos arquivos)
   └─> Cada arquivo segue o fluxo acima em thread separada
```

## Notas Importantes

- **Cache baseado em data do arquivo**: O cache expira baseado na data de download do arquivo, não na data que consta no arquivo.
- **Arredondamento de tempo**: Os tempos são arredondados para múltiplos de 10 minutos
- **Fallback automático**: Se GOES-19 não estiver disponível, usa GOES-16 automaticamente (Precisa melhorias. Útil quando data anterior a 2025.)

