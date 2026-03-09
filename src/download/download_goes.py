"""Módulo para download de dados GOES-19 e GOES-16.

GOES-19 é o substituto do GOES-East (GOES-16): usa GOES-19 para datas >= 2025
e GOES-16 apenas quando a data da previsão é anterior a 2025.
Implementa cache temporário (24h) para evitar downloads desnecessários.
"""

# Data a partir da qual só se usa GOES-19 (GOES-16 descontinuado como GOES-East)
GOES19_ONLY_FROM_YEAR = 2025

import s3fs
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Optional

import pytz

from src.download.cache_manager import CacheManager

# Lock para impressão thread-safe
print_lock = Lock()


def thread_safe_print(*args, **kwargs):
    """Imprime de forma thread-safe."""
    with print_lock:
        print(*args, **kwargs)


def get_time_rounded(dt: Optional[datetime] = None) -> tuple:
    """Obtém a data e hora em UTC, arredondada para múltiplo de 10 minutos.

    Parameters
    ----------
    dt : datetime, optional
        Data e hora para arredondar. Se None, usa a data/hora atual.

    Returns
    -------
    tuple
        Tupla com (ano, mês, dia, hora, minuto, dia_do_ano).
    """
    utc_timezone = pytz.timezone("UTC")

    if dt is None:
        dt = datetime.now(utc_timezone)
    else:
        if dt.tzinfo is None:
            dt = utc_timezone.localize(dt)
        else:
            dt = dt.astimezone(utc_timezone)

    # Arredonda para múltiplo de 10 minutos
    minuto_arredondado = dt.minute - (dt.minute % 10)
    dt = dt.replace(minute=minuto_arredondado, second=0, microsecond=0)

    day = str(dt.day).zfill(2)
    month = str(dt.month).zfill(2)
    year = dt.year
    hour = str(dt.hour).zfill(2)
    minute = str(dt.minute).zfill(2)
    day_year = str(dt.timetuple().tm_yday).zfill(3)

    return year, month, day, hour, minute, day_year


def _satellites_for_date(dt: datetime, prefer_goes19: bool) -> list[str]:
    """Define qual(is) satélite(s) usar conforme a data da previsão.

    GOES-19 substitui o GOES-16 como GOES-East: a partir de 2025 usa-se só GOES-19;
    para datas anteriores a 2025 usa-se só GOES-16.

    Parameters
    ----------
    dt : datetime
        Data e hora da previsão.
    prefer_goes19 : bool
        Em períodos onde ambos existem, priorizar GOES-19 (hoje só afeta cache/fallback).

    Returns
    -------
    list[str]
        Lista de satélites a tentar, ex.: ["goes19"] ou ["goes16"].
    """
    if dt.year >= GOES19_ONLY_FROM_YEAR:
        return ["goes19"]
    return ["goes16"]


