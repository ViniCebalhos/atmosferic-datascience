"""Módulo para download de dados de satélite (1ª fase).

Integra o download GOES com o sistema de cache e parâmetros do projeto.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytz

from src.download.cache_manager import CacheManager
from src.download.download_goes import download_goes_time_range
from src.parameters.nowcasting_parameters import NwcstParams


def download_satellite_data(
    dtime: datetime,
    params: Optional[NwcstParams] = None,
    num_times: int = 4,
    verbose: bool = True,
) -> list[Path]:
    """Baixa dados de satélite usando cache temporário.

    Esta função implementa a 1ª fase do projeto: Download de dados de satélite.
    Prioriza GOES-19 e usa GOES-16 como fallback.
    Utiliza cache temporário (24h) para evitar downloads desnecessários.

    Parameters
    ----------
    dtime : datetime
        Data e hora dos dados a serem baixados.
    params : NwcstParams, optional
        Parâmetros de configuração. Se None, cria uma nova instância.
    num_times : int, optional
        Número de tempos a serem baixados (padrão: 4).
    verbose : bool, optional
        Se True, imprime mensagens de status (padrão: True).

    Returns
    -------
    list[Path]
        Lista de caminhos dos arquivos baixados ou encontrados no cache.

    Examples
    --------
    >>> from datetime import datetime
    >>> import pytz
    >>> from src.download.download_satellite import download_satellite_data
    >>> dtime = datetime.now(pytz.UTC)
    >>> files = download_satellite_data(dtime, num_times=4)
    """
    if params is None:
        params = NwcstParams(source="goes")

    # Inicializa o gerenciador de cache
    cache_manager = CacheManager(
        cache_dir=params.cache_dir,
        max_age_hours=params.cache_max_age_hours,
        auto_clean=True,
    )

    # Calcula intervalo de tempo necessário
    interval_minutes = params.time_range_minutes
    start_dt = dtime - timedelta(minutes=(num_times - 1) * interval_minutes)
    end_dt = dtime

    # Garante que está em UTC
    utc = pytz.UTC
    if start_dt.tzinfo is None:
        start_dt = utc.localize(start_dt)
    if end_dt.tzinfo is None:
        end_dt = utc.localize(end_dt)

    if verbose:
        print(f"\n{'='*60}")
        print(f"DOWNLOAD DE DADOS DE SATÉLITE")
        print(f"Data/Hora alvo: {dtime.strftime('%Y-%m-%d %H:%M')} UTC")
        print(
            f"Período necessário: {start_dt.strftime('%Y-%m-%d %H:%M')} até {end_dt.strftime('%Y-%m-%d %H:%M')} UTC"
        )
        print(f"Número de tempos: {num_times}")
        print(f"Intervalo: {interval_minutes} minutos")
        print(f"Cache: {params.cache_dir} (max {params.cache_max_age_hours}h)")
        print(
            f"Satélite: GOES-19 (data >= 2025) ou GOES-16 (data < 2025)"
        )
        print(f"{'='*60}\n")

    # Executa o download
    stats = download_goes_time_range(
        start_dt=start_dt,
        end_dt=end_dt,
        cache_manager=cache_manager,
        interval_minutes=interval_minutes,
        max_retries=10,
        wait_time=60,
        verbose=verbose,
        prefer_goes19=params.prefer_goes19,
        max_workers=params.max_workers,
        num_times_needed=num_times,
    )

    if verbose:
        cache_size_mb = cache_manager.get_cache_size() / (1024 * 1024)
        print(f"\nTamanho do cache: {cache_size_mb:.2f} MB")

    return stats["files"]