def download_goes_single(
    dt: datetime,
    cache_manager: CacheManager,
    max_retries: int = 10,
    wait_time: int = 60,
    verbose: bool = True,
    prefer_goes19: bool = True,
) -> dict:
    """Baixa um único arquivo GOES.

    Usa GOES-19 para datas >= 2025 e GOES-16 para datas anteriores a 2025.

    Parameters
    ----------
    dt : datetime
        Data e hora para baixar os dados.
    cache_manager : CacheManager
        Gerenciador de cache para verificar/armazenar arquivos.
    max_retries : int, optional
        Número máximo de tentativas (padrão: 10).
    wait_time : int, optional
        Tempo de espera entre tentativas em segundos (padrão: 60).
    verbose : bool, optional
        Se True, imprime mensagens de status (padrão: True).
    prefer_goes19 : bool, optional
        Mantido para compatibilidade; a escolha do satélite é por data.

    Returns
    -------
    dict
        Dicionário com informações sobre o download:
        - success: bool
        - file_path: Path | None
        - satellite: str | None ('goes19' ou 'goes16')
        - error: str | None
        - from_cache: bool
    """
    result = {
        "success": False,
        "file_path": None,
        "satellite": None,
        "error": None,
        "from_cache": False,
    }

    try:
        year, month, day, hour, minute, day_year = get_time_rounded(dt)

        # Satélite definido pela data: >= 2025 → GOES-19, antes → GOES-16
        satellites = _satellites_for_date(dt, prefer_goes19)

        for sat in satellites:
            # Tenta encontrar no cache pelo nome exato primeiro
            cache_filename = f"OR_ABI-L2-RRQPEF-M6_G1{9 if sat == 'goes19' else 6}_s{year}{day_year}{hour}{minute}.nc"
            cache_path = cache_manager.get_file_path(cache_filename, subdir=sat)

            if cache_path and cache_path.exists():
                if verbose:
                    thread_safe_print(
                        f"✓ Arquivo encontrado no cache ({sat}): {cache_filename}"
                    )
                result["success"] = True
                result["file_path"] = cache_path
                result["satellite"] = sat
                result["from_cache"] = True
                return result

            # Se não encontrou pelo nome exato, procura por padrão (timestamp)
            # Isso cobre casos onde o arquivo foi baixado com nome ligeiramente diferente
            timestamp_pattern = f"_s{year}{day_year}{hour}{minute}"
            matching_files = cache_manager.find_files_by_pattern(
                timestamp_pattern, subdir=sat
            )

            if matching_files:
                # Pega o primeiro arquivo válido encontrado
                cache_path = matching_files[0]
                if verbose:
                    thread_safe_print(
                        f"✓ Arquivo encontrado no cache ({sat}): {cache_path.name}"
                    )
                result["success"] = True
                result["file_path"] = cache_path
                result["satellite"] = sat
                result["from_cache"] = True
                return result

        # Se não encontrou no cache, tenta baixar
        fs = s3fs.S3FileSystem(anon=True)

        for sat in satellites:
            sat_num = 19 if sat == "goes19" else 16
            s3_path = f"noaa-goes{sat_num}/ABI-L2-RRQPEF/{year}/{day_year}/{hour}"

            if verbose:
                thread_safe_print(
                    f"Tentando baixar de {sat} para: {year}-{month}-{day} {hour}:{minute} UTC"
                )

            # Verifica se a pasta existe, com tentativas múltiplas
            retries = 0
            files = []

            while retries < max_retries:
                try:
                    files = fs.ls(s3_path)
                    if files:
                        break
                except FileNotFoundError:
                    pass
                except Exception as e:
                    if verbose:
                        thread_safe_print(f"Erro ao acessar S3 ({sat}): {e}")

                retries += 1
                if verbose and retries < max_retries:
                    thread_safe_print(
                        f"Tentativa {retries} falhou ({sat}). Esperando {wait_time}s..."
                    )
                time.sleep(wait_time)

            if not files:
                if verbose:
                    thread_safe_print(f"Nenhum arquivo encontrado em {sat}")
                continue  # Tenta próximo satélite

            # Filtra arquivo que corresponda ao minuto arredondado
            target_timestamp = f"_s{year}{day_year}{hour}{minute}"
            desired_file = None

            for file in files:
                if target_timestamp in file:
                    desired_file = file
                    break

            # Se não encontrar o arquivo exato, pega o mais recente da hora
            if desired_file is None:
                hour_files = [f for f in files if f"_s{year}{day_year}{hour}" in f]
                if hour_files:
                    desired_file = sorted(hour_files)[-1]
                    if verbose:
                        thread_safe_print(
                            f"Arquivo exato não encontrado ({sat}), usando o mais recente da hora"
                        )
                else:
                    desired_file = sorted(files)[-1]
                    if verbose:
                        thread_safe_print(
                            f"Nenhum arquivo da hora encontrado ({sat}), usando o mais recente do dia"
                        )

            # Define nome do arquivo e caminho no cache
            filename = desired_file.split("/")[-1]
            cache_path = cache_manager.get_cache_path(filename, subdir=sat)

            # Verifica se o arquivo já existe no cache antes de baixar
            if cache_path.exists():
                # Verifica se o arquivo ainda é válido (não expirou)
                file_age = time.time() - cache_path.stat().st_mtime
                max_age_seconds = cache_manager.max_age_hours * 3600

                if file_age <= max_age_seconds:
                    if verbose:
                        thread_safe_print(
                            f"✓ Arquivo já existe no cache ({sat}): {filename}"
                        )
                    result["success"] = True
                    result["file_path"] = cache_path
                    result["satellite"] = sat
                    result["from_cache"] = True
                    return result
                else:
                    # Arquivo expirado, remove para baixar novamente
                    cache_path.unlink()

            # Baixa o arquivo
            if verbose:
                thread_safe_print(f"Baixando {sat}: {filename}")

            fs.get(desired_file, str(cache_path))

            if verbose:
                thread_safe_print(f"✓ Arquivo baixado ({sat}): {filename}")

            result["success"] = True
            result["file_path"] = cache_path
            result["satellite"] = sat
            return result

        # Se chegou aqui, nenhum satélite funcionou
        result["error"] = f"Nenhum arquivo encontrado após {max_retries} tentativas em ambos os satélites"

    except Exception as e:
        result["error"] = str(e)
        if verbose:
            thread_safe_print(f"ERRO ao baixar arquivo: {e}")

    return result


def download_goes_time_range(
    start_dt: datetime,
    end_dt: datetime,
    cache_manager: CacheManager,
    interval_minutes: int = 10,
    max_retries: int = 10,
    wait_time: int = 60,
    verbose: bool = True,
    prefer_goes19: bool = True,
    max_workers: int = 4,
    num_times_needed: int = 4,
) -> dict:
    """Baixa dados GOES para um intervalo de tempo.

    Parameters
    ----------
    start_dt : datetime
        Data/hora de início.
    end_dt : datetime
        Data/hora de fim.
    cache_manager : CacheManager
        Gerenciador de cache.
    interval_minutes : int, optional
        Intervalo em minutos entre downloads (padrão: 10).
    max_retries : int, optional
        Número máximo de tentativas por arquivo (padrão: 10).
    wait_time : int, optional
        Tempo de espera entre tentativas em segundos (padrão: 60).
    verbose : bool, optional
        Se True, imprime mensagens de status (padrão: True).
    prefer_goes19 : bool, optional
        Se True, prioriza GOES-19 (padrão: True).
    max_workers : int, optional
        Número máximo de threads paralelas (padrão: 4).
    num_times_needed : int, optional
        Número de tempos necessários para previsão (padrão: 4).

    Returns
    -------
    dict
        Dicionário com estatísticas do download:
        - total: int
        - success: int
        - from_cache: int
        - downloaded: int
        - errors: int
        - files: list[Path]
    """
    # Gera lista de timestamps
    timestamps = []
    current_dt = start_dt
    while current_dt <= end_dt:
        timestamps.append(current_dt)
        current_dt += timedelta(minutes=interval_minutes)

    # Limita ao número necessário de tempos
    if len(timestamps) > num_times_needed:
        timestamps = timestamps[:num_times_needed]

    total_files = len(timestamps)

    if verbose:
        thread_safe_print(f"\n{'='*60}")
        thread_safe_print(f"DOWNLOAD GOES INICIADO")
        thread_safe_print(
            f"Período: {start_dt.strftime('%Y-%m-%d %H:%M')} até {end_dt.strftime('%Y-%m-%d %H:%M')} UTC"
        )
        thread_safe_print(f"Total de arquivos: {total_files}")
        thread_safe_print(f"Threads paralelas: {max_workers}")
        thread_safe_print(f"Intervalo: {interval_minutes} minutos")
        thread_safe_print(f"{'='*60}\n")

    stats = {
        "total": total_files,
        "success": 0,
        "from_cache": 0,
        "downloaded": 0,
        "errors": 0,
        "files": [],
        "start_time": time.time(),
    }

    # Executa downloads em paralelo
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_dt = {
            executor.submit(
                download_goes_single,
                dt=dt,
                cache_manager=cache_manager,
                max_retries=max_retries,
                wait_time=wait_time,
                verbose=verbose,
                prefer_goes19=prefer_goes19,
            ): dt
            for dt in timestamps
        }

        completed = 0
        for future in as_completed(future_to_dt):
            dt = future_to_dt[future]
            result = future.result()
            completed += 1

            if result["success"]:
                stats["success"] += 1
                stats["files"].append(result["file_path"])
                if result["from_cache"]:
                    stats["from_cache"] += 1
                else:
                    stats["downloaded"] += 1
            else:
                stats["errors"] += 1
                if verbose:
                    thread_safe_print(
                        f"ERRO para {dt.strftime('%Y-%m-%d %H:%M')}: {result['error']}"
                    )

            # Mostra progresso
            if verbose and (completed % 10 == 0 or completed == total_files):
                elapsed = time.time() - stats["start_time"]
                rate = completed / elapsed if elapsed > 0 else 0
                thread_safe_print(
                    f"Progresso: {completed}/{total_files} ({completed/total_files*100:.1f}%) | "
                    f"Sucesso: {stats['success']} | Cache: {stats['from_cache']} | "
                    f"Baixados: {stats['downloaded']} | Erros: {stats['errors']}"
                )

    stats["total_time"] = time.time() - stats["start_time"]

    if verbose:
        thread_safe_print(f"\n{'='*60}")
        thread_safe_print(f"ESTATÍSTICAS FINAIS")
        thread_safe_print(f"Total: {stats['total']}")
        thread_safe_print(f"Sucessos: {stats['success']}")
        thread_safe_print(f"  - Do cache: {stats['from_cache']}")
        thread_safe_print(f"  - Baixados: {stats['downloaded']}")
        thread_safe_print(f"Erros: {stats['errors']}")
        thread_safe_print(f"Tempo total: {stats['total_time']:.2f} segundos")
        thread_safe_print(f"{'='*60}")

    return stats

